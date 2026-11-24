<template>
  <view class="live-page live-ui">
    <view class="live-heading"><view><text class="live-eyebrow">清诉 · 档案</text><text class="live-title">健康档案</text></view><button role="button" tabindex="0" @keydown="activateButton" class="live-secondary" :disabled="loading" @click="load">刷新记录</button></view>
    <view v-if="!auth.isLoggedIn" class="live-card live-blank"><QIcon name="file" /><text>登录后查看自己的健康记录</text><button role="button" tabindex="0" @keydown="activateButton" class="live-primary" @click="workspace.accountOpen = true">登录账户</button></view>
    <template v-else>
      <view class="live-card"><view class="live-row"><text class="live-subtitle">{{ workspace.profile.name }}</text></view><view v-if="overview" class="overview-grid"><view><text class="live-muted">身高 / 体重</text><text>{{ overview.vitals.latest_height_cm ?? '—' }} cm / {{ overview.vitals.latest_weight_kg ?? '—' }} kg</text></view><view><text class="live-muted">最近血压</text><text>{{ overview.vitals.latest_bp ? `${overview.vitals.latest_bp.systolic}/${overview.vitals.latest_bp.diastolic} mmHg` : '暂无记录' }}</text></view><view><text class="live-muted">BMI</text><text>{{ overview.vitals.bmi ?? '—' }}</text></view><view><text class="live-muted">近 90 天问诊</text><text>{{ overview.trend_summary.episodes_90d }}</text></view></view></view>
      <view class="live-tabs" role="tablist" aria-label="档案类型"><button v-for="tab in tabs" :key="tab.id" role="tab" tabindex="0" @keydown="activateButton" :aria-selected="active === tab.id" :class="{ active: active === tab.id }" @click="active = tab.id">{{ tab.title }}</button></view>
      <text v-if="error" class="live-error" role="alert">{{ error }}</text><text v-if="loading" class="live-muted" role="status">正在读取健康记录…</text>
      <view v-if="active === 'episodes'" class="live-card">
        <view class="record-filters" aria-label="问诊筛选">
          <view><text class="live-label">问诊状态</text><picker :range="episodeStatusLabels" :value="episodeStatusIndex" @change="episodeStatusIndex = Number($event.detail.value); load()"><view class="live-select">{{ episodeStatusLabels[episodeStatusIndex] }}</view></picker></view>
          <view><text class="live-label">就医建议</text><picker :range="triageLabels" :value="triageIndex" @change="triageIndex = Number($event.detail.value); load()"><view class="live-select">{{ triageLabels[triageIndex] }}</view></picker></view>
        </view>
        <text v-if="!episodes.length && !loading" class="live-muted">暂无问诊记录。</text>
        <view v-for="record in episodes" :key="record.id" class="live-list-row"><view class="live-row"><view><text class="live-preserve">{{ record.complaint_excerpt }}</text><text class="live-muted">{{ record.created_at }} · {{ record.saved_at ? '已归档' : '未归档' }}<text v-if="record.triage_label"> · {{ record.triage_label }}</text></text></view><text class="live-pill">{{ statusLabel(record.status) }}</text></view><view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="$emit('open-conversation', String(record.id))">查看问诊与依据</button><button role="button" tabindex="0" @keydown="activateButton" class="live-link" :disabled="busy" @click="remove('episode', record.id)">删除记录</button></view></view>
        <button v-if="episodes.length < episodeTotal" role="button" tabindex="0" @keydown="activateButton" class="live-secondary" :disabled="loading" @click="moreEpisodes">加载更多</button>
        <text class="live-muted import-note">病历上传 / OCR · 待接入</text>
      </view>
      <template v-if="active === 'vitals'">
        <view class="live-row"><text class="live-subtitle">体征记录</text><button role="button" tabindex="0" @keydown="activateButton" class="live-primary" @click="newVital()">添加体征</button></view>
        <view class="record-filters"><view><text class="live-label">体征类型</text><picker :range="vitalFilterLabels" :value="vitalFilterIndex" @change="vitalFilterIndex = Number($event.detail.value); load()"><view class="live-select">{{ vitalFilterLabels[vitalFilterIndex] }}</view></picker></view></view>
        <view v-if="vitalOpen" id="vital-editor" class="live-card"><text class="live-subtitle">{{ vitalId ? '编辑体征' : '添加体征' }}</text><view class="live-grid"><view><text class="live-label">类型</text><picker :range="vitalLabels" :value="vital.kind" :disabled="Boolean(vitalId)" @change="vital.kind = Number($event.detail.value)"><view class="live-select">{{ vitalLabels[vital.kind] }}</view></picker></view><view><text class="live-label">测量日期</text><picker mode="date" :value="vital.date" @change="vital.date = String($event.detail.value)"><view class="live-select">{{ vital.date }}</view></picker></view><view><text class="live-label">测量时间</text><picker mode="time" :value="vital.time" @change="vital.time = String($event.detail.value)"><view class="live-select">{{ vital.time }}</view></picker></view><template v-if="vital.kind === 0"><view><label class="live-label" for="systolic">收缩压（mmHg）</label><input id="systolic" v-model="vital.systolic" class="live-input" type="number" /></view><view><label class="live-label" for="diastolic">舒张压（mmHg）</label><input id="diastolic" v-model="vital.diastolic" class="live-input" type="number" /></view><view><label class="live-label" for="pulse">脉搏（选填）</label><input id="pulse" v-model="vital.pulse" class="live-input" type="number" /></view></template><view v-else><label class="live-label" for="vital-value">{{ vital.kind === 1 ? '身高（cm）' : '体重（kg）' }}</label><input id="vital-value" v-model="vital.value" class="live-input" type="digit" /></view></view><view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-primary" :disabled="busy" @click="submitVital">保存体征</button><button role="button" tabindex="0" @keydown="activateButton" class="live-secondary" @click="vitalOpen = false">取消</button></view></view>
        <view class="live-card"><text v-if="!vitals.length && !loading" class="live-muted">暂无体征记录。</text><view v-for="item in vitals" :key="item.id" class="live-list-row"><view class="live-row"><view><text>{{ vitalText(item) }}</text><text class="live-muted">{{ item.measured_at }}</text></view><view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="editVital(item)">编辑</button><button role="button" tabindex="0" @keydown="activateButton" class="live-link" :disabled="busy" @click="remove('vital', item.id)">删除</button></view></view></view><button v-if="vitals.length < vitalTotal" role="button" tabindex="0" @keydown="activateButton" class="live-secondary" :disabled="loading" @click="moreVitals">加载更多</button></view>
      </template>
      <template v-if="active === 'medications'">
        <view class="live-row"><text class="live-subtitle">已有用药记录</text><button role="button" tabindex="0" @keydown="activateButton" class="live-primary" @click="newMedication">添加用药记录</button></view>
        <view class="record-filters" aria-label="用药记录筛选">
          <view><text class="live-label">用药类型</text><picker :range="medicationKindLabels" :value="medicationKindIndex" @change="medicationKindIndex = Number($event.detail.value); load()"><view class="live-select">{{ medicationKindLabels[medicationKindIndex] }}</view></picker></view>
          <view><text class="live-label">记录状态</text><picker :range="medicationStatusLabels" :value="medicationStatusIndex" @change="medicationStatusIndex = Number($event.detail.value); load()"><view class="live-select">{{ medicationStatusLabels[medicationStatusIndex] }}</view></picker></view>
        </view>
        <view v-if="medicationOpen" class="live-card"><text class="live-muted">仅录入本人已有医嘱或实际用药记录。</text><view class="live-grid"><view class="live-full"><label class="live-label" for="medicine-name">药品名称 *</label><input id="medicine-name" v-model="medication.name" class="live-input" maxlength="40" /></view><view><label class="live-label" for="medicine-dosage">已有剂量描述（选填）</label><input id="medicine-dosage" v-model="medication.dosage_text" class="live-input" maxlength="40" /></view><view><label class="live-label" for="medicine-frequency">已有频次描述（选填）</label><input id="medicine-frequency" v-model="medication.frequency_text" class="live-input" maxlength="40" /></view><view><text class="live-label">用药类型</text><picker :range="['长期', '短期']" :value="medication.kind" :disabled="Boolean(medicationId)" @change="medication.kind = Number($event.detail.value)"><view class="live-select">{{ medication.kind ? '短期' : '长期' }}</view></picker></view><view><text class="live-label">开始日期</text><picker mode="date" :value="medication.started_on" :disabled="Boolean(medicationId)" @change="medication.started_on = String($event.detail.value)"><view class="live-select">{{ medication.started_on }}</view></picker></view><view><text class="live-label">结束日期（选填）</text><picker mode="date" :value="medication.ended_on" @change="medication.ended_on = String($event.detail.value)"><view class="live-select">{{ medication.ended_on || '未填写' }}</view></picker><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="medication.ended_on = ''">清除结束日期</button></view></view><view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-primary" :disabled="busy" @click="submitMedication">保存记录</button><button role="button" tabindex="0" @keydown="activateButton" class="live-secondary" @click="medicationOpen = false">取消</button></view></view>
        <view class="live-card"><text v-if="!medications.length && !loading" class="live-muted">暂无用药记录。</text><view v-for="item in medications" :key="item.id" class="live-list-row"><view class="live-row"><view><text>{{ item.name }}</text><text class="live-muted">{{ item.dosage_text || '未填写剂量' }} · {{ item.frequency_text || '未填写频次' }}</text><text class="live-muted">{{ item.started_on }} 至 {{ item.ended_on || '未设结束日期' }}</text></view><text class="live-pill">{{ item.status === 'active' ? '当前记录' : item.status === 'stopped' ? '已标记停用' : '已到期' }}</text></view><view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="editMedication(item)">编辑</button><button v-if="item.status === 'active'" role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="stopMedication(item)">标记记录为停用</button><button v-if="item.status === 'stopped'" role="button" tabindex="0" @keydown="activateButton" class="live-link" :disabled="busy" @click="restoreMedication(item)">恢复为当前记录</button><button role="button" tabindex="0" @keydown="activateButton" class="live-link" :disabled="busy" @click="remove('medication', item.id)">删除</button></view></view></view>
      </template>
      <view v-if="active === 'trend'" class="live-card">
        <view class="record-filters" aria-label="趋势范围">
          <view><text class="live-label">时间范围</text><picker :range="trendDayLabels" :value="trendDayIndex" @change="trendDayIndex = Number($event.detail.value); load()"><view class="live-select">{{ trendDayLabels[trendDayIndex] }}</view></picker></view>
          <view><text class="live-label">每类记录数量</text><picker :range="trendLimitLabels" :value="trendLimitIndex" @change="trendLimitIndex = Number($event.detail.value); load()"><view class="live-select">{{ trendLimitLabels[trendLimitIndex] }}</view></picker></view>
        </view>
        <template v-if="trend"><text class="live-subtitle">近 {{ trendDays[trendDayIndex] }} 天记录</text><view v-for="(point, index) in trend.bp_points" :key="`bp-${index}`" class="live-list-row live-row"><text>{{ point.at }}</text><text>{{ point.systolic }} / {{ point.diastolic }} mmHg</text></view><view v-for="(point, index) in trend.weight_points" :key="`weight-${index}`" class="live-list-row live-row"><text>{{ point.at }}</text><text>{{ point.weight_kg }} kg</text></view><view v-for="(point, index) in trend.triage_points" :key="`triage-${index}`" class="live-list-row live-row"><text>{{ point.at }}</text><text>{{ triageLabel(point.triage) }}</text></view><text v-if="!trend.bp_points.length && !trend.weight_points.length && !trend.triage_points.length" class="live-muted">此范围内暂无趋势记录。</text><view class="live-tabs"><text v-for="item in trend.symptom_keywords" :key="item.term" class="live-pill">{{ item.term }} · {{ item.count }}</text></view></template>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import QIcon from '@/components/QIcon.vue'
