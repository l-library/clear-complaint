import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  ArchiveRecord, ChatMessage, Conversation, FollowUpPlan, FollowUpPlanInput,
  HealthEpisode, HealthPlan, HealthRecord, MedicalRecordInput, MedicationCheckIn,
  MedicationPlan, MedicationPlanInput, PatientProfile, WorkspaceTab,
} from '@/types/consultation'

const storageKey = 'clear-complaint.workspace.v2'
const legacyKey = 'clear-complaint.demo-archive.v1'
const demoProfile: PatientProfile = {
  id: 'demo-patient', name: '演示用户', age: 28, description: '虚构资料，仅用于体验健康记录流程',
}

interface WorkspaceSnapshot {
  version: 2
  conversations: Conversation[]
  episodes: HealthEpisode[]
  records: HealthRecord[]
  plans: HealthPlan[]
  medicationCheckIns: MedicationCheckIn[]
  selectedConversationId: string
  landingDraft: string
}

// Modern Asia/Shanghai dates use UTC+8; UTC accessors avoid the device's time zone.
function now() {
  return new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 19).replace('T', ' ')
}

function today() {
  return now().slice(0, 10)
}

function futureTime(days: number) {
  return new Date(Date.now() + days * 86400000 + 8 * 3600000)
    .toISOString().slice(0, 10) + ' 09:00:00'
}

let sequence = 0
function id(prefix: string) {
  sequence += 1
  return `${prefix}-${Date.now()}-${sequence}-${Math.random().toString(36).slice(2, 7)}`
}

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function textFields(value: Record<string, unknown>, fields: string[]) {
  return fields.every((field) => typeof value[field] === 'string')
}

function optionalText(value: unknown) {
  return value === undefined || typeof value === 'string'
}

function validDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const parsed = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function dateTime(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const normalized = value.trim().replace('T', ' ')
  if (!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?$/.test(normalized)
    || !validDate(normalized.slice(0, 10))) return undefined
  const time = normalized.slice(11)
  if (!/^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/.test(time)) return undefined
  return normalized.length === 16 ? `${normalized}:00` : normalized
}

function validMessage(value: unknown): value is ChatMessage {
  return object(value) && textFields(value, ['id', 'content'])
    && (value.role === 'user' || value.role === 'assistant')
}

function validConversation(value: unknown): value is Conversation {
  return object(value) && textFields(value, ['id', 'patientId', 'title', 'draft', 'createdAt', 'updatedAt'])
    && (value.type === 'consultation' || value.type === 'follow_up')
    && (value.status === 'active' || value.status === 'completed')
    && Array.isArray(value.messages) && value.messages.every(validMessage)
    && ['healthEpisodeId', 'followUpPlanId', 'archivedRecordId'].every((field) => optionalText(value[field]))
    && (value.archivedMessageCount === undefined || (Number.isInteger(value.archivedMessageCount)
      && Number(value.archivedMessageCount) >= 0 && Number(value.archivedMessageCount) <= value.messages.length))
    && Boolean(dateTime(value.createdAt)) && Boolean(dateTime(value.updatedAt))
}

function validEpisode(value: unknown): value is HealthEpisode {
  return object(value) && textFields(value, ['id', 'patientId', 'title', 'startedAt'])
    && (value.status === 'ongoing' || value.status === 'resolved') && validDate(value.startedAt)
}

function validRecord(value: unknown): value is HealthRecord {
  return object(value) && textFields(value, ['id', 'patientId', 'healthEpisodeId', 'title', 'date', 'summary'])
    && ['ai_consultation', 'medical_document', 'ai_follow_up'].includes(String(value.source))
    && (value.confirmation === 'pending' || value.confirmation === 'confirmed')
    && (value.dataSource === 'demo' || value.dataSource === 'local')
    && ['conversationId', 'institution', 'department', 'documentedDiagnosis', 'medicalInstructions', 'sourceFileName']
      .every((field) => optionalText(value[field]))
    && (validDate(value.date) || Boolean(dateTime(value.date)))
}

