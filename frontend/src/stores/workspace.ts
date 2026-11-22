import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getArchiveOverview,
  getArchiveTrend,
  getReminders,
  createBloodPressure,
  respondReminder,
  type ArchiveOverview,
  type ArchiveTrend,
  type ReminderResponse,
} from '@/api/archive'
import {
  clarifyEpisodeStream,
  createEpisodeStream,
  getEpisode,
  listEpisodes,
  retryEpisodeStream,
  saveEpisode,
  skipClarifyStream,
  type EpisodeResult,
  type EpisodeStreamEvent,
  type EpisodeSummary,
  type QuestionField,
} from '@/api/episodes'
import { getProfile, type Profile } from '@/api/profile'
import { useAuthStore } from '@/stores/auth'

type WorkspaceTab = 'consult' | 'archive' | 'reminders'
type MessageKind = 'text' | 'stage' | 'question' | 'error'

interface ChatMessage {
  id: number
  role: 'assistant' | 'user'
  kind: MessageKind
  text: string
  title?: string
  items?: string[]
}

const initialMessages: ChatMessage[] = [
  {
    id: 1,
    role: 'assistant',
    kind: 'text',
    text: '您好，我是清诉。请用您自己的话描述不适，我会先确认信息，再给出有依据的就医建议。',
  },
  {
    id: 2,
    role: 'user',
    kind: 'text',
    text: '这两天有点头晕，感觉是没睡好，我想把降压药停两天。',
  },
  {
    id: 3,
    role: 'assistant',
    kind: 'stage',
    text: '已完成主诉理解，发现“自行停药”和“风险淡化”两个需要继续确认的表达。',
  },
  {
    id: 4,
    role: 'assistant',
    kind: 'question',
    title: '还需要确认 3 件事',
    text: '这些信息会影响建议，暂时不会直接给出结论。',
    items: ['症状持续多久？', '最近一次血压是多少？', '有没有心慌、胸痛等伴随症状？'],
  },
]

const quickAnswers = ['持续大约两天', '最近血压 162/98', '偶尔心慌，没有胸痛']

