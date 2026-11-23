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
        <!-- #ifdef H5 -->
        <view v-if="privacy" class="policy-links"><a :href="privacy.policy_url" target="_blank" rel="noopener noreferrer">隐私政策</a><a :href="privacy.sensitive_policy_url" target="_blank" rel="noopener noreferrer">敏感信息说明</a></view>
        <!-- #endif -->
        <!-- #ifndef H5 -->
        <view v-if="privacy" class="live-actions"><button class="live-link" @click="copyPolicy(false)">复制隐私政策地址</button><button class="live-link" @click="copyPolicy(true)">复制敏感信息说明地址</button></view>
        <!-- #endif -->
        <text v-if="!privacy" class="live-muted">隐私政策未加载，暂不能注册。</text><button v-if="!privacy" role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="loadPrivacy">重新读取隐私政策</button>
      </view>
      <button role="button" tabindex="0" @keydown="activateButton" class="live-primary login-button" :disabled="busy || auth.loading || (mode === 'register' && !privacy)" @click="authenticate">{{ mode === 'login' ? '登录' : '注册账户' }}</button>
    </view>
    <view v-else>
      <text v-if="!workspace.initialized" class="live-notice">尚未读取到账户档案。<button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="workspace.initialize(true)">重新读取</button></text>
      <view v-if="workspace.patientProfile && !workspace.patientProfile.required_missing.length && !editing" class="account-summary"><text class="live-subtitle">{{ workspace.patientProfile.name || '我的账户' }}</text><text class="live-muted">{{ workspace.patientProfile.age_years ?? '—' }} 岁 · {{ sexIndex >= 0 ? sexLabels[sexIndex] : '未填写性别' }}<text v-if="workspace.patientProfile.city_name"> · {{ workspace.patientProfile.city_name }}</text></text><button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="editing = true">编辑账户档案</button></view>
      <view v-if="editing || !workspace.patientProfile || workspace.patientProfile.required_missing.length" class="live-grid">
        <view class="live-full"><label class="live-label" for="profile-name">称呼</label><input id="profile-name" v-model="form.name" class="live-input" maxlength="40" /></view>
        <view><text class="live-label">出生日期 *</text><picker mode="date" :value="form.birth_date" :end="today" @change="form.birth_date = String($event.detail.value)"><view class="live-select">{{ form.birth_date || '选择日期' }}</view></picker></view>
        <view><text class="live-label">性别 *</text><picker :range="sexLabels" :value="sexIndex" @change="form.sex = sexes[Number($event.detail.value)]"><view class="live-select">{{ sexIndex < 0 ? '请选择' : sexLabels[sexIndex] }}</view></picker></view>
        <view><label class="live-label" for="city-code">城市代码</label><input id="city-code" v-model="form.city_code" class="live-input" maxlength="20" placeholder="如 110100" /></view>
        <view><label class="live-label" for="city-name">城市名称</label><input id="city-name" v-model="form.city_name" class="live-input" maxlength="40" /></view>
        <view class="live-full"><text class="live-label">既往情况</text><picker :range="factLabels" :value="form.conditionState" @change="form.conditionState = Number($event.detail.value)"><view class="live-select">{{ factLabels[form.conditionState] }}</view></picker><input v-if="form.conditionState === 2" v-model="form.conditions" class="live-input fact-input" aria-label="既往情况，使用逗号分隔" placeholder="使用逗号分隔" /></view>
        <view class="live-full"><text class="live-label">过敏情况</text><picker :range="factLabels" :value="form.allergyState" @change="form.allergyState = Number($event.detail.value)"><view class="live-select">{{ factLabels[form.allergyState] }}</view></picker><input v-if="form.allergyState === 2" v-model="form.allergies" class="live-input fact-input" aria-label="过敏情况，使用逗号分隔" placeholder="使用逗号分隔" /></view>
        <view class="live-full"><label class="live-label" for="condition-note">既往情况备注（选填）</label><textarea id="condition-note" v-model="form.condition_note" class="live-textarea" maxlength="1000" /></view>
        <view class="live-full"><label class="live-label" for="allergy-note">过敏备注（选填）</label><textarea id="allergy-note" v-model="form.allergy_note" class="live-textarea" maxlength="1000" /></view>
      </view>
      <button v-if="editing || !workspace.patientProfile || workspace.patientProfile.required_missing.length" role="button" tabindex="0" @keydown="activateButton" class="live-primary" :disabled="busy || !workspace.initialized" @click="saveProfile">保存账户档案</button>
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { activateButton } from '@/components/buttonKeyboard'
import { useAuthStore } from '@/stores/auth'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'
import { getPrivacyMeta, type PrivacyMeta } from '@/api/meta'
import { updateProfile, type Sex } from '@/api/profile'
import { exportAccountData, clearAccountData, deleteAccount } from '@/api/account'
import { getConsentRecord, type ConsentRecord } from '@/api/health'
import { getApiBaseUrl } from '@/request'

