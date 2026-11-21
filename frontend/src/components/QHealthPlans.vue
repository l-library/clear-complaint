<template>
  <view class="plans-page">
    <view class="page-heading"><view><text class="eyebrow">HEALTH PLANS</text><text class="page-title">健康计划</text><text class="description">把随访与医嘱安排好，一步步照顾自己。</text></view><button class="primary" @click="showForm = true"><QIcon name="plus" />{{ hasDraft ? '继续填写计划' : '新建计划' }}</button></view>
    <view class="notice"><QIcon name="clock" /><text>本地演示 · 计划不发送后台通知。当前有 {{ upcomingCount }} 项待随访，{{ activeMedicationCount }} 项用药计划进行中。</text></view>
    <view v-if="store.error" class="error" role="alert"><text>{{ store.error }}</text><button v-if="store.error.startsWith('本地保存失败') && !planDraft.pendingPlanId" class="text-button" @click="store.persist()">重试本地保存</button></view>

    <view v-show="showForm" class="card plan-form">
      <view class="card-heading"><text class="section-title">{{ form.type === 'follow_up' ? '新建随访计划' : '新建用药计划' }}</text><button class="text-button" @click="showForm = false">收起并暂存</button></view>
      <view v-show="!planDraft.pendingPlanId">
      <view class="type-switch"><button :class="{ selected: form.type === 'follow_up' }" :aria-pressed="form.type === 'follow_up'" @click="form.type = 'follow_up'">随访计划</button><button :class="{ selected: form.type === 'medication' }" :aria-pressed="form.type === 'medication'" @click="form.type = 'medication'">用药计划</button></view>
      <view class="form-grid">
        <view class="field full"><text class="label">关联健康问题 *</text><picker :range="episodeOptions" :value="episodeIndex" @change="changeEpisode"><view class="picker-value">{{ episodeOptions[episodeIndex] }}<text>⌄</text></view></picker><text v-if="!store.episodes.length" class="hint">请先在健康档案保存一份咨询或病历，建立健康问题。</text></view>
        <view class="field full"><text class="label">{{ form.type === 'medication' ? '个体化医嘱来源 *' : '关联来源（选填）' }}</text><picker :range="sourceOptions" :value="sourceIndex" @change="changeSource"><view class="picker-value">{{ sourceOptions[sourceIndex] }}<text>⌄</text></view></picker></view>
        <template v-if="form.type === 'follow_up'">
          <view class="field full"><label class="label" for="plan-title">随访标题 *</label><input id="plan-title" v-model="form.title" class="input" maxlength="80" placeholder="如：回顾本周症状变化" /></view>
          <view class="field"><text class="label">随访日期 *</text><picker mode="date" :value="form.date" :start="today" @change="form.date = String($event.detail.value)"><view class="picker-value">{{ form.date || '选择日期' }}<QIcon name="calendar" /></view></picker></view>
          <view class="field"><text class="label">随访时间 *</text><picker mode="time" :value="form.time" @change="form.time = String($event.detail.value)"><view class="picker-value">{{ form.time || '选择时间' }}<QIcon name="clock" /></view></picker></view>
          <view class="field full"><label class="label" for="plan-goal">随访目标 *</label><textarea id="plan-goal" v-model="form.goal" class="textarea" maxlength="1500" placeholder="希望回顾哪些变化或补充哪些信息？" /></view>
          <view class="field full"><label class="label" for="plan-questions">准备的问题 *（每行一个，至少一题）</label><textarea id="plan-questions" v-model="form.questions" class="textarea" maxlength="2000" placeholder="如：症状是否改善？是否按原医嘱用药？" /></view>
        </template>
        <template v-else>
          <view class="field full"><label class="label" for="medicine-name">药品名称 *</label><input id="medicine-name" v-model="form.medicineName" class="input" maxlength="100" placeholder="按本人当前医嘱填写" /></view>
          <view class="field full"><label class="label" for="medicine-instructions">本人当前用法用量 *</label><textarea id="medicine-instructions" v-model="form.instructions" class="textarea" maxlength="2000" placeholder="照录医生为本人开具的具体用法用量，不以药品说明书替代" /></view>
          <view class="field full"><label class="label" for="medicine-source">医嘱来源说明 *</label><input id="medicine-source" v-model="form.sourceLabel" class="input" maxlength="160" placeholder="如：本人已核对的某院门诊医嘱及日期" /></view>
          <view class="field"><text class="label">开始日期 *</text><picker mode="date" :value="form.startDate" @change="form.startDate = String($event.detail.value)"><view class="picker-value">{{ form.startDate || '选择日期' }}<QIcon name="calendar" /></view></picker></view>
          <view class="field"><text class="label">结束日期 *</text><picker mode="date" :value="form.endDate" :start="form.startDate" @change="form.endDate = String($event.detail.value)"><view class="picker-value">{{ form.endDate || '选择日期' }}<QIcon name="calendar" /></view></picker></view>
          <view class="field full"><label class="label" for="medicine-times">每日记录时间 *</label><input id="medicine-times" v-model="form.reminderTimes" class="input" maxlength="100" placeholder="24小时制，如 08:00, 20:00" /><text class="hint">使用英文或中文逗号分隔。这里只记录安排，不发送通知。</text></view>
          <button class="confirmation full" role="checkbox" :aria-checked="form.sourceConfirmed" @click="form.sourceConfirmed = !form.sourceConfirmed"><view class="check-box" :class="{ checked: form.sourceConfirmed }"><QIcon v-if="form.sourceConfirmed" name="check" /></view><text>我确认这是医生为本人制定、目前仍在执行的个体化医嘱，并已核对药品、用法用量和时间。AI 不生成或调整剂量。</text></button>
        </template>
      </view>
      </view>
      <text v-if="planDraft.pendingPlanId" class="hint">计划已保留在本次页面，尚未写入本地。请重试保存，不会重复创建。</text>
      <text v-if="formError" class="error" role="alert">{{ formError }}</text>
      <view class="actions"><button class="primary" @click="savePlan"><QIcon name="check" />{{ planDraft.pendingPlanId ? '重试本地保存' : '确认创建' }}</button><button class="secondary" @click="showForm = false">暂存填写</button></view>
      <text class="hint form-note">未提交内容在本次打开应用期间暂存，刷新后会丢失。</text>
    </view>

    <view class="tabs" role="tablist" aria-label="健康计划类型"><button v-for="tab in tabs" :key="tab.value" role="tab" :aria-selected="store.selectedPlanTab === tab.value" :class="{ active: store.selectedPlanTab === tab.value }" @click="store.selectedPlanTab = tab.value">{{ tab.label }}</button></view>
    <text v-if="actionError" class="error" role="alert">{{ actionError }}</text>
    <view v-if="!filteredPlans.length" class="card empty"><QIcon name="calendar" /><text class="section-title">留一个时间，关心后来的变化</text><text class="description">从一次随访开始，或按已核对的本人医嘱建立用药计划。</text><button class="secondary" @click="showForm = true">新建计划</button></view>
    <view v-for="plan in filteredPlans" :key="plan.id" class="card plan-card">
      <view class="card-heading"><view class="plan-heading"><view class="plan-icon"><QIcon :name="plan.type === 'follow_up' ? 'calendar' : 'heart'" /></view><view><text class="section-title">{{ plan.title }}</text><text class="description">{{ episodeTitle(plan.healthEpisodeId) }}</text></view></view><text class="status" :class="{ paused: plan.status === 'paused' }">{{ statusLabel(plan.status) }}</text></view>
      <template v-if="plan.type === 'follow_up'">
        <text class="schedule"><QIcon name="clock" />{{ plan.scheduledAt }}</text>
        <text class="body-text">{{ plan.goal }}</text>
        <text v-if="plan.questions.length" class="description">准备问题：{{ plan.questions.join('；') }}</text>
        <text class="source">来源：{{ sourceTitle(plan.sourceRecordId) }}</text>
        <view class="actions"><button v-if="['scheduled', 'in_progress'].includes(plan.status)" class="primary" @click="startFollowUp(plan.id)"><QIcon name="chat" />{{ plan.conversationId ? '继续随访' : '开始随访' }}</button><button v-if="plan.status === 'completed'" class="secondary" @click="viewFollowUp(plan)">查看随访记录</button><button v-if="['scheduled', 'in_progress', 'paused'].includes(plan.status)" class="secondary" @click="store.setPlanStatus(plan.id, plan.status === 'paused' ? (plan.conversationId ? 'in_progress' : 'scheduled') : 'paused')">{{ plan.status === 'paused' ? '恢复计划' : '暂停计划' }}</button></view>
      </template>
      <template v-else>
        <text class="body-text">{{ plan.medicineName }} · {{ plan.instructions }}</text><text class="description">{{ plan.startDate }} 至 {{ plan.endDate }} · 每日 {{ plan.reminderTimes.join('、') }}</text><text class="source">医嘱来源：{{ plan.sourceLabel }}{{ plan.sourceRecordId ? ` · ${sourceTitle(plan.sourceRecordId)}` : '' }}</text>
        <view v-if="plan.status === 'active' && today >= plan.startDate && today <= plan.endDate" class="today-checkins"><text class="label">今日用药记录 · {{ today }}</text><view v-for="time in plan.reminderTimes" :key="time" class="checkin"><view><text class="time">{{ time }}</text><text v-if="currentTime.slice(11, 16) < time" class="hint">未到时间</text></view><view class="checkin-actions"><button :disabled="Boolean(store.medicationOutcome(plan.id, time)) || currentTime.slice(11, 16) < time" :class="{ marked: store.medicationOutcome(plan.id, time) === 'taken' }" :aria-pressed="store.medicationOutcome(plan.id, time) === 'taken'" :aria-label="`${plan.medicineName} ${time} 已服用`" @click="mark(plan.id, time, 'taken')"><QIcon name="check" />{{ store.medicationOutcome(plan.id, time) === 'taken' ? '已记录服用' : '已服用' }}</button><button :disabled="Boolean(store.medicationOutcome(plan.id, time)) || currentTime.slice(11, 16) < time" :class="{ skipped: store.medicationOutcome(plan.id, time) === 'skipped' }" :aria-pressed="store.medicationOutcome(plan.id, time) === 'skipped'" :aria-label="`${plan.medicineName} ${time} 跳过`" @click="mark(plan.id, time, 'skipped')">{{ store.medicationOutcome(plan.id, time) === 'skipped' ? '已记录跳过' : '跳过' }}</button></view></view><text class="hint">如有漏服或不适，请咨询医生或药师，不自行补服或调整剂量。</text></view>
        <text v-else-if="plan.status === 'active'" class="hint">{{ today < plan.startDate ? '尚未到开始日期。' : '计划日期已结束，可将状态标记为已结束。' }}</text>
        <view v-if="plan.status !== 'ended'" class="actions"><button class="secondary" @click="store.setPlanStatus(plan.id, plan.status === 'paused' ? 'active' : 'paused')">{{ plan.status === 'paused' ? '恢复记录计划' : '暂停记录计划' }}</button><button class="text-button" @click="endMedication(plan.id)">结束记录计划</button></view>
      </template>
    </view>
  </view>
