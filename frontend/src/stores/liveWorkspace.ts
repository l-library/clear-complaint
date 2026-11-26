import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { getProfile, type Profile } from '@/api/profile'
import { respondReminder, type ReminderItem, type ReminderResponseResult } from '@/api/archive'
import { createIdempotencyKey } from '@/request/idempotency'
import {
  createEpisodeStream, clarifyEpisodeStream, retryEpisodeStream,
  getEpisode, listEpisodes, type AnswerAction, type EpisodeDetail, type EpisodeSummary,
  type EpisodeStreamEvent, type PendingQuestion, type SafetyPayload,
} from '@/api/episodes'


export type WorkspaceTab = 'chat' | 'archive' | 'plans'

interface Message { id: string; role: 'user' | 'assistant'; content: string }
export const useLiveWorkspaceStore = defineStore('live-workspace', () => {
  const auth = useAuthStore()
  const screen = ref<'landing' | 'workspace'>('landing')
  const activeTab = ref<WorkspaceTab>('chat')
  const draft = ref('')
  const messages = ref<Message[]>([])
  const pending = ref(false)
  const error = ref('')
  const stage = ref('')
  const patientProfile = ref<Profile | null>(null)
  const detail = ref<EpisodeDetail | null>(null)
  const episodeId = ref<number | null>(null)
  const pendingQuestion = ref<PendingQuestion | null>(null)
  const answerText = ref('')
  const safety = ref<SafetyPayload | null>(null)
  const notice = ref<{ kind: string; text: string } | null>(null)
  const history = ref<EpisodeSummary[]>([])
  const historyPage = ref(0)
  const historyTotal = ref(0)
  const accountOpen = ref(false)
  const initialized = ref(false)
  const selectedPlanTab = ref<'all' | 'follow_up' | 'medication'>('all')
  const followUpReminder = ref<ReminderItem | null>(null)
  const followUpAnswers = ref({ relieved: '', visited: '', new_symptom: '' })
  const followUpNote = ref('')
  const followUpResponse = ref<ReminderResponseResult | null>(null)
  let generation = 0
  let messageId = 0
  let initialization: Promise<void> | null = null
  let lastRequest: { complaint: string; key: string } | null = null
  const saved = computed(() => Boolean(detail.value?.episode.saved_at))
  const result = computed(() => detail.value?.result ?? null)
  const profile = computed(() => ({ name: patientProfile.value?.name || (auth.isLoggedIn ? '我的账户' : '未登录'), age: patientProfile.value?.age_years, description: auth.user?.phone || '登录后管理健康记录' }))
  const activeConversation = computed(() => episodeId.value ? ({ id: String(episodeId.value), title: detail.value?.episode.complaint_text || messages.value.find((item) => item.role === 'user')?.content || '新的问诊' }) : null)
  const recentConversations = computed(() => history.value.map((item) => ({ id: String(item.id), title: item.complaint_excerpt })))
  const readyToSend = computed(() => auth.isLoggedIn && initialized.value && patientProfile.value && patientProfile.value.required_missing.length === 0)
  function openWorkspace(tab: WorkspaceTab = 'chat') { screen.value = 'workspace'; activeTab.value = tab }
  function newConversation() {
    generation += 1; pending.value = false; messages.value = []; detail.value = null; episodeId.value = null
    pendingQuestion.value = null; answerText.value = ''; safety.value = null; notice.value = null
    error.value = ''; stage.value = ''; lastRequest = null
    followUpReminder.value = null; followUpResponse.value = null; followUpNote.value = ''
    followUpAnswers.value = { relieved: '', visited: '', new_symptom: '' }
    openWorkspace()
  }
  function reset() {
    const previousScreen = screen.value, previousTab = activeTab.value
    newConversation(); screen.value = previousScreen; activeTab.value = previousTab
    history.value = []; historyTotal.value = 0; historyPage.value = 0
    patientProfile.value = null; initialized.value = false; draft.value = ''
    initialization = null
  }
  function addMessage(role: Message['role'], content: string) {
    messages.value.push({ id: `live-${++messageId}`, role, content })
  }
  async function loadHistory(more = false) {
    if (!auth.isLoggedIn) return
    const owner = auth.user?.id
    const page = more ? historyPage.value + 1 : 1
    const response = await listEpisodes(undefined, page)
    if (owner !== auth.user?.id) return
    history.value = more ? [...history.value, ...response.records] : response.records
    historyPage.value = page; historyTotal.value = response.total
  }
  async function initialize(force = false) {
    if (!auth.isLoggedIn || (initialized.value && !force)) return
    if (initialization) return initialization
    const owner = auth.user?.id
    error.value = ''
    const task = (async () => {
      try {
        await auth.ensureFreshSession()
        const response = await getProfile()
        if (owner !== auth.user?.id) return
        patientProfile.value = response.profile
        initialized.value = true
        await loadHistory()
      } catch (cause) { if (owner === auth.user?.id) error.value = message(cause) }
    })()
    initialization = task
    try { await task } finally { if (initialization === task) initialization = null }
  }
  function message(cause: unknown) { return cause instanceof Error ? cause.message : '请求失败，请重试。' }
  function applyDetail(value: EpisodeDetail) {
    detail.value = value; episodeId.value = value.episode.id
    const pending = value.clarify?.pending || null
    // 恢复待答问题；同一编号不重复展示（后端台账幂等）
    if (pending && pendingQuestion.value?.question_id !== pending.question_id) {
      pendingQuestion.value = pending
      answerText.value = ''
    }
    if (!pending) pendingQuestion.value = null
    safety.value = value.gate?.crisis || null
  }
  async function openConversation(id: string) {
    if (!auth.isLoggedIn) { accountOpen.value = true; return false }
    const numeric = Number(id)
    if (!Number.isSafeInteger(numeric) || numeric <= 0) return false
    if (episodeId.value === numeric) { openWorkspace(); return true }
    const run = ++generation
    pending.value = true; error.value = ''
    try {
      const value = await getEpisode(numeric)
      if (run !== generation) return false
      followUpReminder.value = null; followUpResponse.value = null
      messages.value = []; addMessage('user', value.episode.complaint_text)
      applyDetail(value); openWorkspace()
      return true
    } catch (cause) { if (run === generation) error.value = message(cause); return false }
    finally { if (run === generation) pending.value = false }
  }
  async function runStream(action: (onEvent: (event: EpisodeStreamEvent) => void) => Promise<void>) {
    const run = ++generation
    pending.value = true; error.value = ''; stage.value = '正在连接服务…'
    try {
      await auth.ensureFreshSession()
      if (run !== generation) return
      await action((event) => {
        if (run !== generation) return
        const data = event.data
        const id = Number(data.episode_id)
        if (Number.isSafeInteger(id) && id > 0) episodeId.value = id
        if (event.event === 'stage' && typeof data.text === 'string') stage.value = data.text
        if (event.event === 'question' && typeof data.question_id === 'string') {
          // 单问协议（io.6 / request.v2）：一次一问，后端赋稳定号
          pendingQuestion.value = {
            question_id: String(data.question_id),
            purpose: String(data.purpose || 'other'),
            text: String(data.text || ''),
            can_skip: Boolean(data.can_skip),
            not_understood: Boolean(data.not_understood),
          }
          answerText.value = ''
        }
        if (event.event === 'safety' && data.kind === 'crisis') {
          safety.value = {
            kind: 'crisis',
            rule_ids: Array.isArray(data.rule_ids) ? data.rule_ids.map(String) : [],
            version: Number(data.version) || 0,
            copy: Array.isArray(data.copy) ? data.copy.map(String) : [],
          }
        }
        if (event.event === 'notice' && typeof data.text === 'string') {
          notice.value = { kind: String(data.kind || ''), text: data.text }
        }
        if (event.event === 'error') error.value = typeof data.message === 'string' ? data.message : '生成失败，请重试。'
      })
      if (run !== generation) return
      if (!episodeId.value) throw new Error('服务未返回问诊编号，请重试。')
      const value = await getEpisode(episodeId.value)
      if (run !== generation) return
      applyDetail(value)
      if (run === generation) await loadHistory()
    } catch (cause) {
      if (run !== generation) return
      error.value = message(cause)
      if (episodeId.value) {
        try { const value = await getEpisode(episodeId.value); if (run === generation) applyDetail(value) } catch { /* Keep the original error and user input for retry. */ }
      }
    } finally { if (run === generation) { pending.value = false; stage.value = '' } }
  }
  function sendMessage() {
    if (pending.value) return false
    const text = draft.value.trim()
    if (!text) { error.value = '请先填写要描述的内容。'; return false }
    if (!readyToSend.value) { error.value = auth.isLoggedIn ? '请先完善出生日期与性别，并保存档案。' : '请先登录，再开始问诊。'; accountOpen.value = true; return false }
    if (followUpReminder.value) { followUpNote.value = text; void submitFollowUp(); return false }
    if (pendingQuestion.value) { error.value = '请先回答上方的问题。'; return false }
    // 结果后的继续补充沿用同一问诊（issue #23 修订机制），新建问诊走侧栏按钮
    if (episodeId.value && result.value) {
      addMessage('user', text); draft.value = ''
      const id = episodeId.value
      void runStream((onEvent) => clarifyEpisodeStream(id, { question_id: null, action: 'answer', text }, onEvent))
      return false
    }
    newConversation(); addMessage('user', text); draft.value = ''
    lastRequest = { complaint: text, key: createIdempotencyKey() }
    const request = lastRequest
    void runStream((onEvent) => createEpisodeStream(request.complaint, onEvent, patientProfile.value?.city_code || undefined, request.key))
    return true
  }
  async function submitAnswer(action: AnswerAction, text?: string) {
    const question = pendingQuestion.value
    if (!episodeId.value || !question || pending.value) return
    if (action === 'answer' && !answerText.value.trim() && !text?.trim()) {
      error.value = '请写下回答，或选择不知道。'; return
    }
    // 契约第 3 节：对话里显示「我不清楚」「已跳过此问」，都不转成「没有」
    addMessage('user', action === 'answer' ? (text ?? answerText.value).trim() : action === 'unknown' ? '我不清楚' : '已跳过此问')
    const id = episodeId.value
    const questionId = question.question_id
    pendingQuestion.value = null
    const answer = action === 'answer'
      ? { question_id: questionId, action, text: (text ?? answerText.value).trim() }
      : { question_id: questionId, action, text: '' }
    answerText.value = ''
    await runStream((onEvent) => clarifyEpisodeStream(id, answer, onEvent))
  }
  async function retry() {
    if (pending.value) return
    if (episodeId.value && detail.value?.episode.status === 'failed') {
      const id = episodeId.value; await runStream((onEvent) => retryEpisodeStream(id, onEvent))
    } else if (!episodeId.value && lastRequest) {
      const request = lastRequest; await runStream((onEvent) => createEpisodeStream(request.complaint, onEvent, patientProfile.value?.city_code || undefined, request.key))
    } else if (episodeId.value) {
      try { applyDetail(await getEpisode(episodeId.value)); error.value = '' } catch (cause) { error.value = message(cause) }
    }
  }
  function startFollowUp(reminder: ReminderItem) {
    newConversation(); followUpReminder.value = reminder
    addMessage('assistant', reminder.body || reminder.title)
  }
  async function submitFollowUp() {
    const reminder = followUpReminder.value
    if (!reminder || pending.value || reminder.status !== 'pending') return
    if (Object.values(followUpAnswers.value).some((value) => !value)) { error.value = '请先回答三项随访问题。'; return }
    const run = ++generation
    pending.value = true; error.value = ''
    try {
      const response = await respondReminder(reminder.id, { action: 'answer', answers: { ...followUpAnswers.value }, note: followUpNote.value })
      if (run !== generation) return
      followUpResponse.value = response; followUpReminder.value = { ...reminder, status: response.status }
      if (followUpNote.value.trim()) addMessage('user', followUpNote.value.trim())
      draft.value = ''
    } catch (cause) { if (run === generation) error.value = message(cause) }
    finally { if (run === generation) pending.value = false }
  }
  watch(() => auth.user?.id, () => { reset(); if (auth.isLoggedIn) void initialize() })
  return { auth, screen, activeTab, draft, messages, pending, error, stage, patientProfile, detail, result, episodeId,
    pendingQuestion, answerText, safety, notice, saved, profile, activeConversation, recentConversations, history, historyTotal, historyPage,
    accountOpen, initialized, readyToSend, selectedPlanTab,
    followUpReminder, followUpAnswers, followUpNote, followUpResponse, startFollowUp, submitFollowUp,
    initialize, loadHistory, openWorkspace, newConversation, openConversation, sendMessage, submitAnswer, retry, reset }
})
