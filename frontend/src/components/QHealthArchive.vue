<template>
  <view class="archive-page">
    <view class="page-heading"><view><text class="eyebrow">HEALTH RECORDS</text><text class="page-title">健康档案</text></view><button role="button" tabindex="0" @keydown="activateButton" class="primary" @click="store.archiveMode = 'import'"><QIcon name="plus" />导入医院病历</button></view>
    <view v-if="store.error" class="error" role="alert"><text>{{ store.error }}</text><button role="button" tabindex="0" @keydown="activateButton" v-if="store.error.startsWith('本地保存失败') && !followUpDraft.pendingPlanId && store.archiveMode !== 'import'" class="text-button" @click="store.persist()">重试本地保存</button></view>
    <QMedicalImport v-show="store.archiveMode === 'import'" class="card" @cancel="store.archiveMode = 'list'" @done="importDone" />
    <view v-show="store.archiveMode !== 'import'">
      <view class="profile-strip"><view class="avatar"><QIcon name="user" /></view><view class="profile-content"><text class="profile-name">{{ store.profile.name }}的健康档案</text><text class="description">{{ store.profile.description }} · {{ store.episodes.length }} 个健康问题 · {{ store.records.length }} 份记录</text></view><text class="local-badge">本地演示</text></view>
      <view v-if="selectedRecord && !followUpDraft.visible" class="card record-detail">
        <button role="button" tabindex="0" @keydown="activateButton" class="text-button back" @click="store.selectedRecordId = ''">‹ 返回健康时间线</button>
        <view class="detail-heading"><view><text class="source-label">{{ sourceLabel(selectedRecord.source) }}</text><text class="detail-title">{{ selectedRecord.title }}</text></view><text class="badge">{{ confirmationLabel(selectedRecord) }}</text></view>
        <view class="detail-notice"><QIcon name="info" /><text>{{ selectedRecord.source === 'medical_document' ? '此记录为病历转录。核对状态仅代表转录内容已核对，诊断及“考虑、疑似”等措辞以原始病历为准。' : '此记录为 AI 辅助整理的咨询草稿，用于回顾与就诊沟通，不等同于医生诊断。请结合原对话核对。' }}</text></view>
        <view class="detail-meta"><text>{{ selectedRecord.source === 'medical_document' ? '就诊日期（病历记载）' : '记录时间' }}：{{ selectedRecord.date }}</text><text>关联问题：{{ episodeTitle(selectedRecord.healthEpisodeId) }}</text><text>数据来源：{{ selectedRecord.dataSource === 'demo' ? '虚构演示资料' : '当前设备录入' }}</text><text v-if="selectedRecord.institution">就诊机构：{{ selectedRecord.institution }}{{ selectedRecord.department ? ` · ${selectedRecord.department}` : '' }}</text><text v-if="selectedRecord.sourceFileName">原始文件：{{ selectedRecord.sourceFileName }}（仅保存文件名与转录文字）</text></view>
        <view v-if="selectedRecord.documentedDiagnosis" class="detail-block"><text class="section-title">病历记载诊断（原文）</text><text class="body-text">{{ selectedRecord.documentedDiagnosis }}</text></view>
        <view class="detail-block"><text class="section-title">{{ selectedRecord.source === 'medical_document' ? '就诊情况摘要' : '咨询整理摘要' }}</text><text class="body-text">{{ selectedRecord.summary }}</text></view>
        <view v-if="selectedRecord.medicalInstructions" class="detail-block"><text class="section-title">病历医嘱（转录）</text><text class="body-text">{{ selectedRecord.medicalInstructions }}</text></view>
        <view class="actions"><button role="button" tabindex="0" @keydown="activateButton" v-if="selectedRecord.conversationId" class="secondary" @click="emit('open-conversation', selectedRecord.conversationId)"><QIcon name="chat" />查看原对话</button><button role="button" tabindex="0" @keydown="activateButton" class="primary" @click="beginFollowUp(selectedRecord)"><QIcon name="calendar" />安排后续随访</button><button role="button" tabindex="0" @keydown="activateButton" class="text-button" @click="emit('open-plans')">查看健康计划</button></view>
        <view class="related"><text class="section-title">同一健康问题的记录</text><button role="button" tabindex="0" @keydown="activateButton" v-for="record in relatedRecords" :key="record.id" class="related-row" @click="store.openRecord(record)"><view><text class="record-title">{{ record.title }}</text><text class="description">{{ sourceLabel(record.source) }} · {{ record.date }}</text></view><QIcon name="chevron" /></button><text v-if="!relatedRecords.length" class="description">这是该健康问题的第一份记录。</text></view>
        <view v-if="episodePlans(selectedRecord.healthEpisodeId).length" class="related"><text class="section-title">后续随访</text><button role="button" tabindex="0" @keydown="activateButton" v-for="plan in episodePlans(selectedRecord.healthEpisodeId)" :key="plan.id" class="related-row" @click="emit('open-plans')"><view><text class="record-title">{{ plan.title }}</text><text class="description">{{ plan.scheduledAt }} · {{ planStatus(plan.status) }}</text></view><QIcon name="chevron" /></button></view>
      </view>
      <view v-show="followUpDraft.visible" class="card followup-form">
        <view class="card-heading"><view><text class="section-title">安排后续随访</text><text class="description">关联记录：{{ draftSourceTitle }}</text></view><button role="button" tabindex="0" @keydown="activateButton" class="text-button" @click="followUpDraft.visible = false">收起并暂存</button></view>
        <view v-show="!followUpDraft.pendingPlanId" class="form-grid">
          <view class="field full"><label class="label" for="archive-plan-title">随访标题 *</label><input id="archive-plan-title" v-model="followUpDraft.title" class="input" maxlength="80" placeholder="为这次随访起一个名称" /></view>
          <view class="field"><text class="label">随访日期 *</text><picker mode="date" :value="followUpDraft.date" :start="today" @change="followUpDraft.date = String($event.detail.value)"><view class="picker-value">{{ followUpDraft.date || '选择日期' }}<QIcon name="calendar" /></view></picker></view>
          <view class="field"><text class="label">随访时间 *</text><picker mode="time" :value="followUpDraft.time" @change="followUpDraft.time = String($event.detail.value)"><view class="picker-value">{{ followUpDraft.time || '选择时间' }}<QIcon name="clock" /></view></picker></view>
          <view class="field full"><label class="label" for="archive-plan-goal">随访目标 *</label><textarea id="archive-plan-goal" v-model="followUpDraft.goal" class="textarea" maxlength="1500" placeholder="如：回顾症状、测量记录或就诊后的变化" /></view>
          <view class="field full"><label class="label" for="archive-plan-questions">准备的问题 *（每行一个，至少一题）</label><textarea id="archive-plan-questions" v-model="followUpDraft.questions" class="textarea" maxlength="2000" placeholder="填写希望在随访中回顾的问题" /></view>
        </view>
        <text v-if="followUpDraft.pendingPlanId" class="hint">计划已保留在本次页面，尚未写入本地。请重试保存，不会重复创建。</text><text v-if="formError" class="error" role="alert">{{ formError }}</text><view class="actions"><button role="button" tabindex="0" @keydown="activateButton" class="primary" @click="saveFollowUp">{{ followUpDraft.pendingPlanId ? '重试本地保存' : '确认创建随访' }}</button><button role="button" tabindex="0" @keydown="activateButton" class="secondary" @click="followUpDraft.visible = false">暂存填写</button></view><text class="hint">本地演示不发送后台通知。未提交填写在本次打开应用期间暂存，刷新后会丢失。</text>
      </view>
      <view v-if="createdMessage" class="success" role="status"><text>{{ createdMessage }}</text><button role="button" tabindex="0" @keydown="activateButton" class="text-button" @click="emit('open-plans')">查看健康计划 ›</button></view>
      <view v-show="!selectedRecord && !followUpDraft.visible" class="timeline-section">
        <view class="timeline-heading"><text class="section-title">健康时间线</text><text class="description">按健康问题串起完整经过</text></view>
        <view class="filters" role="tablist" aria-label="档案来源筛选"><button tabindex="0" @keydown="activateButton" v-for="filter in filters" :key="filter.value" role="tab" :aria-selected="activeFilter === filter.value" :class="{ active: activeFilter === filter.value }" @click="activeFilter = filter.value">{{ filter.label }}</button></view>
        <view v-if="!visibleEpisodes.length" class="card empty"><QIcon name="file" /><text class="section-title">{{ store.records.length ? '此分类还没有记录' : '从第一份健康记录开始' }}</text><text class="description">可保存一次咨询，也可以导入已核对的医院病历。</text><button role="button" tabindex="0" @keydown="activateButton" class="secondary" @click="store.archiveMode = 'import'">导入病历</button></view>
        <view v-for="episode in visibleEpisodes" :key="episode.id" class="card episode-card">
          <button role="button" tabindex="0" @keydown="activateButton" class="episode-heading" :aria-expanded="!collapsedIds.includes(episode.id)" @click="toggleEpisode(episode.id)"><view class="episode-symbol"><QIcon name="heart" /></view><view class="episode-heading-copy"><text class="section-title">{{ episode.title }}</text><text class="description">{{ episode.startedAt }} 起 · {{ recordsFor(episode.id).length }} 份记录 · {{ episode.status === 'ongoing' ? '持续关注' : '已结束' }}</text></view><text class="expand-label">{{ collapsedIds.includes(episode.id) ? '展开' : '收起' }}</text></button>
          <view v-show="!collapsedIds.includes(episode.id)" class="timeline">
            <button role="button" tabindex="0" @keydown="activateButton" v-for="record in recordsFor(episode.id)" :key="record.id" class="record-row" @click="store.openRecord(record)"><view class="timeline-dot"><QIcon :name="record.source === 'medical_document' ? 'file' : 'chat'" /></view><view class="record-copy"><view class="record-top"><text class="source-label">{{ sourceLabel(record.source) }}</text><text class="record-date">{{ record.date }}</text></view><text class="record-title">{{ record.title }}</text><text class="record-summary">{{ record.summary }}</text><text class="record-confirmation">{{ confirmationLabel(record) }} · {{ record.dataSource === 'demo' ? '虚构演示' : '本地记录' }}</text></view><QIcon name="chevron" class="chevron" /></button>
            <button role="button" tabindex="0" @keydown="activateButton" v-for="plan in episodePlans(episode.id)" :key="plan.id" class="future-row" @click="emit('open-plans')"><view class="timeline-dot future"><QIcon name="calendar" /></view><view class="record-copy"><text class="record-title">{{ plan.title }}</text><text class="description">{{ plan.scheduledAt }} · {{ planStatus(plan.status) }}</text></view><QIcon name="chevron" class="chevron" /></button>
          </view>
        </view>
      </view>
    </view>
    <text class="page-note">档案仅保存在当前设备，用于健康信息整理；AI 内容需核对，医院诊断与用药以原始医嘱为准。</text>
  </view>
