<template>
  <view class="live-page live-ui">
    <view class="live-heading">
      <view>
        <text class="live-eyebrow">每天留一点时间，回看自己</text>
        <text class="live-title">{{ heading }}</text>
        <view class="daily-date-switch" role="group" aria-label="选择小结日期">
          <button role="button" tabindex="0" @keydown="activateButton" :class="{ 'daily-date-active': selectedDate === today }" :aria-pressed="selectedDate === today" @click="selectDate(today)">今天</button>
          <button role="button" tabindex="0" @keydown="activateButton" :class="{ 'daily-date-active': selectedDate === yesterday }" :aria-pressed="selectedDate === yesterday" @click="selectDate(yesterday)">昨天</button>
        </view>
        <view v-if="badges.length" class="daily-badges">
          <text v-for="badge in badges" :key="badge.key" class="daily-badge" :class="`daily-badge-${badge.key}`" role="note" :aria-label="badge.description">{{ badge.label }}</text>
        </view>
      </view>
      <button role="button" tabindex="0" @keydown="activateButton" class="live-secondary" :disabled="loading || generating" @click="load">{{ loading ? '正在读取…' : '重新读取' }}</button>
    </view>

    <view v-if="!auth.isLoggedIn" class="live-card live-blank">
      <QIcon name="clock" />
      <text class="daily-empty-title">登录后查看今天的小结</text>
      <text class="live-muted">小结只属于本人账户，登录后才能读取或生成。</text>
      <button role="button" tabindex="0" @keydown="activateButton" class="live-primary" @click="workspace.accountOpen = true">登录账户</button>
    </view>
    <template v-else>
      <text v-if="report?.data_source === 'mock'" class="daily-note">当天步数、睡眠等指标来自模拟手表数据，不是真实设备记录。</text>
      <text v-if="report?.degraded" class="daily-note">本次正文由模板兜底生成，内容照常按板块展示。</text>
      <text v-if="error" class="live-error" role="alert">{{ error }}</text>
      <text v-if="loading" class="live-muted" role="status">正在读取{{ selectedDateLabel }}的小结…</text>

      <view v-if="state === 'ready' && report?.summary" class="live-card">
        <text class="live-muted daily-meta">{{ meta }}</text>
        <text v-if="greeting" class="daily-greeting">{{ greeting }}</text>
        <view v-for="block in blocks" :key="block.key" class="daily-block" role="region" :aria-label="block.title">
          <text class="live-subtitle" role="heading" aria-level="2">{{ block.title }}</text>
          <view v-for="(item, index) in block.items" :key="`${block.key}-${index}`" class="daily-item">
            <text class="daily-bullet" aria-hidden="true">·</text>
            <text class="daily-item-text">{{ item }}</text>
          </view>
        </view>
        <text v-if="closing" class="daily-closing">{{ closing }}</text>
      </view>

      <view v-else-if="emptyState" class="live-card live-blank">
        <QIcon :name="emptyState.icon" />
        <text class="daily-empty-title">{{ emptyState.title }}</text>
        <text class="live-muted">{{ emptyState.detail }}</text>
        <button v-if="emptyState.action" role="button" tabindex="0" @keydown="activateButton" class="live-primary" :disabled="loading || generating" @click="handleAction">{{ actionLabel }}</button>
      </view>
    </template>

    <text class="daily-note daily-disclaimer">{{ limitation }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch, type Ref } from 'vue'
import { activateButton } from '@/components/buttonKeyboard'
import QIcon from '@/components/QIcon.vue'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'
import { generateDailyReport, getDailyReport, type DailyReport } from '@/api/daily'
import { ApiError } from '@/request'