function validPlan(value: unknown): value is HealthPlan {
  if (!object(value) || !textFields(value, ['id', 'patientId', 'healthEpisodeId', 'title'])
    || !optionalText(value.sourceRecordId)) return false
  if (value.type === 'follow_up') {
    return textFields(value, ['goal', 'scheduledAt']) && Boolean(dateTime(value.scheduledAt))
      && strings(value.questions) && value.questions.length > 0 && optionalText(value.conversationId)
      && ['scheduled', 'in_progress', 'completed', 'paused', 'cancelled'].includes(String(value.status))
  }
  return value.type === 'medication'
    && textFields(value, ['medicineName', 'instructions', 'startDate', 'endDate', 'sourceLabel'])
    && value.sourceConfirmed === true && strings(value.reminderTimes) && value.reminderTimes.length > 0
    && value.reminderTimes.every((time) => /^([01]\d|2[0-3]):[0-5]\d$/.test(time))
    && new Set(value.reminderTimes).size === value.reminderTimes.length
    && validDate(value.startDate) && validDate(value.endDate) && value.endDate >= value.startDate
    && ['active', 'paused', 'ended'].includes(String(value.status))
}

function validCheckIn(value: unknown): value is MedicationCheckIn {
  return object(value) && textFields(value, ['id', 'planId', 'date', 'time', 'recordedAt'])
    && validDate(value.date) && /^([01]\d|2[0-3]):[0-5]\d$/.test(String(value.time))
    && Boolean(dateTime(value.recordedAt)) && (value.outcome === 'taken' || value.outcome === 'skipped')
}

function validSnapshot(value: unknown): value is WorkspaceSnapshot {
  if (!object(value) || value.version !== 2 || !textFields(value, ['selectedConversationId', 'landingDraft'])
    || !Array.isArray(value.conversations) || !value.conversations.every(validConversation)
    || !Array.isArray(value.episodes) || !value.episodes.every(validEpisode)
    || !Array.isArray(value.records) || !value.records.every(validRecord)
    || !Array.isArray(value.plans) || !value.plans.every(validPlan)
    || !Array.isArray(value.medicationCheckIns) || !value.medicationCheckIns.every(validCheckIn)) return false
  const snapshot = value as unknown as WorkspaceSnapshot
  const unique = (items: { id: string }[]) => new Set(items.map((item) => item.id)).size === items.length
  if (![snapshot.conversations, snapshot.episodes, snapshot.records, snapshot.plans, snapshot.medicationCheckIns]
    .every(unique)) return false
  const episodeExists = (episodeId: string) => snapshot.episodes.some((episode) => episode.id === episodeId)
  const conversationExists = (conversationId: string) => snapshot.conversations.some((item) => item.id === conversationId)
  return (!snapshot.selectedConversationId || conversationExists(snapshot.selectedConversationId))
    && snapshot.conversations.every((conversation) => (!conversation.healthEpisodeId || episodeExists(conversation.healthEpisodeId))
      && (!conversation.followUpPlanId || snapshot.plans.some((plan) => plan.type === 'follow_up'
        && plan.id === conversation.followUpPlanId && plan.conversationId === conversation.id
        && plan.healthEpisodeId === conversation.healthEpisodeId))
      && (!conversation.archivedRecordId || snapshot.records.some((record) => record.id === conversation.archivedRecordId
        && record.conversationId === conversation.id)))
    && snapshot.records.every((record) => episodeExists(record.healthEpisodeId)
      && (!record.conversationId || conversationExists(record.conversationId)))
    && snapshot.plans.every((plan) => episodeExists(plan.healthEpisodeId)
      && (!plan.sourceRecordId || snapshot.records.some((record) => record.id === plan.sourceRecordId
        && record.healthEpisodeId === plan.healthEpisodeId))
      && (plan.type !== 'follow_up' || !plan.conversationId || conversationExists(plan.conversationId)))
    && snapshot.medicationCheckIns.every((entry) => snapshot.plans.some((plan) => plan.type === 'medication'
      && plan.id === entry.planId && plan.reminderTimes.includes(entry.time)
      && entry.date >= plan.startDate && entry.date <= plan.endDate))
    && new Set(snapshot.medicationCheckIns.map((entry) => `${entry.planId}/${entry.date}/${entry.time}`)).size
      === snapshot.medicationCheckIns.length
}