</template>

<script lang="ts">
import { reactive } from 'vue'

const followUpDraft = reactive({ visible: false, recordId: '', healthEpisodeId: '', title: '', date: '', time: '', goal: '', questions: '', pendingPlanId: '' })
</script>

<script setup lang="ts">
import { activateButton } from '@/components/buttonKeyboard'
import { computed, ref } from 'vue'
import QIcon from '@/components/QIcon.vue'
import QMedicalImport from '@/components/QMedicalImport.vue'
import { useConsultationStore } from '@/stores/consultation'
import type { FollowUpPlan, HealthRecord, RecordSource } from '@/types/consultation'

const store = useConsultationStore()
const emit = defineEmits<{ (event: 'open-conversation', conversationId: string): void; (event: 'open-plans'): void }>()
const activeFilter = ref<'all' | RecordSource>('all')
const collapsedIds = ref<string[]>([])
const formError = ref('')
const createdMessage = ref('')
const filters = [{ value: 'all', label: '全部' }, { value: 'ai_consultation', label: 'AI 咨询' }, { value: 'medical_document', label: '医院病历' }, { value: 'ai_follow_up', label: '随访' }] as const
const today = computed(() => store.today())
const selectedRecord = computed(() => store.records.find((record) => record.id === store.selectedRecordId))
const relatedRecords = computed(() => store.records.filter((record) => record.healthEpisodeId === selectedRecord.value?.healthEpisodeId && record.id !== selectedRecord.value?.id).sort((a, b) => b.date.localeCompare(a.date)))
const visibleEpisodes = computed(() => store.episodes.filter((episode) => recordsFor(episode.id).length > 0 || (activeFilter.value === 'all' && episodePlans(episode.id).length > 0)))
const draftSourceTitle = computed(() => store.records.find((record) => record.id === followUpDraft.recordId)?.title || '已选择的健康记录')