const workspace = useLiveWorkspaceStore(), auth = workspace.auth
// 当天按 Asia/Shanghai 取，和报告日期口径一致（docs/api.md 1.3）
function reportDate(offset = 0) {
  return new Date(Date.now() + 8 * 3600000 + offset * 86400000).toISOString().slice(0, 10)
}
const today = reportDate()
const yesterday = reportDate(-1)
const STANDING_DISCLAIMER = '单日设备变化不能判断疾病好转或恶化，请以自己的感受和医生意见为准。'
const EMPTY_HEADING = '每日小结'
const BLOCKS = [
  { key: 'highlights', title: '今天值得肯定的事' },
  { key: 'health_connections', title: '和你照护目标的联系' },
  { key: 'gentle_reminders', title: '温和提醒' },
  { key: 'tomorrow_actions', title: '明天可以做的小事' },
] as const
// 业务码到本地文案的唯一映射：5002/5003 没有正文，5004 重试无意义，都不照抄 message。
const EMPTY_STATES = {
  missing: { icon: 'clock', title: '今天还没有小结', detail: '小结会把今天的合成手表记录和你此前保存的档案放在一起回看，只在你点按时生成。', action: { kind: 'generate', label: '生成今日小结' } },
  insufficient: { icon: 'info', title: '今天记录不足，先不生成小结', detail: '今天的设备记录太少，写不出有意义的小结。等明天记录多一点再看；身体不舒服请照常就医。', action: null },
  review: { icon: 'info', title: '今天的小结需要人工核实，这不替代急诊处理', detail: '今天的记录里有需要人工确认的信号，所以先不生成活动和明日安排。如有紧急情况，请立即联系当地急救服务。', action: null },
  invalid: { icon: 'info', title: '这次生成没有通过输入校验', detail: '这次内容没有通过检查，重试不会改变结果。可以先看看健康档案里的记录是否完整。', action: null },
  error: { icon: 'info', title: '没能读到今天的小结', detail: '网络或服务暂时不可用，稍后可以点右上角重新读取。', action: null },
} as const

type DailyState = 'idle' | keyof typeof EMPTY_STATES | 'ready'
const state = ref<DailyState>('idle')
const report = ref<DailyReport | null>(null)
const selectedDate = ref(today)
const loading = ref(false)
const generating = ref(false)
const error = ref('')
let loadVersion = 0

const summary = computed(() => report.value?.summary ?? null)
const selectedDateLabel = computed(() => selectedDate.value === yesterday ? '昨天' : '今天')
const heading = computed(() => asText(summary.value?.title) || EMPTY_HEADING)
const greeting = computed(() => asText(summary.value?.greeting))
const closing = computed(() => asText(summary.value?.closing))
// summary 为 null 的行（review_required 本地短路或平台没给正文）也走这条兜底，绝不补写正文。
const limitation = computed(() => asText(summary.value?.limitations) || STANDING_DISCLAIMER)
const meta = computed(() => {
  const value = report.value
  if (!value) return ''
  return [
    value.report_date,
    value.updated_at ? `更新于 ${value.updated_at}` : '',
    value.used_record_ids?.length ? `引用档案记录 ${value.used_record_ids.length} 条` : '',
  ].filter(Boolean).join(' · ')
})
const badges = computed(() => {
  const items: { key: string; label: string; description: string }[] = []
  if (report.value?.data_source === 'mock') items.push({ key: 'mock', label: '模拟数据演示', description: '模拟数据标记：当天的指标由后端合成' })
  if (report.value?.degraded === true) items.push({ key: 'degraded', label: '降级小结', description: '降级标记：本次正文由模板兜底' })
  return items
})
const blocks = computed(() => {
  const value = summary.value
  if (!value || state.value !== 'ready') return []
  return BLOCKS
    .map((block) => ({ key: block.key, title: block.title, items: listOf(value[block.key]) }))
    .filter((block) => block.items.length > 0)
})
const emptyState = computed(() => {
  const current = state.value
  if (current === 'ready' || current === 'idle') return null
  const base = EMPTY_STATES[current]
  const label = selectedDateLabel.value
  return {
    ...base,
    title: base.title.replaceAll('今天', label),
    detail: base.detail.replaceAll('今天', label),
    action: current === 'missing' && selectedDate.value === today ? base.action : null,
  }
})
const actionLabel = computed(() => {
  const action = emptyState.value?.action
  if (!action) return ''
  return action.kind === 'generate' && generating.value ? '正在生成…' : action.label
})