function validLegacyRecord(value: unknown): value is ArchiveRecord {
  return object(value) && textFields(value, ['id', 'title', 'date', 'summary', 'complaint', 'status'])
    && (value.messages === undefined || (Array.isArray(value.messages) && value.messages.every(validMessage)))
}

function seed(): WorkspaceSnapshot {
  const timestamp = now()
  return {
    version: 2, selectedConversationId: '', landingDraft: '', medicationCheckIns: [],
    episodes: [{ id: 'demo-stomach', patientId: demoProfile.id, title: '胃部不适（虚构演示）', startedAt: today(), status: 'ongoing' }],
    conversations: [{
      id: 'demo-consultation', patientId: demoProfile.id, type: 'consultation', title: '胃部不适的记录（演示）',
      healthEpisodeId: 'demo-stomach', status: 'active', draft: '', createdAt: timestamp, updatedAt: timestamp,
      archivedRecordId: 'demo-consultation-record', archivedMessageCount: 2,
      messages: [
        { id: 'demo-message-1', role: 'user', content: '【虚构演示】想把这次胃部不适的时间和变化记下来。' },
        { id: 'demo-message-2', role: 'assistant', content: '【流程演示】可记录不适开始时间、持续多久、伴随表现和就诊资料。本演示只整理你提供的信息，不生成诊断或用药建议。' },
      ],
    }],
    records: [
      { id: 'demo-consultation-record', patientId: demoProfile.id, healthEpisodeId: 'demo-stomach', conversationId: 'demo-consultation', source: 'ai_consultation', title: '胃部不适的咨询记录（演示）', date: timestamp, summary: '虚构示例：记录不适时间与变化，准备就诊沟通。', confirmation: 'confirmed', dataSource: 'demo' },
      { id: 'demo-medical-record', patientId: demoProfile.id, healthEpisodeId: 'demo-stomach', source: 'medical_document', title: '门诊资料（虚构演示）', date: today(), summary: '虚构资料，用于展示门诊资料与咨询属于同一健康事件。', institution: '演示医疗机构（虚构）', department: '演示科室', documentedDiagnosis: '未录入；本演示不生成诊断', medicalInstructions: '演示文字：按已确认的个人医嘱记录后续变化。', confirmation: 'confirmed', dataSource: 'demo' },
    ],
    plans: [
      { id: 'demo-follow-up', type: 'follow_up', patientId: demoProfile.id, healthEpisodeId: 'demo-stomach', sourceRecordId: 'demo-consultation-record', title: '胃部不适变化回顾（演示）', scheduledAt: futureTime(2), goal: '回顾本次不适的变化，补充新的就诊信息。', questions: ['和上次记录相比，不适有什么变化？', '期间是否就诊，或有新的资料需要记录？'], status: 'scheduled' },
      { id: 'demo-medication', type: 'medication', patientId: demoProfile.id, healthEpisodeId: 'demo-stomach', sourceRecordId: 'demo-medical-record', title: '示例药物提醒（虚构演示）', medicineName: '示例药物', instructions: '仅演示提醒与打卡流程；不代表真实药物、剂量或频次建议。', reminderTimes: ['09:00', '20:00'], startDate: today(), endDate: futureTime(6).slice(0, 10), sourceLabel: '虚构演示医嘱；不可作为实际用药依据', sourceConfirmed: true, status: 'active' },
    ],
  }
}