</template>

<script lang="ts">
import { reactive } from 'vue'

const planDraft = reactive({
  showForm: false,
  pendingPlanId: '',
  form: { type: 'follow_up' as 'follow_up' | 'medication', healthEpisodeId: '', sourceRecordId: '', title: '', date: '', time: '', goal: '', questions: '', medicineName: '', instructions: '', reminderTimes: '', startDate: '', endDate: '', sourceLabel: '', sourceConfirmed: false },
})
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, toRefs } from 'vue'
import QIcon from '@/components/QIcon.vue'
import { useConsultationStore } from '@/stores/consultation'
import type { FollowUpPlan } from '@/types/consultation'

const store = useConsultationStore()
const emit = defineEmits<{ (event: 'open-conversation', conversationId: string): void }>()
const { showForm } = toRefs(planDraft)
const form = planDraft.form
const formError = ref('')
const actionError = ref('')
const tabs = [{ value: 'all', label: '全部计划' }, { value: 'follow_up', label: '随访计划' }, { value: 'medication', label: '用药计划' }] as const
const currentTime = ref(store.now())
const today = computed(() => currentTime.value.slice(0, 10))
let clockTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => { clockTimer = setInterval(() => { currentTime.value = store.now() }, 15000) })
onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })
const filteredPlans = computed(() => store.plans.filter((plan) => store.selectedPlanTab === 'all' || plan.type === store.selectedPlanTab))
const upcomingCount = computed(() => store.plans.filter((plan) => plan.type === 'follow_up' && ['scheduled', 'in_progress'].includes(plan.status)).length)
const activeMedicationCount = computed(() => store.plans.filter((plan) => plan.type === 'medication' && plan.status === 'active').length)
const hasDraft = computed(() => Boolean(form.healthEpisodeId || form.title || form.goal || form.medicineName || form.instructions))
const episodeOptions = computed(() => ['请选择健康问题', ...store.episodes.map((episode) => episode.title)])
const episodeIndex = computed(() => store.episodes.findIndex((episode) => episode.id === form.healthEpisodeId) + 1)
const sourceRecords = computed(() => store.records.filter((record) => record.healthEpisodeId === form.healthEpisodeId && (form.type !== 'medication' || record.source === 'medical_document')))
const sourceOptions = computed(() => [form.type === 'medication' ? '本人确认的个体化医生医嘱' : '自行安排的随访', ...sourceRecords.value.map((record) => record.title)])
const sourceIndex = computed(() => sourceRecords.value.findIndex((record) => record.id === form.sourceRecordId) + 1)