const auth = useAuthStore()
const workspace = useLiveWorkspaceStore()
const modes = [{ id: 'login', title: '登录' }, { id: 'register', title: '注册' }]
const mode = ref('login'), phone = ref(''), password = ref(''), busy = ref(false), error = ref(''), notice = ref('')
const privacy = ref<PrivacyMeta | null>(null), consent = ref<ConsentRecord | null>(null)
const privacyAccepted = ref(false), sensitiveAccepted = ref(false), dangerOpen = ref(false), confirmation = ref(''), downloadUrl = ref('')
const editing = ref(false)
const sexes: Sex[] = ['male', 'female', 'undisclosed'], sexLabels = ['男', '女', '不便透露'], factLabels = ['未告知', '明确没有', '填写已知情况']
const today = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10)
const form = reactive({ name: '', birth_date: '', sex: '' as Sex | '', city_code: '', city_name: '', conditions: '', allergies: '', condition_note: '', allergy_note: '', conditionState: 0, allergyState: 0 })
const sexIndex = computed(() => sexes.indexOf(form.sex as Sex))
watch(() => workspace.patientProfile, (profile) => {
  Object.assign(form, { name: profile?.name || '', birth_date: profile?.birth_date || '', sex: profile?.sex || '', city_code: profile?.city_code || '', city_name: profile?.city_name || '', conditions: profile?.conditions?.join('、') || '', allergies: profile?.allergies?.join('、') || '', condition_note: profile?.condition_note || '', allergy_note: profile?.allergy_note || '', conditionState: profile?.conditions == null ? 0 : profile.conditions.length ? 2 : 1, allergyState: profile?.allergies == null ? 0 : profile.allergies.length ? 2 : 1 })
}, { immediate: true })
watch(() => auth.user?.id, () => { password.value = ''; consent.value = null; downloadUrl.value = ''; confirmation.value = ''; notice.value = ''; editing.value = false; void loadConsent() })
async function loadConsent() { const owner = auth.user?.id; if (auth.isLoggedIn) { try { const record = await getConsentRecord(); if (owner === auth.user?.id) consent.value = record } catch (cause) { if (owner === auth.user?.id) error.value = cause instanceof Error ? cause.message : '隐私记录读取失败' } } }
async function loadPrivacy() { error.value = ''; try { privacy.value = await getPrivacyMeta() } catch (cause) { error.value = cause instanceof Error ? cause.message : '后端连接失败' } }
onMounted(async () => { await loadPrivacy(); await loadConsent() })
async function perform(action: () => Promise<void>) { if (busy.value) return; busy.value = true; error.value = ''; notice.value = ''; try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : '操作失败，请重试。' } finally { busy.value = false } }
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
  if (!form.birth_date || !form.sex) throw new Error('请填写出生日期和性别。')
  if ((form.conditionState === 2 && !form.conditions.trim()) || (form.allergyState === 2 && !form.allergies.trim())) throw new Error('请填写已知情况，或选择未告知／明确没有。')
  const owner = auth.user?.id
  const profile = await updateProfile({ name: form.name, birth_date: form.birth_date, sex: form.sex, city_code: form.city_code, city_name: form.city_name, conditions: facts(form.conditionState, form.conditions), allergies: facts(form.allergyState, form.allergies), condition_note: form.condition_note, allergy_note: form.allergy_note })
  if (owner !== auth.user?.id) return
  workspace.patientProfile = profile
  auth.updateProfileComplete(workspace.patientProfile.required_missing.length === 0); notice.value = '账户档案已保存。'; workspace.error = ''; editing.value = false
}) }
function exportData() { void perform(async () => { const owner = auth.user?.id; const result = await exportAccountData(); if (owner !== auth.user?.id) return; if (!result.url.startsWith('/api/export/')) throw new Error('导出地址格式不正确。'); downloadUrl.value = result.url; notice.value = `有效期至 ${result.expires_at}` }) }
function copyPolicy(sensitive: boolean) { const url = sensitive ? privacy.value?.sensitive_policy_url : privacy.value?.policy_url; if (url) uni.setClipboardData({ data: url }) }
function copyDownload() { const base = getApiBaseUrl().replace(/\/api\/?$/, ''); uni.setClipboardData({ data: `${base}${downloadUrl.value}` }) }
function signOut() { void perform(async () => { await auth.logout(); notice.value = '已退出登录。' }) }
function confirmDestruction(removeAccount: boolean) {
  if (confirmation.value !== '删除') return
  uni.showModal({ title: removeAccount ? '永久注销账户？' : '永久清空健康数据？', content: '此操作会删除服务器中的相关数据，无法恢复。', confirmText: '确认删除', success: (answer) => { if (answer.confirm) void perform(async () => { if (removeAccount) { await deleteAccount(); auth.clearLocalSession() } else { await clearAccountData(); workspace.reset(); await workspace.initialize(true) } confirmation.value = ''; dangerOpen.value = false; notice.value = '操作已完成。' }) } })
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
.fact-input { margin-top: 9px; }
.policy-links { display: flex; gap: 14px; font-size: 12px; }
.policy-links a, .download-link { color: #2463eb; text-decoration: none; }
.download-link { display: block; margin-top: 10px; font-size: 12px; }
@media (max-width: 1100px) { .account-panel .live-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
