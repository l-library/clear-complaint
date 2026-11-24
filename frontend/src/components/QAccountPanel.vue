<template>
  <view class="account-panel live-ui">
    <view class="live-row"><text class="account-title">账户信息</text><text class="live-pill">{{ auth.isLoggedIn ? '已登录' : '未登录' }}</text></view>
    <text v-if="auth.user" class="account-phone">{{ auth.user.phone }}</text>
    <view v-if="!auth.isLoggedIn">
      <view class="live-tabs" role="tablist" aria-label="账户操作"><button v-for="item in modes" :key="item.id" role="tab" tabindex="0" @keydown="activateButton" :aria-selected="mode === item.id" :class="{ active: mode === item.id }" @click="mode = item.id">{{ item.title }}</button></view>
      <label class="live-label" for="account-phone">手机号</label><input id="account-phone" v-model="phone" class="live-input" type="number" maxlength="11" placeholder="11 位手机号" />
      <label class="live-label password-label" for="account-password">密码</label><input id="account-password" v-model="password" class="live-input" password maxlength="32" placeholder="8–32 位，包含字母与数字" />
      <view v-if="mode === 'register'">
        <checkbox-group @change="privacyAccepted = $event.detail.value.includes('privacy')"><label class="live-check"><checkbox value="privacy" :checked="privacyAccepted" /><text>我已阅读并同意隐私政策</text></label></checkbox-group>
        <checkbox-group @change="sensitiveAccepted = $event.detail.value.includes('sensitive')"><label class="live-check"><checkbox value="sensitive" :checked="sensitiveAccepted" /><text>我同意为健康服务处理我提交的敏感个人信息</text></label></checkbox-group>
        <view class="policy-links"><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="openPolicy(false)">隐私说明</button><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="openPolicy(true)">敏感信息说明</button></view>
        <text v-if="!privacy" class="live-muted">隐私政策未加载，暂不能注册。</text><button v-if="!privacy" role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="loadPrivacy">重新读取隐私政策</button>
      </view>
      <button role="button" tabindex="0" @keydown="activateButton" class="live-primary login-button" :disabled="busy || auth.loading || (mode === 'register' && !privacy)" @click="authenticate">{{ mode === 'login' ? '登录' : '注册账户' }}</button>
    </view>
    <view v-else>
      <text v-if="!workspace.initialized" class="live-notice">尚未读取到账户档案。<button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="workspace.initialize(true)">重新读取</button></text>
      <view class="account-section"><text class="live-subtitle">基础信息</text>
      <view v-if="workspace.patientProfile && !workspace.patientProfile.required_missing.length && !editing" class="account-summary"><text class="live-subtitle">{{ workspace.patientProfile.name || '我的账户' }}</text><text class="live-muted">{{ workspace.patientProfile.age_years ?? '—' }} 岁 · {{ sexIndex >= 0 ? sexLabels[sexIndex] : '未填写性别' }}<text v-if="workspace.patientProfile.city_name"> · {{ workspace.patientProfile.city_name }}</text></text><text class="live-muted">身高 {{ measurements.height_cm || '—' }} cm · 体重 {{ measurements.weight_kg || '—' }} kg</text><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="editing = true">编辑基础信息</button></view>
      <view v-if="editing || !workspace.patientProfile || workspace.patientProfile.required_missing.length" class="live-grid">
        <view class="live-full"><label class="live-label" for="profile-name">称呼</label><input id="profile-name" v-model="form.name" class="live-input" maxlength="40" /></view>
        <view><text class="live-label">出生日期 *</text><picker mode="date" :value="form.birth_date" :end="today" @change="form.birth_date = String($event.detail.value)"><view class="live-select">{{ form.birth_date || '选择日期' }}</view></picker></view>
        <view><text class="live-label">性别 *</text><picker :range="sexLabels" :value="sexIndex" @change="form.sex = sexes[Number($event.detail.value)]"><view class="live-select">{{ sexIndex < 0 ? '请选择' : sexLabels[sexIndex] }}</view></picker></view>
        <QCityPicker class="live-full" :code="form.city_code" :name="form.city_name" @change="form.city_code = $event.code; form.city_name = $event.name" />
        <view class="live-full measurement-grid">
          <view><label class="live-label" for="profile-height">身高（cm）</label><input id="profile-height" v-model="measurements.height_cm" class="live-input" type="digit" :disabled="busy || !measurementsLoaded" placeholder="选填" /></view>
          <view><label class="live-label" for="profile-weight">体重（kg）</label><input id="profile-weight" v-model="measurements.weight_kg" class="live-input" type="digit" :disabled="busy || !measurementsLoaded" placeholder="选填" /></view>
        </view>
        <text class="live-full live-muted">身高和体重留空时保留原记录。</text>
        <view class="live-full"><text class="live-label">既往情况</text><picker :range="factLabels" :value="form.conditionState" @change="form.conditionState = Number($event.detail.value)"><view class="live-select">{{ factLabels[form.conditionState] }}</view></picker><input v-if="form.conditionState === 2" v-model="form.conditions" class="live-input fact-input" aria-label="既往情况，使用逗号分隔" placeholder="使用逗号分隔" /></view>
        <view class="live-full"><text class="live-label">过敏情况</text><picker :range="factLabels" :value="form.allergyState" @change="form.allergyState = Number($event.detail.value)"><view class="live-select">{{ factLabels[form.allergyState] }}</view></picker><input v-if="form.allergyState === 2" v-model="form.allergies" class="live-input fact-input" aria-label="过敏情况，使用逗号分隔" placeholder="使用逗号分隔" /></view>
        <view class="live-full"><label class="live-label" for="condition-note">既往情况备注（选填）</label><textarea id="condition-note" v-model="form.condition_note" class="live-textarea" maxlength="1000" /></view>
        <view class="live-full"><label class="live-label" for="allergy-note">过敏备注（选填）</label><textarea id="allergy-note" v-model="form.allergy_note" class="live-textarea" maxlength="1000" /></view>
      </view>
      <button v-if="editing || !workspace.patientProfile || workspace.patientProfile.required_missing.length" role="button" tabindex="0" @keydown="activateButton" class="live-primary" :disabled="busy || !workspace.initialized" @click="saveProfile">保存基础信息</button>
      <button v-if="!measurementsLoaded" role="button" tabindex="0" @keydown="activateButton" class="live-link" :disabled="busy" @click="loadMeasurements">重新读取身高与体重</button>
      </view>
      <view class="account-section"><text class="live-label">隐私与数据</text><text class="live-muted">{{ consent ? `已同意版本 ${consent.consented_version || '未登记'}${consent.outdated ? ' · 版本已更新' : ''}` : '隐私记录尚未读取' }}</text><button role="button" tabindex="0" @keydown="activateButton" class="live-link" :disabled="busy" @click="exportData">导出全部数据</button>
        <!-- #ifdef H5 -->
        <a v-if="downloadUrl" class="download-link" :href="downloadUrl" target="_blank" rel="noopener noreferrer">下载导出包（一次性链接）</a>
        <!-- #endif -->
        <!-- #ifndef H5 -->
        <button v-if="downloadUrl" class="live-link" @click="copyDownload">复制下载地址</button>
        <!-- #endif -->
      </view>
      <view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-secondary" :disabled="busy" @click="signOut">退出登录</button><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="dangerOpen = !dangerOpen">数据管理</button></view>
      <view v-if="dangerOpen" class="account-section"><text class="live-muted">清空数据和注销均无法恢复。请输入“删除”后继续。</text><input v-model="confirmation" class="live-input" aria-label="输入删除确认操作" placeholder="删除" /><view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-danger" :disabled="busy || confirmation !== '删除'" @click="confirmDestruction(false)">清空健康数据</button><button role="button" tabindex="0" @keydown="activateButton" class="live-danger" :disabled="busy || confirmation !== '删除'" @click="confirmDestruction(true)">注销账户</button></view></view>
    </view>
    <text v-if="error || workspace.error" class="live-error" role="alert">{{ error || workspace.error }}</text><text v-if="notice" class="live-notice" role="status">{{ notice }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import QCityPicker from '@/components/QCityPicker.vue'
import { useProfileDraftStore } from '@/stores/profileDraft'
import { activateButton } from '@/components/buttonKeyboard'
import { useAuthStore } from '@/stores/auth'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'
import { getPrivacyMeta, type PrivacyMeta } from '@/api/meta'
import { updateProfile, type Sex } from '@/api/profile'
import { exportAccountData, clearAccountData, deleteAccount } from '@/api/account'
import { getConsentRecord, saveVital, type ConsentRecord } from '@/api/health'
import { getArchiveOverview } from '@/api/archive'
import { getApiBaseUrl } from '@/request'

const auth = useAuthStore()
const workspace = useLiveWorkspaceStore()
const modes = [{ id: 'login', title: '登录' }, { id: 'register', title: '注册' }]
const mode = ref('login'), phone = ref(''), password = ref('')
const editor = useProfileDraftStore()
const { form, measurements, measurementsLoaded, busy, error, notice, editing } = storeToRefs(editor)
const privacy = ref<PrivacyMeta | null>(null), consent = ref<ConsentRecord | null>(null)
const privacyAccepted = ref(false), sensitiveAccepted = ref(false), dangerOpen = ref(false), confirmation = ref(''), downloadUrl = ref('')
const sexes: Sex[] = ['male', 'female', 'undisclosed'], sexLabels = ['男', '女', '不便透露'], factLabels = ['未告知', '明确没有', '填写已知情况']
const today = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10)
const sexIndex = computed(() => sexes.indexOf(form.value.sex as Sex))
watch(() => workspace.patientProfile, (profile) => editor.hydrate(profile), { immediate: true })
watch(() => auth.user?.id, () => { password.value = ''; consent.value = null; downloadUrl.value = ''; confirmation.value = ''; notice.value = ''; editing.value = false; void loadConsent(); void loadMeasurements() })
async function loadConsent() { const owner = auth.user?.id; if (auth.isLoggedIn) { try { const record = await getConsentRecord(); if (owner === auth.user?.id) consent.value = record } catch (cause) { if (owner === auth.user?.id) error.value = cause instanceof Error ? cause.message : '隐私记录读取失败' } } }
async function loadPrivacy() { if (!editor.dirty) error.value = ''; try { privacy.value = await getPrivacyMeta() } catch (cause) { error.value = cause instanceof Error ? cause.message : '暂时无法连接，请稍后重试' } }
async function loadMeasurements() {
  const owner = auth.user?.id
  if (!auth.isLoggedIn) return
  try {
    const overview = await getArchiveOverview()
    if (owner === auth.user?.id) editor.hydrateMeasurements(overview.vitals)
  } catch { if (owner === auth.user?.id) error.value = '身高与体重读取失败，请重新读取。' }
}
onMounted(async () => { await Promise.all([loadPrivacy(), loadConsent(), loadMeasurements()]) })
async function perform(action: () => Promise<void>) { if (busy.value) return; const owner = auth.user?.id; busy.value = true; error.value = ''; notice.value = ''; try { await action() } catch (cause) { if (owner === auth.user?.id) error.value = cause instanceof Error ? cause.message : '操作失败，请重试。' } finally { if (!owner || owner === auth.user?.id) busy.value = false } }
function authenticate() { void perform(async () => {
  if (!/^\d{11}$/.test(phone.value)) throw new Error('手机号须为 11 位数字。')
  if (mode.value === 'register') {
    if (!privacy.value || !privacyAccepted.value || !sensitiveAccepted.value) throw new Error('请阅读并明确同意两项隐私说明。')
    await auth.register({ phone: phone.value, password: password.value, consent_version: privacy.value.current_version, accept_privacy: true, accept_sensitive: true })
  } else await auth.login(phone.value, password.value)
  password.value = ''; await workspace.initialize(true)
}) }
const facts = (state: number, value: string) => state === 0 ? null : state === 1 ? [] : value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean)
function saveProfile() { void perform(async () => {
  const draft = form.value
  if (!draft.birth_date || !draft.sex) throw new Error('请填写出生日期和性别。')
  if ((draft.conditionState === 2 && !draft.conditions.trim()) || (draft.allergyState === 2 && !draft.allergies.trim())) throw new Error('请填写已知情况，或选择未告知／明确没有。')
  const body = { ...measurements.value }
  const changes: Array<{ key: 'height_cm' | 'weight_kg'; value: number; submitted: string }> = []
  for (const key of ['height_cm', 'weight_kg'] as const) {
    const text = body[key].trim()
    if (!text) continue
    const value = Number(text), min = key === 'height_cm' ? 50 : 2, max = key === 'height_cm' ? 250 : 300
    if (!/^\d+(?:\.\d+)?$/.test(text) || !Number.isFinite(value) || value < min || value > max) throw new Error(key === 'height_cm' ? '身高请填写 50–250 cm。' : '体重请填写 2–300 kg。')
    if (value !== Number(editor.savedMeasurements[key])) changes.push({ key, value, submitted: body[key] })
  }
  if (changes.length && !measurementsLoaded.value) throw new Error('请先重新读取身高与体重。')
  const owner = auth.user?.id
  const submitted = JSON.stringify(draft)
  const profile = await updateProfile({ name: draft.name, birth_date: draft.birth_date, sex: draft.sex, city_code: draft.city_code || null, city_name: draft.city_name || null, conditions: facts(draft.conditionState, draft.conditions), allergies: facts(draft.allergyState, draft.allergies), condition_note: draft.condition_note, allergy_note: draft.allergy_note })
  if (owner !== auth.user?.id) return
  workspace.patientProfile = profile
  editor.accept(profile, submitted)
  auth.updateProfileComplete(workspace.patientProfile.required_missing.length === 0)
  try {
    for (const change of changes) {
      if (owner !== auth.user?.id) return
      const record = await saveVital({ measured_at: new Date().toISOString(), ...(change.key === 'height_cm' ? { kind: 'height', height_cm: change.value } : { kind: 'weight', weight_kg: change.value }) })
      if (owner !== auth.user?.id) return
      const value = record[change.key]
      if (value == null || !Number.isFinite(value)) throw new Error('保存结果不完整。')
      editor.acceptMeasurement(change.key, value, change.submitted)
    }
  } catch { throw new Error('基础资料已保存，身高和体重尚未全部保存。未保存的内容已保留，请重试。') }
  for (const key of ['height_cm', 'weight_kg'] as const) {
    if (measurements.value[key] === body[key]) measurements.value[key] = editor.savedMeasurements[key]
  }
  editing.value = editor.dirty
  notice.value = editor.dirty ? '已保存，当前还有未保存的修改。' : '基础信息已保存。'; workspace.error = ''
}) }
function exportData() { void perform(async () => { const owner = auth.user?.id; const result = await exportAccountData(); if (owner !== auth.user?.id) return; if (!result.url.startsWith('/api/export/')) throw new Error('导出地址格式不正确。'); downloadUrl.value = result.url; notice.value = `有效期至 ${result.expires_at}` }) }
function openPolicy(sensitive: boolean) { uni.navigateTo({ url: `/pages/privacy/index?section=${sensitive ? 'sensitive' : 'privacy'}` }) }
function copyDownload() { const base = getApiBaseUrl().replace(/\/api\/?$/, ''); uni.setClipboardData({ data: `${base}${downloadUrl.value}` }) }
function signOut() { void perform(async () => { await auth.logout(); notice.value = '已退出登录。' }) }
function confirmDestruction(removeAccount: boolean) {
  if (confirmation.value !== '删除') return
  uni.showModal({ title: removeAccount ? '永久注销账户？' : '永久清空健康数据？', content: '此操作会删除账户中的相关数据，无法恢复。', confirmText: '确认删除', success: (answer) => { if (answer.confirm) void perform(async () => { if (removeAccount) { await deleteAccount(); auth.clearLocalSession() } else { await clearAccountData(); editor.reset(); busy.value = true; workspace.reset(); await workspace.initialize(true); await loadMeasurements() } confirmation.value = ''; dangerOpen.value = false; notice.value = '操作已完成。' }) } })
}
</script>

<style scoped>
.account-panel { padding: clamp(22px, 1.3vw, 36px); }
.account-title { font-size: 19px; font-weight: 500; color: #4e5d53; }
.account-phone { display: block; margin: 18px 0; font-size: 20px; letter-spacing: .4px; }
.account-panel .live-input, .account-panel .live-select { background: rgba(255,255,255,.5); border-color: rgba(194,206,195,.65); }
.account-panel .live-grid { gap: 13px; }
.account-panel .live-tabs { margin: 20px 0; }
.account-panel .live-tabs .active { color: #35483c; background: rgba(255,255,255,.65); box-shadow: inset 0 1px 0 #fff; }
.password-label { margin-top: 15px; }
.login-button { width: 100%; margin-top: 22px !important; }
.account-section { margin-top: 25px; padding-top: 20px; border-top: 1px solid var(--glass-rule, #deded7); }
.account-summary { margin-top: 20px; }
.measurement-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
.fact-input { margin-top: 9px; }
.policy-links { display: flex; gap: 14px; font-size: 12px; }
.policy-links a, .download-link { color: #2463eb; text-decoration: none; }
.download-link { display: block; margin-top: 10px; font-size: 12px; }
@media (max-width: 1100px) { .account-panel .live-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