export const useConsultationStore = defineStore('consultation', () => {
  const initial = seed()
  const profile = ref<PatientProfile>({ ...demoProfile })
  const screen = ref<'landing' | 'workspace'>('landing')
  const activeTab = ref<WorkspaceTab>('chat')
  const conversations = ref<Conversation[]>(initial.conversations)
  const episodes = ref<HealthEpisode[]>(initial.episodes)
  const records = ref<HealthRecord[]>(initial.records)
  const plans = ref<HealthPlan[]>(initial.plans)
  const medicationCheckIns = ref<MedicationCheckIn[]>(initial.medicationCheckIns)
  const selectedConversationId = ref('')
  const selectedRecordId = ref('')
  const archiveMode = ref<'list' | 'import'>('list')
  const selectedPlanTab = ref<'all' | 'follow_up' | 'medication'>('all')
  const landingDraft = ref('')
  const pending = ref(false)
  const error = ref('')
  let replyTimer: ReturnType<typeof setTimeout> | undefined
  let recoveryRequired = false

  const activeConversation = computed(() => conversations.value.find((item) => item.id === selectedConversationId.value))
  const currentEpisode = computed(() => episodes.value.find((item) => item.id === activeConversation.value?.healthEpisodeId))
  const messages = computed(() => activeConversation.value?.messages || [])
  const recentConversations = computed(() => conversations.value.filter((item) => item.messages.length > 0)
    .slice().sort((left, right) => right.updatedAt.localeCompare(left.updatedAt)))
  const saved = computed(() => Boolean(activeConversation.value?.archivedRecordId)
    && activeConversation.value?.archivedMessageCount === messages.value.length)
  const draft = computed({
    get: () => screen.value === 'landing' ? landingDraft.value : (activeConversation.value?.draft ?? landingDraft.value),
    set: (value: string) => {
      if (screen.value !== 'landing' && activeConversation.value) activeConversation.value.draft = value
      else landingDraft.value = value
      persist()
    },
  })
  const hasUnsavedChanges = computed(() => draft.value.trim().length > 0 || (messages.value.length > 0 && !saved.value))

  function persist() {
    const snapshot: WorkspaceSnapshot = {
      version: 2, conversations: conversations.value, episodes: episodes.value, records: records.value,
      plans: plans.value, medicationCheckIns: medicationCheckIns.value,
      selectedConversationId: selectedConversationId.value, landingDraft: landingDraft.value,
    }
    const recovering = recoveryRequired
    try {
      if (recoveryRequired) {
        // A failed read must be retried before any write can replace an unknown original value.
        const previous: unknown = uni.getStorageSync(storageKey)
        if (previous !== undefined && previous !== null && previous !== '') {
          uni.setStorageSync(`${storageKey}.recovery.${id('backup')}`, previous)
        }
        recoveryRequired = false
      }
      // Store a plain snapshot so later reactive changes cannot mutate storage by reference.
      uni.setStorageSync(storageKey, JSON.parse(JSON.stringify(snapshot)))
      if (recovering || error.value.startsWith('本地保存失败')) error.value = ''
      return true
    } catch {
      error.value = '本地保存失败；本次内容仍保留在当前页面，刷新前请重试保存。'
      return false
    }
  }

  function load() {
    try {
      const stored: unknown = uni.getStorageSync(storageKey)
      if (stored !== undefined && stored !== null && stored !== '') {
        if (!validSnapshot(stored)) {
          recoveryRequired = true
          error.value = '本地工作区数据格式异常，暂时显示演示内容；后续保存前会先备份原数据。'
          return
        }
        const snapshot: WorkspaceSnapshot = JSON.parse(JSON.stringify(stored))
        conversations.value = snapshot.conversations
        episodes.value = snapshot.episodes
        records.value = snapshot.records
        plans.value = snapshot.plans
        medicationCheckIns.value = snapshot.medicationCheckIns
        selectedConversationId.value = snapshot.selectedConversationId
        landingDraft.value = snapshot.landingDraft
        return
      }
      const legacy: unknown = uni.getStorageSync(legacyKey)
      if (legacy === undefined || legacy === null || legacy === '') return
      if (!Array.isArray(legacy) || !legacy.every(validLegacyRecord)) {
        error.value = '旧版归档数据格式异常，未迁移；原始归档仍保留在本地。'
        return
      }
      legacy.forEach((record) => {
        const episodeId = id('migrated-episode')
        const conversationId = id('migrated-conversation')
        const recordId = records.value.some((item) => item.id === record.id) ? id('migrated-record') : record.id
        const timestamp = dateTime(record.date) || now()
        const restoredMessages = record.messages?.length ? record.messages.map((message) => ({ ...message })) : [
          { id: id('message'), role: 'user' as const, content: record.complaint },
          { id: id('message'), role: 'assistant' as const, content: record.summary },
        ]
        episodes.value.push({ id: episodeId, patientId: profile.value.id, title: record.title, startedAt: timestamp.slice(0, 10), status: 'ongoing' })
        conversations.value.push({ id: conversationId, patientId: profile.value.id, type: 'consultation', title: record.title, healthEpisodeId: episodeId, status: 'active', messages: restoredMessages, draft: '', createdAt: timestamp, updatedAt: timestamp, archivedRecordId: recordId, archivedMessageCount: restoredMessages.length })
        records.value.push({ id: recordId, patientId: profile.value.id, healthEpisodeId: episodeId, conversationId, source: 'ai_consultation', title: record.title, date: timestamp, summary: record.summary, confirmation: 'confirmed', dataSource: 'local' })
      })
      persist()
    } catch {
      recoveryRequired = true
      error.value = '本地保存失败；无法读取原存储，当前内容保留在页面中，请稍后重试。'
    }
  }

  function cancelReply() {
    if (replyTimer !== undefined) clearTimeout(replyTimer)
    replyTimer = undefined
    pending.value = false
  }

  function openWorkspace(tab: WorkspaceTab = 'chat') {
    screen.value = 'workspace'
    activeTab.value = tab
  }

  function newConversation(healthEpisodeId?: string): string {
    const episode = episodes.value.find((item) => item.id === healthEpisodeId)
    if (healthEpisodeId && !episode) {
      error.value = '所选健康事件不存在，未创建新对话。'
      return ''
    }
    cancelReply()
    error.value = ''
    const timestamp = now()
    const conversation: Conversation = {
      id: id('conversation'), patientId: profile.value.id, type: 'consultation', title: '新的健康咨询',
      healthEpisodeId: episode?.id, status: 'active', messages: [], draft: '', createdAt: timestamp, updatedAt: timestamp,
    }
    conversations.value.push(conversation)
    selectedConversationId.value = conversation.id
    openWorkspace()
    persist()
    return conversation.id
  }

  function openConversation(conversationId: string) {
    if (!conversations.value.some((item) => item.id === conversationId)) {
      error.value = '未找到这段对话。'
      return false
    }
    if (selectedConversationId.value === conversationId) {
      openWorkspace()
      return true
    }
    cancelReply()
    selectedConversationId.value = conversationId
    error.value = ''
    openWorkspace()
    persist()
    return true
  }

  function sendMessage() {
    const fromLanding = screen.value === 'landing'
    if (pending.value && !fromLanding) return
    const content = draft.value.trim()
    if (!content) {
      error.value = '请先填写要记录的内容。'
      return
    }
    if (fromLanding) {
      newConversation()
      landingDraft.value = ''
    }
    if (activeConversation.value?.status === 'completed') {
      error.value = '本次随访已完成，内容保持归档。请新建咨询记录后续补充，草稿已保留。'
      return
    }
    if (activeConversation.value?.type === 'follow_up') {
      const linkedPlan = plans.value.find((plan) => plan.id === activeConversation.value?.followUpPlanId)
      if (!linkedPlan || linkedPlan.status !== 'in_progress') {
        error.value = '此随访计划当前不可填写，请先恢复计划。'
        return
      }
    }
    if (!activeConversation.value) {
      newConversation()
      landingDraft.value = ''
    }
    const conversation = activeConversation.value
    if (!conversation) return
    error.value = ''
    conversation.messages.push({ id: id('message'), role: 'user', content })
    conversation.draft = ''
    if (conversation.messages.length === 1) conversation.title = content.length > 24 ? `${content.slice(0, 24)}…` : content
    conversation.updatedAt = now()
    openWorkspace()
    pending.value = true
    persist()
    const conversationId = conversation.id
    replyTimer = setTimeout(() => {
      const target = conversations.value.find((item) => item.id === conversationId)
      if (target && target.status === 'active') {
        const content = target.type === 'follow_up'
          ? '【本地流程演示】你的补充已记录。请核对描述是否准确；保存本次随访后，记录会关联到原健康事件，计划将标记为已完成。本演示不判断病情变化或调整治疗。'
          : target.messages.filter((message) => message.role === 'user').length === 1
            ? '【本地流程演示】为了整理这次描述，可以补充不适何时开始、持续多久、伴随表现，以及已有的就诊或用药资料。这里仅记录你提供的信息，不作诊断，也不生成剂量建议。'
            : '【本地流程演示】补充内容已记录。你可以继续完善，或核对后保存到健康档案；本演示尚未接入医疗问答服务。'
        target.messages.push({ id: id('message'), role: 'assistant', content })
        target.updatedAt = now()
      }
      replyTimer = undefined
      pending.value = false
      persist()
    }, 650)
  }

  function saveConversation(): HealthRecord | undefined {
    const conversation = activeConversation.value
    if (!conversation || !conversation.messages.some((message) => message.role === 'user') || pending.value) {
      error.value = pending.value ? '请等待本次记录完成后再保存。' : '补充内容后再保存这段对话。'
      return undefined
    }
    error.value = ''
    if (saved.value) {
      persist()
      return records.value.find((record) => record.id === conversation.archivedRecordId)
    }
    if (!conversation.healthEpisodeId) {
      const episode: HealthEpisode = { id: id('episode'), patientId: profile.value.id, title: conversation.title, startedAt: conversation.createdAt.slice(0, 10), status: 'ongoing' }
      episodes.value.unshift(episode)
      conversation.healthEpisodeId = episode.id
    }
    const description = conversation.messages.filter((message) => message.role === 'user')
      .map((message) => message.content).join('；')
    const record: HealthRecord = {
      id: conversation.archivedRecordId || id('record'), patientId: profile.value.id,
      healthEpisodeId: conversation.healthEpisodeId, conversationId: conversation.id,
      source: conversation.type === 'follow_up' ? 'ai_follow_up' : 'ai_consultation',
      title: conversation.title, date: now(),
      summary: `本人描述：${description.slice(0, 240)}${description.length > 240 ? '…' : ''}（本地记录，未经医疗判断）`,
      confirmation: 'confirmed', dataSource: 'local',
    }
    const existing = records.value.findIndex((item) => item.id === record.id)
    if (existing >= 0) records.value.splice(existing, 1, record)
    else records.value.unshift(record)
    conversation.archivedRecordId = record.id
    conversation.archivedMessageCount = conversation.messages.length
    conversation.updatedAt = now()
    if (conversation.type === 'follow_up') {
      const plan = plans.value.find((item) => item.id === conversation.followUpPlanId)
      if (plan?.type === 'follow_up') plan.status = 'completed'
      conversation.status = 'completed'
    }
    selectedRecordId.value = record.id
    persist()
    return record
  }

  function importMedicalRecord(input: MedicalRecordInput): HealthRecord | undefined {
    const recordDate = validDate(input.date) ? input.date : dateTime(input.date)
    const episode = episodes.value.find((item) => item.id === input.healthEpisodeId)
    if (!input.title.trim() || !input.summary.trim() || !recordDate || recordDate.slice(0, 10) > today()
      || (input.healthEpisodeId ? !episode : !input.episodeTitle?.trim())) {
      error.value = '请填写资料标题、本人核对后的摘要和有效日期，并选择或新建健康事件。'
      return undefined
    }
    error.value = ''
    let episodeId = episode?.id
    if (!episodeId) {
      episodeId = id('episode')
      episodes.value.unshift({ id: episodeId, patientId: profile.value.id, title: input.episodeTitle!.trim(), startedAt: recordDate.slice(0, 10), status: 'ongoing' })
    }
    const record: HealthRecord = {
      id: id('record'), patientId: profile.value.id, healthEpisodeId: episodeId, source: 'medical_document',
      title: input.title.trim(), date: recordDate, summary: input.summary.trim(),
      institution: input.institution.trim() || undefined, department: input.department.trim() || undefined,
      documentedDiagnosis: input.documentedDiagnosis.trim() || undefined,
      medicalInstructions: input.medicalInstructions.trim() || undefined,
      sourceFileName: input.sourceFileName?.trim() || undefined, confirmation: 'confirmed', dataSource: 'local',
    }
    records.value.unshift(record)
    openRecord(record)
    persist()
    return record
  }

  function validPlanSource(healthEpisodeId: string, sourceRecordId?: string) {
    return episodes.value.some((episode) => episode.id === healthEpisodeId)
      && (!sourceRecordId || records.value.some((record) => record.id === sourceRecordId && record.healthEpisodeId === healthEpisodeId))
  }

  function createFollowUpPlan(input: FollowUpPlanInput): FollowUpPlan | undefined {
    const scheduledAt = dateTime(input.scheduledAt)
    const questions = input.questions.map((question) => question.trim()).filter(Boolean)
    if (!validPlanSource(input.healthEpisodeId, input.sourceRecordId) || !input.title.trim() || !input.goal.trim()
      || !scheduledAt || scheduledAt < now() || questions.length === 0) {
      error.value = '请选择有效的健康事件与同一事件的来源记录，填写未来的随访时间、目标和至少一个问题。'
      return undefined
    }
    const plan: FollowUpPlan = {
      id: id('follow-up'), type: 'follow_up', patientId: profile.value.id,
      healthEpisodeId: input.healthEpisodeId, sourceRecordId: input.sourceRecordId || undefined,
      title: input.title.trim(), scheduledAt, goal: input.goal.trim(), questions, status: 'scheduled',
    }
    error.value = ''
    plans.value.unshift(plan)
    persist()
    return plan
  }

  function startFollowUp(planId: string): string | undefined {
    const plan = plans.value.find((item) => item.id === planId)
    if (!plan || plan.type !== 'follow_up') {
      error.value = '未找到这项随访计划。'
      return undefined
    }
    if (plan.status === 'cancelled' || plan.status === 'paused') {
      error.value = '请先恢复这项随访计划。'
      return undefined
    }
    if (plan.conversationId && conversations.value.some((item) => item.id === plan.conversationId)) {
      if (plan.status === 'scheduled') plan.status = 'in_progress'
      openConversation(plan.conversationId)
      persist()
      return plan.conversationId
    }
    if (plan.status === 'completed') {
      error.value = '这项随访已完成，没有可继续填写的对话。'
      return undefined
    }
    cancelReply()
    const episode = episodes.value.find((item) => item.id === plan.healthEpisodeId)
    const timestamp = now()
    const conversation: Conversation = {
      id: id('follow-up-conversation'), patientId: profile.value.id, type: 'follow_up',
      title: plan.title, healthEpisodeId: plan.healthEpisodeId, followUpPlanId: plan.id,
      status: 'active', draft: '', createdAt: timestamp, updatedAt: timestamp,
      messages: [{ id: id('message'), role: 'assistant', content: `【本地随访演示】\n健康事件：${episode?.title || '未命名事件'}\n随访目标：${plan.goal}\n\n${plan.questions.map((question, index) => `${index + 1}. ${question}`).join('\n')}\n\n请按实际情况补充。本演示只整理记录，不生成诊断或治疗建议。` }],
    }
    conversations.value.push(conversation)
    plan.conversationId = conversation.id
    plan.status = 'in_progress'
    selectedConversationId.value = conversation.id
    error.value = ''
    openWorkspace()
    persist()
    return conversation.id
  }

  function createMedicationPlan(input: MedicationPlanInput): MedicationPlan | undefined {
    const times = [...new Set(input.reminderTimes.map((time) => time.trim()))].sort()
    const personalSource = input.sourceLabel.trim()
    const onlyGeneralSource = /说明书|百科|搜索|网络|网页|通用|科普|leaflet|wikipedia/i.test(personalSource)
      && !/医生|医师|处方|个人医嘱|本人医嘱|门诊|出院医嘱|医嘱单|药师核对|prescription/i.test(personalSource)
    if (!validPlanSource(input.healthEpisodeId, input.sourceRecordId) || !input.medicineName.trim()
      || !input.instructions.trim() || !input.sourceConfirmed || !personalSource || onlyGeneralSource
      || !times.length || times.some((time) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))
      || !validDate(input.startDate) || !validDate(input.endDate) || input.endDate < input.startDate
      || input.endDate < today()) {
      error.value = '请按本人已确认的医嘱或处方填写药名、用法、有效日期和提醒时间。通用说明书不能代替个人用药依据。'
      return undefined
    }
    const plan: MedicationPlan = {
      id: id('medication'), type: 'medication', patientId: profile.value.id, healthEpisodeId: input.healthEpisodeId,
      sourceRecordId: input.sourceRecordId || undefined, title: `${input.medicineName.trim()}用药提醒`,
      medicineName: input.medicineName.trim(), instructions: input.instructions.trim(), reminderTimes: times,
      startDate: input.startDate, endDate: input.endDate, sourceLabel: personalSource,
      sourceConfirmed: true, status: 'active',
    }
    error.value = ''
    plans.value.unshift(plan)
    persist()
    return plan
  }

  function setPlanStatus(planId: string, status: HealthPlan['status']) {
    const plan = plans.value.find((item) => item.id === planId)
    const allowed = plan?.type === 'follow_up'
      ? ['scheduled', 'in_progress', 'completed', 'paused', 'cancelled'] : ['active', 'paused', 'ended']
    if (!plan || !allowed.includes(status)) {
      error.value = '计划状态无效。'
      return false
    }
    if (plan.type === 'follow_up' && plan.status === 'completed' && status !== 'completed') {
      error.value = '已完成的随访仅可回看，请新建计划安排下一次随访。'
      return false
    }
    error.value = ''
    if (plan.type === 'follow_up') {
      plan.status = status as FollowUpPlan['status']
      const conversation = conversations.value.find((item) => item.id === plan.conversationId)
      if (conversation) {
        if (selectedConversationId.value === conversation.id) cancelReply()
        conversation.status = status === 'completed' ? 'completed' : 'active'
      }
    } else plan.status = status as MedicationPlan['status']
    persist()
    return true
  }

  function medicationOutcome(planId: string, time: string) {
    return medicationCheckIns.value.find((entry) => entry.planId === planId && entry.date === today() && entry.time === time)?.outcome
  }

  function markMedication(planId: string, time: string, outcome: MedicationCheckIn['outcome']) {
    const plan = plans.value.find((item) => item.id === planId)
    const day = today()
    if (!plan || plan.type !== 'medication' || plan.status !== 'active' || !plan.sourceConfirmed
      || !plan.reminderTimes.includes(time) || day < plan.startDate || day > plan.endDate
      || now().slice(11, 16) < time || !['taken', 'skipped'].includes(outcome)) {
      error.value = '仅可记录进行中计划里，今天已到时间的用药提醒。'
      return false
    }
    error.value = ''
    const existing = medicationCheckIns.value.find((entry) => entry.planId === planId && entry.date === day && entry.time === time)
    if (existing) {
      if (existing.outcome !== outcome) error.value = '这次提醒已有打卡记录，未重复记录。'
      else persist()
      return existing.outcome === outcome
    }
    medicationCheckIns.value.push({ id: id('check-in'), planId, date: day, time, outcome, recordedAt: now() })
    persist()
    return true
  }

  function openRecord(record: HealthRecord) {
    if (!records.value.some((item) => item.id === record.id)) {
      error.value = '未找到这份健康记录。'
      return
    }
    selectedRecordId.value = record.id
    archiveMode.value = 'list'
    error.value = ''
    openWorkspace('archive')
  }

  load()

  return {
    screen, activeTab, draft, messages, pending, error, profile, conversations, episodes, records, plans,
    medicationCheckIns, activeConversation, currentEpisode, recentConversations, saved, hasUnsavedChanges,
    selectedConversationId, selectedRecordId, archiveMode, selectedPlanTab,
    openWorkspace, newConversation, openConversation, sendMessage, saveConversation, importMedicalRecord,
    createFollowUpPlan, startFollowUp, createMedicationPlan, setPlanStatus, markMedication, medicationOutcome,
    openRecord, persist, now, today,
  }
})