export const useWorkspaceStore = defineStore('workspace', () => {
  const activeTab = ref<WorkspaceTab>('consult')
  const mode = ref<'demo' | 'live'>('demo')
  const messages = ref<ChatMessage[]>(initialMessages.map((item) => ({ ...item })))
  const usedReplies = ref<string[]>([])
  const resultReady = ref(false)
  const typing = ref(false)
  const streamStage = ref('')
  const errorText = ref('')
  const profile = ref<Profile | null>(null)
  const archiveOverview = ref<ArchiveOverview | null>(null)
  const archiveTrend = ref<ArchiveTrend | null>(null)
  const reminderData = ref<ReminderResponse | null>(null)
  const historyEpisodes = ref<EpisodeSummary[]>([])
  const episodeId = ref<number | null>(null)
  const pendingQuestions = ref<QuestionField[]>([])
  const answerDraft = ref<Record<string, string>>({})
  const result = ref<EpisodeResult | null>(null)
  let nextId = 10

  const remainingReplies = computed(() =>
    quickAnswers.filter((item) => !usedReplies.value.includes(item)),
  )
  const liveMode = computed(() => mode.value === 'live')
  const flattenedReminders = computed(() => {
    const groups = reminderData.value?.groups
    if (!groups) return []
    return [...groups.medication, ...groups.followup, ...groups.recheck]
  })

  function switchTab(tab: WorkspaceTab) {
    activeTab.value = tab
  }

  function resetConversation() {
    messages.value =
      mode.value === 'demo'
        ? initialMessages.map((item) => ({ ...item }))
        : [
            {
              id: 1,
              role: 'assistant',
              kind: 'text',
              text: '您好，我是清诉。请先描述目前最困扰您的不适。',
            },
          ]
    usedReplies.value = []
    resultReady.value = false
    typing.value = false
    streamStage.value = ''
    errorText.value = ''
    episodeId.value = null
    pendingQuestions.value = []
    answerDraft.value = {}
    result.value = null
    activeTab.value = 'consult'
    nextId = 10
  }

  async function initialize() {
    const auth = useAuthStore()
    mode.value = auth.demo ? 'demo' : 'live'
    resetConversation()

    if (mode.value === 'demo') {
      return { ok: true, needsLogin: false, needsProfile: false, error: '' }
    }
    if (!auth.isLoggedIn) {
      return { ok: false, needsLogin: true, needsProfile: false, error: '' }
    }

    try {
      await auth.ensureFreshSession()
      const response = await getProfile()
      profile.value = response.profile
      if (!response.profile || response.profile.required_missing.length > 0) {
        return { ok: true, needsLogin: false, needsProfile: true, error: '' }
      }
      await loadArchive()
      return { ok: true, needsLogin: false, needsProfile: false, error: '' }
    } catch (error) {
      errorText.value = error instanceof Error ? error.message : '读取后端数据失败'
      return {
        ok: false,
        needsLogin: false,
        needsProfile: false,
        error: errorText.value,
      }
    }
  }

  async function loadArchive() {
    const [overview, trend, reminders, episodes] = await Promise.all([
      getArchiveOverview(),
      getArchiveTrend(),
      getReminders(),
      listEpisodes('saved'),
    ])
    archiveOverview.value = overview
    archiveTrend.value = trend
    reminderData.value = reminders
    historyEpisodes.value = episodes.records
    profile.value = overview.profile
  }

  function pushUser(text: string) {
    messages.value.push({
      id: nextId++,
      role: 'user',
      kind: 'text',
      text,
    })
  }

  function pushAssistant(text: string, kind: MessageKind = 'text') {
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      kind,
      text,
    })
  }

  function pushQuestion(questions: QuestionField[], round?: number) {
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      kind: 'question',
      title: round ? `第 ${round} 轮补充信息` : '还需要确认关键信息',
      text: '请补充以下信息，信息不足时不会直接给出分诊结论。',
      items: questions.map((item) => item.text),
    })
  }

  function answerQuick(text: string) {
    if (mode.value !== 'demo' || typing.value || resultReady.value || !quickAnswers.includes(text)) {
      return
    }

    pushUser(text)
    usedReplies.value.push(text)
    typing.value = true

    setTimeout(() => {
      if (remainingReplies.value.length > 0) {
        pushAssistant(
          `已记录。还需要补充 ${remainingReplies.value.length} 项关键信息。`,
          'stage',
        )
      } else {
        pushAssistant(
          '信息已齐。我正在整理分诊草稿，随后会展示建议科室、可能情况和证据来源。',
          'stage',
        )
        resultReady.value = true
      }
      typing.value = false
    }, 450)
  }

  function handleStreamEvent(event: EpisodeStreamEvent) {
    const data = event.data
    if (event.event === 'stage') {
      const id = Number(data.episode_id)
      if (Number.isFinite(id)) episodeId.value = id
      const text = typeof data.text === 'string' ? data.text : '正在处理…'
      streamStage.value = text
      pushAssistant(text, 'stage')
      return
    }
    if (event.event === 'question') {
      const id = Number(data.episode_id)
      if (Number.isFinite(id)) episodeId.value = id
      const questions = Array.isArray(data.questions) ? (data.questions as QuestionField[]) : []
      pendingQuestions.value = questions
      answerDraft.value = Object.fromEntries(questions.map((item) => [item.field, '']))
      pushQuestion(questions, Number(data.round) || undefined)
      return
    }
    if (event.event === 'done') {
      const id = Number(data.episode_id)
      if (Number.isFinite(id)) episodeId.value = id
      streamStage.value = ''
      typing.value = false
      resultReady.value = true
      void loadEpisodeResult()
      return
    }
    if (event.event === 'error') {
      const text = typeof data.message === 'string' ? data.message : '本次处理失败，请重试'
      errorText.value = text
      pushAssistant(text, 'error')
    }
  }

  async function loadEpisodeResult() {
    if (!episodeId.value) return
    try {
      const detail = await getEpisode(episodeId.value)
      result.value = detail.result
    } catch (error) {
      errorText.value = error instanceof Error ? error.message : '读取分诊详情失败'
    }
  }

  async function recoverEpisode() {
    if (!episodeId.value) return
    for (let attempt = 0; attempt < 20; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, attempt === 0 ? 300 : 3000))
      try {
        const detail = await getEpisode(episodeId.value)
        if (detail.result) {
          result.value = detail.result
          resultReady.value = true
          pendingQuestions.value = []
          return
        }
        if (detail.clarify?.questions?.length) {
          pendingQuestions.value = detail.clarify.questions
          answerDraft.value = Object.fromEntries(
            detail.clarify.questions.map((item) => [item.field, '']),
          )
          pushQuestion(detail.clarify.questions, detail.clarify.round)
          return
        }
        if (detail.episode.status === 'failed') {
          throw new Error('本轮生成失败，请点击重试')
        }
      } catch (error) {
        if (attempt === 19) {
          errorText.value =
            error instanceof Error ? error.message : '流式连接中断，恢复问诊失败'
        }
      }
    }
  }

  async function createLiveEpisode(text: string) {
    const auth = useAuthStore()
    await auth.ensureFreshSession()
    pushUser(text)
    typing.value = true
    resultReady.value = false
    episodeId.value = null
    pendingQuestions.value = []
    answerDraft.value = {}
    result.value = null
    errorText.value = ''

    try {
      await createEpisodeStream(text, handleStreamEvent)
    } catch (error) {
      errorText.value = error instanceof Error ? error.message : '创建问诊失败'
      pushAssistant(errorText.value, 'error')
      await recoverEpisode()
    } finally {
      typing.value = false
    }
  }

  async function sendMessage(text: string) {
    const value = text.trim()
    if (!value || typing.value) return

    if (mode.value === 'live') {
      if (pendingQuestions.value.length > 0) {
        pushAssistant('请先提交上方的补充信息，再继续描述其他问题。', 'stage')
        return
      }
      await createLiveEpisode(value)
      return
    }

    pushUser(value)
    typing.value = true
    setTimeout(() => {
      pushAssistant(
        '补充信息已记录。当前是本地交互预览，接入后端后会通过流式事件继续追问或更新分诊草稿。',
      )
      typing.value = false
    }, 450)
  }

  async function submitAnswers() {
    if (!episodeId.value || !pendingQuestions.value.length || typing.value) return
    const answers = pendingQuestions.value
      .map((question) => ({
        field: question.field,
        value: (answerDraft.value[question.field] ?? '').trim(),
      }))
      .filter((item) => item.value)
      .map((item) => ({
        ...item,
        is_unknown: ['不知道', '不确定', '跳过'].includes(item.value),
      }))

    if (!answers.length) {
      uni.showToast({ title: '请至少补充一项信息', icon: 'none' })
      return
    }

    const auth = useAuthStore()
    await auth.ensureFreshSession()
    pushUser(answers.map((item) => item.value).join('；'))
    pendingQuestions.value = []
    answerDraft.value = {}
    typing.value = true
    errorText.value = ''
    try {
      await clarifyEpisodeStream(episodeId.value, answers, handleStreamEvent)
    } catch (error) {
      errorText.value = error instanceof Error ? error.message : '提交补充信息失败'
      pushAssistant(errorText.value, 'error')
      await recoverEpisode()
    } finally {
      typing.value = false
    }
  }

  async function skipClarify() {
    if (!episodeId.value || typing.value) return
    pendingQuestions.value = []
    typing.value = true
    try {
      const auth = useAuthStore()
      await auth.ensureFreshSession()
      await skipClarifyStream(episodeId.value, handleStreamEvent)
    } catch (error) {
      errorText.value = error instanceof Error ? error.message : '跳过追问失败'
      await recoverEpisode()
    } finally {
      typing.value = false
    }
  }

  async function retry() {
    if (!episodeId.value || typing.value) return
    typing.value = true
    errorText.value = ''
    try {
      const auth = useAuthStore()
      await auth.ensureFreshSession()
      await retryEpisodeStream(episodeId.value, handleStreamEvent)
    } catch (error) {
      errorText.value = error instanceof Error ? error.message : '重新生成失败'
      await recoverEpisode()
    } finally {
      typing.value = false
    }
  }

  async function saveCurrentEpisode() {
    if (mode.value === 'demo') {
      return { demo: true }
    }
    if (!episodeId.value) throw new Error('当前没有可保存的问诊')
    const saved = await saveEpisode(episodeId.value)
    await loadArchive()
    return { demo: false, saved }
  }

  async function openHistoryEpisode(id: number) {
    if (!id) throw new Error('当前记录没有可读取的详情')
    const detail = await getEpisode(id)
    episodeId.value = id
    result.value = detail.result
    resultReady.value = Boolean(detail.result)
  }

  async function addBloodPressure(payload: {
    measured_at: string
    systolic: number
    diastolic: number
    pulse?: number
  }) {
    if (mode.value === 'demo') {
      return { demo: true }
    }
    const vital = await createBloodPressure(payload)
    await loadArchive()
    return { demo: false, vital }
  }

  async function respondToReminder(id: number, payload: Record<string, unknown>) {
    if (mode.value === 'demo') return { demo: true }
    const response = await respondReminder(id, payload)
    await loadArchive()
    return { demo: false, response }
  }

  return {
    activeTab,
    mode,
    messages,
    usedReplies,
    resultReady,
    typing,
    streamStage,
    errorText,
    profile,
    archiveOverview,
    archiveTrend,
    reminderData,
    historyEpisodes,
    flattenedReminders,
    episodeId,
    pendingQuestions,
    answerDraft,
    result,
    remainingReplies,
    liveMode,
    switchTab,
    resetConversation,
    initialize,
    loadArchive,
    answerQuick,
    sendMessage,
    submitAnswers,
    skipClarify,
    retry,
    saveCurrentEpisode,
    openHistoryEpisode,
    addBloodPressure,
    respondToReminder,
  }
})