import { activateButton } from '@/components/buttonKeyboard'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'
import { getArchiveOverview, getArchiveTrend, type ArchiveOverview, type ArchiveTrend, type VitalRecord } from '@/api/archive'
import { getMedications, createMedication, updateMedication, type Medication } from '@/api/medications'
import { listVitals, saveVital, deleteVital, deleteMedication } from '@/api/health'
import { deleteEpisode, listEpisodes, type EpisodeSummary } from '@/api/episodes'
defineEmits<{ (e: 'open-conversation', id: string): void }>()
const workspace = useLiveWorkspaceStore(), auth = workspace.auth
const tabs = [{ id: 'episodes', title: '问诊记录' }, { id: 'vitals', title: '体征' }, { id: 'medications', title: '用药记录' }, { id: 'trend', title: '趋势' }]
const active = ref('episodes'), loading = ref(false), busy = ref(false), error = ref('')
const overview = ref<ArchiveOverview | null>(null), trend = ref<ArchiveTrend | null>(null), vitals = ref<VitalRecord[]>([]), medications = ref<Medication[]>([])
const vitalPage = ref(1), vitalTotal = ref(0), vitalOpen = ref(false), vitalId = ref<number | undefined>(), medicationOpen = ref(false), medicationId = ref<number | undefined>()
const episodes = ref<EpisodeSummary[]>([]), episodePage = ref(1), episodeTotal = ref(0)
const episodeStatuses = ['', 'generating', 'clarifying', 'ready', 'saved', 'failed']
const episodeStatusLabels = ['全部状态', '处理中', '待补充', '已生成', '已归档', '待重试']
const triages = ['', 'emergency', 'clinic', 'self_observe'], triageLabels = ['全部建议', '急诊', '门诊', '自我观察']
const vitalFilterLabels = ['全部体征', '血压', '身高', '体重']
const medicationKinds = ['', 'long_term', 'short_term'] as const, medicationKindLabels = ['全部类型', '长期', '短期']
const medicationStatuses = ['', 'active', 'stopped'] as const, medicationStatusLabels = ['全部状态', '当前记录', '已标记停用']
const trendDays = [7, 30, 90, 180, 365], trendDayLabels = trendDays.map((days) => `近 ${days} 天`)
const trendLimits = [10, 20, 50], trendLimitLabels = trendLimits.map((limit) => `最多 ${limit} 条`)
const episodeStatusIndex = ref(0), triageIndex = ref(0), vitalFilterIndex = ref(0), medicationKindIndex = ref(0), medicationStatusIndex = ref(0), trendDayIndex = ref(2), trendLimitIndex = ref(0)
const clock = () => new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 16).split('T')
const vitalLabels = ['血压', '身高', '体重'], kinds = ['bp', 'height', 'weight'] as const
const vital = reactive({ kind: 0, date: clock()[0], time: clock()[1], systolic: '', diastolic: '', pulse: '', value: '' })
const medication = reactive({ name: '', dosage_text: '', frequency_text: '', kind: 0, started_on: clock()[0], ended_on: '' })
let loadVersion = 0
async function load() {
  if (!auth.isLoggedIn) return
  const owner = auth.user?.id, version = ++loadVersion
  loading.value = true; error.value = ''
  episodes.value = []; vitals.value = []; medications.value = []; trend.value = null
  try {
    const [summary, history, values, medicines, trends] = await Promise.all([
      getArchiveOverview(), listEpisodes(episodeStatuses[episodeStatusIndex.value] || undefined, 1, triages[triageIndex.value] || undefined),
      listVitals(1, vitalFilterIndex.value ? kinds[vitalFilterIndex.value - 1] : undefined),
      getMedications(medicationKinds[medicationKindIndex.value] || undefined, medicationStatuses[medicationStatusIndex.value] || undefined),
      getArchiveTrend(trendDays[trendDayIndex.value], trendLimits[trendLimitIndex.value]),
    ])
    if (owner !== auth.user?.id || version !== loadVersion) return
    overview.value = summary; episodes.value = history.records; episodePage.value = 1; episodeTotal.value = history.total
    vitals.value = values.records; vitalTotal.value = values.total; vitalPage.value = 1; medications.value = medicines.records; trend.value = trends
  } catch (cause) { if (owner === auth.user?.id && version === loadVersion) error.value = cause instanceof Error ? cause.message : '读取失败，请重试。' }
  finally { if (version === loadVersion) loading.value = false }
}
async function perform(action: () => Promise<void>) { if (busy.value) return; busy.value = true; error.value = ''; try { await action(); await load() } catch (cause) { error.value = cause instanceof Error ? cause.message : '保存失败，请重试。' } finally { busy.value = false } }
watch(() => auth.user?.id, () => { loadVersion += 1; overview.value = null; trend.value = null; episodes.value = []; episodeTotal.value = 0; vitals.value = []; vitalTotal.value = 0; medications.value = []; vitalOpen.value = false; medicationOpen.value = false; loading.value = false; void load() })
onMounted(() => { if (workspace.activeTab === 'archive') void load() })
watch(() => workspace.activeTab, (tab) => { if (tab === 'archive') void load() })
watch(() => workspace.accountOpen, (open, wasOpen) => { if (wasOpen && !open && workspace.activeTab === 'archive') void load() })
function newVital() { vitalId.value = undefined; Object.assign(vital, { kind: 0, date: clock()[0], time: clock()[1], systolic: '', diastolic: '', pulse: '', value: '' }); vitalOpen.value = true }
function editVital(item: VitalRecord) { vitalId.value = item.id; Object.assign(vital, { kind: kinds.indexOf(item.kind), date: item.measured_at.slice(0, 10), time: item.measured_at.slice(11, 16), systolic: String(item.systolic ?? ''), diastolic: String(item.diastolic ?? ''), pulse: String(item.pulse ?? ''), value: String(item.kind === 'height' ? item.height_cm ?? '' : item.weight_kg ?? '') }); vitalOpen.value = true }
function numeric(value: string) { if (!value.trim() || !Number.isFinite(Number(value))) throw new Error('请输入有效数值。'); return Number(value) }
function submitVital() { void perform(async () => { await saveVital({ kind: kinds[vital.kind], measured_at: `${vital.date} ${vital.time}:00`, ...(vital.kind === 0 ? { systolic: numeric(vital.systolic), diastolic: numeric(vital.diastolic), pulse: vital.pulse ? numeric(vital.pulse) : null } : vital.kind === 1 ? { height_cm: numeric(vital.value) } : { weight_kg: numeric(vital.value) }) }, vitalId.value); vitalOpen.value = false }) }
function newMedication() { medicationId.value = undefined; Object.assign(medication, { name: '', dosage_text: '', frequency_text: '', kind: 0, started_on: clock()[0], ended_on: '' }); medicationOpen.value = true }
function editMedication(item: Medication) { medicationId.value = item.id; Object.assign(medication, { ...item, kind: item.kind === 'short_term' ? 1 : 0, dosage_text: item.dosage_text || '', frequency_text: item.frequency_text || '', ended_on: item.ended_on || '' }); medicationOpen.value = true }
function submitMedication() { void perform(async () => { if (!medication.name.trim()) throw new Error('请填写药品名称。'); const fields = { name: medication.name.trim(), dosage_text: medication.dosage_text, frequency_text: medication.frequency_text, ended_on: medication.ended_on || null }; if (medicationId.value) await updateMedication(medicationId.value, fields); else await createMedication({ ...fields, kind: medication.kind ? 'short_term' : 'long_term', started_on: medication.started_on }); medicationOpen.value = false }) }
function stopMedication(item: Medication) { uni.showModal({ title: '更新用药记录状态？', content: '这只更新本人用药记录，不是停药建议。请按实际已确认的用药情况记录。', success: (answer) => { if (answer.confirm) void perform(async () => { await updateMedication(item.id, { status: 'stopped' }) }) } }) }
function restoreMedication(item: Medication) {
  uni.showModal({ title: '恢复为当前用药记录？', content: '请按本人实际用药情况核对。此操作更新记录状态，之前暂停的提醒计划仍保持暂停。', confirmText: '确认恢复', success: (answer) => { if (answer.confirm) void perform(async () => { await updateMedication(item.id, { status: 'active' }) }) } })
}
function remove(kind: 'episode' | 'vital' | 'medication', id: number) { uni.showModal({ title: '永久删除这条记录？', content: kind === 'medication' ? '关联的用药计划也会删除，无法恢复。' : '记录删除后无法恢复。', confirmText: '删除', success: (answer) => { if (answer.confirm) void perform(async () => { await (kind === 'episode' ? deleteEpisode(id) : kind === 'vital' ? deleteVital(id) : deleteMedication(id)) }) } }) }
async function moreEpisodes() {
  if (loading.value) return
  const owner = auth.user?.id, version = loadVersion, page = episodePage.value + 1
  loading.value = true; error.value = ''
  try { const values = await listEpisodes(episodeStatuses[episodeStatusIndex.value] || undefined, page, triages[triageIndex.value] || undefined); if (owner === auth.user?.id && version === loadVersion) { episodes.value.push(...values.records); episodePage.value = page; episodeTotal.value = values.total } }
  catch (cause) { if (owner === auth.user?.id && version === loadVersion) error.value = cause instanceof Error ? cause.message : '读取失败' }
  finally { if (version === loadVersion) loading.value = false }
}
async function moreVitals() {
  if (loading.value) return
  const owner = auth.user?.id, version = loadVersion, page = vitalPage.value + 1
  loading.value = true; error.value = ''
  try { const values = await listVitals(page, vitalFilterIndex.value ? kinds[vitalFilterIndex.value - 1] : undefined); if (owner === auth.user?.id && version === loadVersion) { vitals.value.push(...values.records); vitalPage.value = page; vitalTotal.value = values.total } }
  catch (cause) { if (owner === auth.user?.id && version === loadVersion) error.value = cause instanceof Error ? cause.message : '读取失败' }
  finally { if (version === loadVersion) loading.value = false }
}
function statusLabel(status: string) { return ({ generating: '处理中', clarifying: '待补充', ready: '已生成', saved: '已归档', failed: '待重试' } as Record<string, string>)[status] || status }
function triageLabel(status: string) { return ({ emergency: '急诊', clinic: '门诊', self_observe: '自我观察' } as Record<string, string>)[status] || status }
function vitalText(item: VitalRecord) { return item.kind === 'bp' ? `血压 ${item.systolic}/${item.diastolic} mmHg${item.pulse ? ` · 脉搏 ${item.pulse}` : ''}` : item.kind === 'height' ? `身高 ${item.height_cm} cm` : `体重 ${item.weight_kg} kg` }
</script>

<style scoped>
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 22px; margin-top: 22px; }
.overview-grid > view { min-width: 0; }
.overview-grid text { display: block; }
.import-note { margin-top: 24px; padding-top: 16px; border-top: 1px solid #ededE8; }
.record-filters { display: flex; flex-wrap: wrap; gap: 14px; margin: 18px 0 24px; }
.record-filters > view { flex: 1 1 180px; max-width: 280px; }
@media (max-width: 760px) { .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; } }
</style>