function sourceLabel(source: RecordSource) { return ({ ai_consultation: 'AI 咨询整理', medical_document: '医院病历', ai_follow_up: 'AI 随访整理' })[source] }
function confirmationLabel(record: HealthRecord) { return record.source === 'medical_document' ? (record.confirmation === 'confirmed' ? '转录已核对' : '转录待核对') : (record.confirmation === 'confirmed' ? '用户已核对 · AI 草稿' : 'AI 草稿 · 待核对') }
function episodeTitle(id: string) { return store.episodes.find((episode) => episode.id === id)?.title || '健康问题' }
function planStatus(status: string) { return ({ scheduled: '待随访', in_progress: '随访中', completed: '已完成', paused: '已暂停', cancelled: '已取消' } as Record<string, string>)[status] || status }
function recordsFor(episodeId: string) { return store.records.filter((record) => record.healthEpisodeId === episodeId && (activeFilter.value === 'all' || record.source === activeFilter.value)).sort((a, b) => b.date.localeCompare(a.date)) }
function episodePlans(episodeId: string): FollowUpPlan[] { return store.plans.filter((plan): plan is FollowUpPlan => plan.type === 'follow_up' && plan.healthEpisodeId === episodeId).sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt)) }
function toggleEpisode(id: string) { collapsedIds.value = collapsedIds.value.includes(id) ? collapsedIds.value.filter((value) => value !== id) : [...collapsedIds.value, id] }
function importDone(recordId: string) { store.archiveMode = 'list'; store.selectedRecordId = recordId; createdMessage.value = '' }
function beginFollowUp(record: HealthRecord) {
  if (followUpDraft.pendingPlanId) { followUpDraft.visible = true; formError.value = '请先重试保存之前的随访计划。'; return }
  const apply = () => {
    Object.assign(followUpDraft, { visible: true, recordId: record.id, healthEpisodeId: record.healthEpisodeId, title: `${record.title}随访`.slice(0, 80), date: '', time: '', goal: '', questions: '' })
    formError.value = ''; createdMessage.value = ''
  }
  if (followUpDraft.recordId === record.id) { followUpDraft.visible = true; return }
  if (followUpDraft.recordId && (followUpDraft.goal || followUpDraft.date || followUpDraft.questions)) {
    uni.showModal({ title: '改为安排这份记录的随访？', content: '这会替换之前尚未提交的随访填写。', confirmText: '替换填写', success: (result) => { if (result.confirm) apply() } })
  } else apply()
}
function saveFollowUp() {
  formError.value = ''
  if (followUpDraft.pendingPlanId) {
    if (!store.persist()) { formError.value = store.error; return }
    finishFollowUp()
    return
  }
  if (!followUpDraft.title.trim() || !followUpDraft.goal.trim() || !followUpDraft.date || !followUpDraft.time || !followUpDraft.questions.trim()) { formError.value = '请填写随访标题、目标、日期、时间和至少一个问题。'; return }
  if (`${followUpDraft.date} ${followUpDraft.time}:00` <= store.now()) { formError.value = '请选择将来的随访时间（北京时间）。'; return }
  const plan = store.createFollowUpPlan({ healthEpisodeId: followUpDraft.healthEpisodeId, sourceRecordId: followUpDraft.recordId, title: followUpDraft.title, scheduledAt: `${followUpDraft.date} ${followUpDraft.time}`, goal: followUpDraft.goal, questions: followUpDraft.questions.split('\n').map((question) => question.trim()).filter(Boolean) })
  if (!plan) { formError.value = store.error || '未能创建随访，请检查填写并重试，当前内容已保留。'; return }
  if (store.error) { followUpDraft.pendingPlanId = plan.id; formError.value = store.error; return }
  finishFollowUp()
}
function finishFollowUp() {
  Object.assign(followUpDraft, { visible: false, recordId: '', healthEpisodeId: '', title: '', date: '', time: '', goal: '', questions: '', pendingPlanId: '' })
  createdMessage.value = '随访计划已创建，可在健康计划中开始或调整状态。'
}
</script>