function changeEpisode(event: { detail: { value: string | number } }) {
  form.healthEpisodeId = store.episodes[Number(event.detail.value) - 1]?.id || ''
  form.sourceRecordId = ''
}
function changeSource(event: { detail: { value: string | number } }) { form.sourceRecordId = sourceRecords.value[Number(event.detail.value) - 1]?.id || '' }
function episodeTitle(id: string) { return store.episodes.find((episode) => episode.id === id)?.title || '健康问题' }
function sourceTitle(id?: string) { return store.records.find((record) => record.id === id)?.title || '用户自行安排' }
function statusLabel(status: string) { return ({ scheduled: '待随访', in_progress: '随访中', completed: '已完成', paused: '已暂停', cancelled: '已取消', active: '进行中', ended: '已结束' } as Record<string, string>)[status] || status }

function savePlan() {
  formError.value = ''
  if (planDraft.pendingPlanId) {
    if (!store.persist()) { formError.value = store.error; return }
    finishPlan()
    return
  }
  if (!form.healthEpisodeId) { formError.value = '请先选择关联的健康问题。'; return }
  const sourceRecordId = sourceRecords.value.some((record) => record.id === form.sourceRecordId) ? form.sourceRecordId : undefined
  if (form.type === 'follow_up') {
    if (!form.title.trim() || !form.date || !form.time || !form.goal.trim() || !form.questions.trim()) { formError.value = '请填写随访标题、日期、时间、目标和至少一个问题。'; return }
    const scheduledAt = `${form.date} ${form.time}`
    if (`${scheduledAt}:00` <= store.now()) { formError.value = '请选择将来的随访时间（北京时间）。'; return }
    const plan = store.createFollowUpPlan({ healthEpisodeId: form.healthEpisodeId, sourceRecordId, title: form.title, scheduledAt, goal: form.goal, questions: form.questions.split('\n').map((question) => question.trim()).filter(Boolean) })
    if (!plan) { formError.value = store.error || '创建失败，请检查填写并重试，当前内容已保留。'; return }
    if (store.error) { planDraft.pendingPlanId = plan.id; formError.value = store.error; return }
  } else {
    const times = [...new Set(form.reminderTimes.split(/[,，]/).map((time) => time.trim()).filter(Boolean))].sort()
    if (!form.medicineName.trim() || !form.instructions.trim() || !form.sourceLabel.trim() || !form.startDate || !form.endDate) { formError.value = '请填写药品、本人用法用量、医嘱来源和起止日期。'; return }
    if (!times.length || times.some((time) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) { formError.value = '请按 HH:mm 填写每日时间，例如 08:00, 20:00。'; return }
    if (form.endDate < form.startDate) { formError.value = '结束日期不能早于开始日期。'; return }
    if (form.endDate < today.value) { formError.value = '请填写目前仍在执行的有效医嘱日期。'; return }
    if (!form.sourceConfirmed) { formError.value = '请先确认这是本人当前仍在执行、已核对的个体化医嘱。'; return }
    const plan = store.createMedicationPlan({ healthEpisodeId: form.healthEpisodeId, sourceRecordId, medicineName: form.medicineName, instructions: form.instructions, reminderTimes: times, startDate: form.startDate, endDate: form.endDate, sourceLabel: form.sourceLabel, sourceConfirmed: form.sourceConfirmed })
    if (!plan) { formError.value = store.error || '创建失败，请检查医嘱来源和填写内容后重试。当前内容已保留。'; return }
    if (store.error) { planDraft.pendingPlanId = plan.id; formError.value = store.error; return }
  }
  finishPlan()
}
function finishPlan() {
  store.selectedPlanTab = form.type
  if (form.type === 'follow_up') { form.title = ''; form.date = ''; form.time = ''; form.goal = ''; form.questions = '' }
  else { form.medicineName = ''; form.instructions = ''; form.reminderTimes = ''; form.startDate = ''; form.endDate = ''; form.sourceLabel = ''; form.sourceConfirmed = false }
  form.sourceRecordId = ''
  form.healthEpisodeId = ''
  showForm.value = false
  planDraft.pendingPlanId = ''
}
function startFollowUp(id: string) {
  const conversationId = store.startFollowUp(id)
  if (conversationId) { actionError.value = ''; emit('open-conversation', conversationId) }
  else actionError.value = '未能打开随访，请检查计划状态后重试。'
}
function viewFollowUp(plan: FollowUpPlan) {
  const record = store.records.find((item) => item.source === 'ai_follow_up' && item.conversationId === plan.conversationId)
  if (record) { store.openRecord(record); store.openWorkspace('archive') }
  else if (plan.conversationId) emit('open-conversation', plan.conversationId)
  else actionError.value = '这项随访尚未生成归档记录。'
}
function mark(id: string, time: string, outcome: 'taken' | 'skipped') {
  actionError.value = store.markMedication(id, time, outcome) ? '' : '未能记录，请检查计划日期和状态。当前已有记录已保留。'
}
function endMedication(id: string) {
  uni.showModal({ title: '结束这项记录计划？', content: '已记录的服用情况会保留。此操作仅结束记录安排，不代表停药医嘱。', confirmText: '结束记录', success: (result) => { if (result.confirm) store.setPlanStatus(id, 'ended') } })
}
</script>

<style scoped>
.plans-page { width: 100%; max-width: 1160px; margin: 0 auto; padding: 40px 42px; box-sizing: border-box; color: #293653; }
.page-heading, .card-heading, .plan-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-heading { margin-bottom: 24px; }
.eyebrow { display: block; color: #657590; font-size: 12px; font-weight: 700; letter-spacing: 2px; margin-bottom: 10px; }
.page-title { display: block; font-size: 30px; font-weight: 650; line-height: 1.5; }
.description, .source, .hint { display: block; color: #657590; font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; }
.description { margin-top: 5px; }
.notice { display: flex; align-items: flex-start; gap: 10px; border: 1px solid #dbe7f7; border-radius: 14px; background: #edf4ff; color: #4d6283; padding: 15px 18px; font-size: 13px; line-height: 1.8; }
.card { border: 1px solid #dce5f2; border-radius: 18px; padding: 24px; margin-top: 18px; background: #fff; min-width: 0; }
.section-title { display: block; font-size: 18px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.plan-heading { justify-content: flex-start; flex: 1; min-width: 0; }
.plan-heading > view:last-child { min-width: 0; }
.plan-icon { display: flex; justify-content: center; align-items: center; width: 44px; height: 44px; border-radius: 13px; background: #edf4ff; flex-shrink: 0; }
.status { flex-shrink: 0; padding: 5px 9px; border-radius: 6px; background: #eaf4ef; color: #417459; font-size: 12px; line-height: 1.7; }
.status.paused { background: #f3f5f8; color: #657590; }
.schedule { display: flex; gap: 8px; align-items: center; margin-top: 22px; color: #3470be; font-size: 15px; }
.body-text { display: block; margin: 16px 0 8px; font-size: 15px; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; }
.source { margin: 12px 0 18px; }
button { min-height: 44px; box-sizing: border-box; font-size: 14px; line-height: 1.6; }
.primary, .secondary { display: flex; gap: 8px; justify-content: center; align-items: center; margin: 0; border-radius: 10px; padding: 11px 17px; }
.primary { background: #2f70d3; color: #fff; }
.primary :deep(.q-icon) { filter: brightness(0) invert(1); }
.secondary { background: #fff; color: #3470be; border: 1px solid #d3dfef; }
.text-button { margin: 0; padding: 8px 0; color: #3470be; background: transparent; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 18px; }
.tabs, .type-switch { display: flex; gap: 8px; margin-top: 24px; }
.tabs button, .type-switch button { margin: 0; padding: 10px 15px; background: transparent; border-radius: 10px; color: #657590; }
.tabs .active, .type-switch .selected { background: #e6efff; color: #276ac8; font-weight: 600; }
.type-switch { margin: 16px 0 22px; padding-bottom: 15px; border-bottom: 1px solid #e3ebf5; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.full { grid-column: 1 / -1; }
.field { min-width: 0; }
.label { display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600; line-height: 1.6; }
.input, .textarea, .picker-value { width: 100%; box-sizing: border-box; border: 1px solid #d3dfef; border-radius: 10px; background: #fff; color: #293653; font-size: 14px; }
.input { height: 48px; padding: 0 12px; }
.textarea { height: 100px; padding: 12px; line-height: 1.8; }
.picker-value { min-height: 48px; display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 12px; }
.hint { margin-top: 7px; }
.confirmation { display: flex; align-items: flex-start; gap: 10px; margin: 0; padding: 10px 0; background: transparent; color: #4d6283; font-size: 13px; text-align: left; line-height: 1.8; }
.check-box { display: flex; flex-shrink: 0; align-items: center; justify-content: center; width: 22px; height: 22px; margin-top: 2px; border: 1px solid #acbfdb; border-radius: 5px; }
.checked { background: #e1edff; border-color: #347be5; }
.check-box .q-icon { width: 18px; height: 18px; }
.error { display: block; margin-top: 14px; padding: 12px; background: #fff1f0; color: #a13d39; border-radius: 10px; font-size: 14px; line-height: 1.7; }
.today-checkins { padding: 16px; background: #f7faff; border-radius: 12px; margin-top: 16px; }
.checkin { display: flex; justify-content: space-between; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px solid #e3ebf5; }
.time { font-size: 15px; font-weight: 600; }
.checkin-actions { display: flex; gap: 8px; }
.checkin button { display: flex; gap: 5px; align-items: center; margin: 0; padding: 9px 12px; border: 1px solid #d3dfef; background: #fff; color: #657590; border-radius: 8px; font-size: 13px; }
.checkin button[disabled]:not(.marked):not(.skipped) { color: #8290a5; background: #f2f5fa; }
.checkin .marked { color: #367254; background: #eaf4ef; border-color: #a9d0b9; }
.checkin .skipped { color: #87651f; background: #fff6e6; border-color: #e5cd9c; }
.form-note { margin-top: 16px; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 13px; padding: 45px 20px; text-align: center; }
@media (max-width: 760px) { .plans-page { padding: 27px 20px; } .page-heading { flex-wrap: wrap; gap: 18px; } .page-title { font-size: 26px; } .card { padding: 20px 16px; } .card-heading { gap: 10px; } .form-grid { grid-template-columns: minmax(0, 1fr); } .tabs { gap: 3px; } .tabs button { flex: 1; padding: 10px 5px; font-size: 13px; } .plan-heading { gap: 10px; } .plan-icon { width: 36px; height: 36px; } .section-title { font-size: 16px; } .status { font-size: 11px; padding: 5px 7px; } .today-checkins { padding: 12px 10px; } .checkin-actions { gap: 5px; } .checkin button { padding: 9px 7px; font-size: 12px; } .checkin .q-icon { display: none; } .plan-form .actions .primary { flex: 1; } }
</style>