function asText(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}
function listOf(value: unknown) {
  return Array.isArray(value) ? value.map(asText).filter((item) => item !== '') : []
}
function applyReport(value: DailyReport) {
  report.value = value
  // 没有正文就没有可展示的小结：按待人工核实的文案处理，不显示活动与明日安排
  state.value = value.status === 'review_required' || !value.summary ? 'review' : 'ready'
}
function applyError(cause: unknown) {
  report.value = null
  const code = cause instanceof ApiError ? cause.code : 0
  if (code === 5001) state.value = 'missing'
  else if (code === 5002) state.value = 'insufficient'
  else if (code === 5003) state.value = 'review'
  else if (code === 5004) state.value = 'invalid'
  else {
    state.value = 'error'
    error.value = cause instanceof Error ? cause.message : '读取失败，请重试。'
  }
}
async function run(action: () => Promise<DailyReport>, busy: Ref<boolean>) {
  if (!auth.isLoggedIn || busy.value) return
  const owner = auth.user?.id, version = ++loadVersion
  busy.value = true
  error.value = ''
  try {
    const value = await action()
    if (owner !== auth.user?.id || version !== loadVersion) return
    applyReport(value)
  } catch (cause) {
    if (owner !== auth.user?.id || version !== loadVersion) return
    applyError(cause)
  } finally {
    if (version === loadVersion) busy.value = false
  }
}
function load() { return run(() => getDailyReport(selectedDate.value), loading) }
function generate() {
  if (selectedDate.value !== today) return Promise.resolve()
  return run(() => generateDailyReport(today), generating)
}
function selectDate(date: string) {
  if (selectedDate.value === date) return
  selectedDate.value = date
  report.value = null
  state.value = 'idle'
  error.value = ''
  loadVersion += 1
  loading.value = false
  generating.value = false
  void load()
}
function handleAction() {
  const action = emptyState.value?.action
  if (!action) return
  void (action.kind === 'generate' ? generate() : load())
}

onMounted(() => { if (workspace.activeTab === 'daily') void load() })
watch(() => workspace.activeTab, (tab) => { if (tab === 'daily') void load() })
watch(() => auth.user?.id, () => {
  report.value = null
  selectedDate.value = today
  state.value = 'idle'
  error.value = ''
  loadVersion += 1
  loading.value = false
  generating.value = false
  void load()
})
</script>

<style scoped>
.daily-date-switch { display: flex; width: fit-content; margin-top: 12px; padding: 3px; border: 1px solid #deded7; border-radius: 24px; background: #f5f5f0; }
.daily-date-switch button { min-width: 58px; min-height: 44px; margin: 0; padding: 8px 14px; border-radius: 20px; background: transparent; color: #70706a; font-size: 12px; line-height: 1.4; }
.daily-date-switch .daily-date-active { background: #fff; color: #2463eb; box-shadow: 0 1px 3px #1b1b1812; }
.daily-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.daily-badge { padding: 3px 10px; border-radius: 20px; font-size: 11px; line-height: 1.7; }
.daily-badge-mock { border: 1px solid #f0d6cf; background: #fff2ef; color: #a14136; }
.daily-badge-degraded { border: 1px solid #e4e4df; background: #f5f5f0; color: #62625b; }
.daily-note { display: block; margin-top: 10px; color: #70706a; font-size: 12px; line-height: 1.8; }
.daily-meta { margin-bottom: 16px; }
.daily-greeting { display: block; font-size: 15px; line-height: 1.9; }
.daily-block { margin-top: 22px; }
.daily-block .live-subtitle { margin-bottom: 8px; }
.daily-item { display: flex; gap: 8px; padding: 3px 0; }
.daily-bullet { flex-shrink: 0; color: #2463eb; }
.daily-item-text { flex: 1; min-width: 0; color: #454540; font-size: 14px; line-height: 1.9; }
.daily-closing { display: block; margin-top: 22px; color: #454540; font-size: 14px; line-height: 1.9; }
.daily-empty-title { font-size: 16px; font-weight: 500; line-height: 1.6; }
.daily-disclaimer { margin-top: 16px; padding-top: 14px; border-top: 1px dashed #e4e4df; }
@media (max-width: 760px) {
  .daily-date-switch { margin-top: 10px; }
  .daily-block { margin-top: 18px; }
  .daily-item-text { font-size: 13px; }
}
</style>