<style scoped>
.archive-page { width: 100%; max-width: 1160px; margin: 0 auto; padding: 40px 42px 30px; box-sizing: border-box; color: var(--ink, #1b1b18); }
.page-heading, .card-heading, .detail-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
.page-heading { margin-bottom: 26px; }
.eyebrow { display: block; margin-bottom: 10px; color: var(--muted, #767674); font-size: 12px; font-weight: 700; letter-spacing: 2px; }
.page-title { display: block; font-size: 30px; font-weight: 650; line-height: 1.5; }
.description, .hint { display: block; color: var(--muted, #767674); font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; }
.description { margin-top: 5px; }
button { min-height: 44px; box-sizing: border-box; font-size: 14px; line-height: 1.6; }
.primary, .secondary { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 11px 18px; margin: 0; border-radius: 24px; }
.primary { color: #fff; background: var(--accent, #2463eb); }
.primary :deep(.q-icon) { filter: brightness(0) invert(1); }
.secondary { color: var(--accent, #2463eb); border: 1px solid var(--line, #e4e4df); background: #fff; }
.text-button { margin: 0; padding: 8px 0; color: var(--accent, #2463eb); background: transparent; text-align: left; }
.card { margin-top: 18px; padding: 26px; border: 1px solid var(--line, #e4e4df); border-radius: 18px; background: #fff; min-width: 0; }
.profile-strip { display: flex; align-items: center; gap: 15px; padding: 22px 24px; border: 1px solid var(--line, #e4e4df); border-radius: 18px; background: var(--surface-soft, #f5f5f0); }
.avatar { display: flex; align-items: center; justify-content: center; width: 48px; height: 48px; flex-shrink: 0; border-radius: 14px; background: #fff; }
.profile-content { flex: 1; min-width: 0; }
.profile-name { display: block; font-size: 17px; font-weight: 600; line-height: 1.7; }
.local-badge { padding: 5px 9px; border: 1px solid #deded7; border-radius: 6px; color: var(--muted, #767674); font-size: 12px; flex-shrink: 0; }
.timeline-heading { margin-top: 31px; }
.section-title { display: block; font-size: 18px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.filters { display: flex; gap: 8px; margin: 18px 0; }
.filters button { margin: 0; padding: 10px 15px; color: var(--muted, #767674); background: transparent; border-radius: 9px; }
.filters .active { color: var(--accent, #2463eb); background: var(--surface-tint, #f0f5ff); font-weight: 600; }
.episode-card { padding: 0 24px; }
.episode-heading { display: flex; width: 100%; align-items: center; gap: 13px; padding: 24px 0; margin: 0; text-align: left; background: transparent; color: var(--ink, #1b1b18); }
.episode-symbol { display: flex; flex-shrink: 0; width: 42px; height: 42px; align-items: center; justify-content: center; background: var(--surface-soft, #f5f5f0); border-radius: 12px; }
.episode-heading-copy { flex: 1; min-width: 0; }
.expand-label { flex-shrink: 0; color: var(--muted, #767674); font-size: 12px; }
.record-row, .future-row { display: flex; align-items: flex-start; width: 100%; gap: 16px; padding: 22px 0; margin: 0; border-top: 1px solid var(--line, #e4e4df); border-radius: 0; text-align: left; background: transparent; color: var(--ink, #1b1b18); }
.timeline-dot { display: flex; flex-shrink: 0; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 50%; background: var(--surface-soft, #f5f5f0); }
.timeline-dot .q-icon { width: 18px; height: 18px; }
.timeline-dot.future { border: 1px dashed #d1d1ca; background: #fff; }
.record-copy { flex: 1; min-width: 0; }
.record-top { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 12px; margin-bottom: 7px; }
.source-label { display: block; color: var(--accent, #2463eb); font-size: 12px; line-height: 1.7; }
.record-date { color: var(--muted, #767674); font-size: 12px; line-height: 1.7; }
.record-title { display: block; font-size: 15px; font-weight: 600; line-height: 1.7; overflow-wrap: anywhere; }
.record-summary { display: block; margin-top: 6px; color: var(--muted, #767674); font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; }
.record-confirmation { display: block; color: var(--muted, #767674); font-size: 12px; line-height: 1.7; margin-top: 9px; }
.chevron { width: 14px; height: 14px; margin-top: 12px; opacity: 0.65; }
.detail-title { display: block; margin-top: 5px; font-size: 24px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.back { margin-bottom: 17px; }
.badge { padding: 6px 9px; background: var(--surface-soft, #f5f5f0); color: var(--muted, #767674); border-radius: 7px; font-size: 12px; line-height: 1.7; flex-shrink: 0; }
.detail-notice { display: flex; gap: 9px; margin: 20px 0; padding: 14px; border-radius: 11px; background: var(--surface-soft, #f5f5f0); color: var(--muted, #767674); font-size: 13px; line-height: 1.8; }
.detail-meta { display: flex; flex-direction: column; gap: 8px; color: var(--muted, #767674); font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; }
.detail-block { margin-top: 24px; }
.body-text { display: block; margin-top: 8px; font-size: 15px; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 24px; }
.related { margin-top: 26px; padding-top: 22px; border-top: 1px solid var(--line, #e4e4df); }
.related-row { display: flex; justify-content: space-between; align-items: center; gap: 15px; width: 100%; padding: 15px 0; margin: 0; background: transparent; text-align: left; color: var(--ink, #1b1b18); }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }
.full { grid-column: 1 / -1; }
.field { min-width: 0; }
.label { display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600; line-height: 1.6; }
.input, .textarea, .picker-value { width: 100%; box-sizing: border-box; border: 1px solid var(--line, #e4e4df); border-radius: 10px; background: #fff; color: var(--ink, #1b1b18); font-size: 14px; }
.input { height: 48px; padding: 0 12px; }
.textarea { height: 100px; padding: 12px; line-height: 1.8; }
.picker-value { display: flex; align-items: center; justify-content: space-between; min-height: 48px; gap: 10px; padding: 10px 12px; }
.hint { margin-top: 16px; }
.error { display: block; margin-top: 14px; padding: 12px; background: #fff1f0; color: #a13d39; border-radius: 10px; font-size: 14px; line-height: 1.7; }
.success { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px; margin-top: 18px; padding: 16px; border-radius: 12px; background: #edf7f1; color: #417459; font-size: 14px; line-height: 1.7; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 14px; text-align: center; padding: 40px 20px; }
.page-note { display: block; margin-top: 27px; color: var(--muted, #767674); font-size: 12px; line-height: 1.8; text-align: center; }
@media (max-width: 760px) { .archive-page { padding: 27px 20px; } .page-heading { flex-wrap: wrap; gap: 18px; } .page-title { font-size: 26px; } .card { padding: 20px 16px; } .profile-strip { padding: 18px 16px; gap: 11px; flex-wrap: wrap; } .profile-content { flex-basis: calc(100% - 60px); } .local-badge { margin-left: 59px; } .episode-card { padding: 0 16px; } .episode-heading { padding: 20px 0; gap: 10px; } .episode-symbol { width: 34px; height: 34px; } .section-title { font-size: 16px; } .filters { gap: 3px; } .filters button { flex: 1; padding: 10px 3px; font-size: 13px; } .record-row, .future-row { gap: 10px; } .timeline-dot { width: 28px; height: 28px; } .timeline-dot .q-icon { width: 16px; height: 16px; } .detail-heading { flex-wrap: wrap; gap: 10px; } .detail-title { font-size: 21px; } .form-grid { grid-template-columns: minmax(0, 1fr); } .followup-form .actions .primary { flex: 1; } }
</style>
