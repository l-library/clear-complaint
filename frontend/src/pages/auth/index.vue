<template>
  <view class="auth-page">
    <view class="ambient ambient-one" />
    <view class="ambient ambient-two" />

    <view class="auth-shell">
      <view class="brand-panel">
        <view class="brand">
          <text class="brand-mark">清</text>
          <view>
            <text class="brand-name">清诉</text>
            <text class="brand-en">ClearComplaint</text>
          </view>
        </view>

        <view class="brand-copy">
          <text class="kicker">从模糊症状到就医线索</text>
          <text class="headline">把模糊的不适，<br />整理成清楚的就医线索。</text>
          <text class="description">
            先追问关键信息，再匹配建议科室与可信证据。所有结果均标明“不构成诊断”。
          </text>
        </view>

        <view class="feature-list">
          <view class="feature-item">
            <text class="feature-number">先追问</text>
            <text>信息不足时先追问，不急着下结论</text>
          </view>
          <view class="feature-item">
            <text class="feature-number">有依据</text>
            <text>每条建议都能查看信息来源</text>
          </view>
          <view class="feature-item">
            <text class="feature-number">可回看</text>
            <text>长期保存问诊与健康记录</text>
          </view>
        </view>

        <text class="preview-note">已接入真实登录接口代码；后端不可用时可使用交互预览</text>
      </view>

      <view class="form-panel">
        <view class="tabs">
          <button
            class="tab"
            :class="{ active: mode === 'login' }"
            @click="mode = 'login'"
          >
            登录
          </button>
          <button
            class="tab"
            :class="{ active: mode === 'register' }"
            @click="mode = 'register'"
          >
            注册
          </button>
        </view>

        <view class="form-heading">
          <text class="form-title">{{ mode === 'login' ? '欢迎回来' : '创建健康账户' }}</text>
          <text class="form-subtitle">
            {{ mode === 'login' ? '登录后继续您的健康记录' : '注册后先完成基础档案' }}
          </text>
        </view>

        <view class="field">
          <text class="field-label">手机号</text>
          <input
            v-model="phone"
            class="input"
            type="number"
            maxlength="11"
            placeholder="请输入 11 位手机号"
          />
        </view>

        <view class="field">
          <text class="field-label">密码</text>
          <input
            v-model="password"
            class="input"
            password
            maxlength="32"
            placeholder="8–32 位，需包含字母和数字"
          />
        </view>

        <view v-if="mode === 'register'" class="consent" @click="agreed = !agreed">
          <text class="checkbox" :class="{ checked: agreed }">{{ agreed ? '✓' : '' }}</text>
          <text class="consent-text">我已阅读并同意隐私政策与敏感信息处理规则</text>
        </view>
        <view v-if="mode === 'register' && privacyUrls.privacy" class="policy-links">
          <text @click.stop="openPolicy(privacyUrls.privacy)">查看隐私政策</text>
          <text @click.stop="openPolicy(privacyUrls.sensitive)">敏感信息处理规则</text>
        </view>

        <button class="primary" :loading="auth.loading" @click="submit">
          {{ mode === 'login' ? '登录' : '注册并继续' }}
        </button>

        <view class="divider"><text>或</text></view>

        <button class="secondary" @click="openPreview">免登录体验交互预览</button>

        <text v-if="errorText" class="error-text">{{ errorText }}</text>

        <text class="help-text">
          后端未启动时，可先使用免登录交互预览。正式模式会连接登录、档案与问诊接口。
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getPrivacyMeta } from '@/api/meta'
import { useAuthStore } from '@/stores/auth'

const mode = ref<'login' | 'register'>('login')
const phone = ref('')
const password = ref('')
const agreed = ref(false)
const privacyVersion = ref('')
const privacyUrls = ref({ privacy: '', sensitive: '' })
const errorText = ref('')
const auth = useAuthStore()

onMounted(async () => {
  try {
    const meta = await getPrivacyMeta()
    privacyVersion.value = meta.current_version
    privacyUrls.value = {
      privacy: meta.policy_url,
      sensitive: meta.sensitive_policy_url,
    }
  } catch {
    // The backend may not be running in preview mode.
  }
})

async function submit() {
  errorText.value = ''
  if (!/^1\d{10}$/.test(phone.value)) {
    uni.showToast({ title: '请输入 11 位手机号', icon: 'none' })
    return
  }
  if (!/^(?=.*[A-Za-z])(?=.*\d).{8,32}$/.test(password.value)) {
    uni.showToast({ title: '密码需包含字母和数字', icon: 'none' })
    return
  }
  if (mode.value === 'register' && !agreed.value) {
    uni.showToast({ title: '请先同意隐私规则', icon: 'none' })
    return
  }

  try {
    const complete =
      mode.value === 'login'
        ? await auth.login(phone.value, password.value)
        : await auth.register({
            phone: phone.value,
            password: password.value,
            consent_version: privacyVersion.value,
            accept_privacy: true,
            accept_sensitive: true,
          })
    uni.reLaunch({ url: complete ? '/pages/workspace/index' : '/pages/profile/index' })
  } catch (error) {
    errorText.value =
      error instanceof Error ? error.message : '登录失败，请检查后端是否已经启动'
  }
}

function openPolicy(url: string) {
  if (!url) return
  // #ifdef H5
  window.open(url, '_blank', 'noopener,noreferrer')
  // #endif
  // #ifndef H5
  uni.setClipboardData({ data: url })
  // #endif
}

function openPreview() {
  auth.enterDemo()
  uni.navigateTo({ url: '/pages/workspace/index' })
}
</script>

<style scoped>
/* Mint theme overrides: keep the layout, replace the dark forest palette. */
.auth-page {
  background:
    radial-gradient(circle at 12% 16%, var(--wash-accent-18), transparent 34%),
    radial-gradient(circle at 86% 82%, var(--wash-light-48), transparent 38%),
    var(--palette-eef9f5);
  color: var(--palette-23493e);
}

.ambient-one {
  background: radial-gradient(circle, var(--wash-accent-18), transparent 68%);
}

.ambient-two {
  background: radial-gradient(circle, var(--wash-light-48), transparent 70%);
}

.brand-panel {
  background:
    linear-gradient(145deg, var(--wash-light-42), transparent 48%),
    linear-gradient(135deg, var(--palette-dff5ed), var(--palette-cceee3));
  color: var(--palette-20483d);
}

.brand-mark {
  background: var(--palette-55aa92);
  color: var(--palette-ffffff);
  box-shadow: var(--shadow-brand);
}

.brand-name {
  color: var(--palette-1d463a);
}

.brand-en {
  color: var(--palette-6f9589);
}

.kicker {
  color: var(--palette-328b74);
}

.headline {
  color: var(--palette-193f35);
}

.description {
  color: var(--palette-57796d);
}

.feature-item {
  border-color: var(--border-accent-18);
  background: var(--wash-light-48);
  color: var(--palette-42685c);
  box-shadow: var(--shadow-feature);
}

.feature-number {
  color: var(--palette-2f8d75);
}

.preview-note {
  color: var(--palette-6f9186);
}

.form-panel {
  background: var(--palette-f5fcf9);
}

.tabs {
  background: var(--palette-dcf2ea);
}

.tab {
  color: var(--palette-6d8c81);
}

.tab.active {
  background: var(--palette-ffffff);
  color: var(--palette-2f7f69);
}

.form-title,
.field-label {
  color: var(--palette-23493e);
}

.form-subtitle,
.consent-text,
.help-text {
  color: var(--palette-7c978d);
}

.input {
  border-color: var(--palette-cfe6dd);
  background: var(--palette-ffffff);
}

.checkbox.checked {
  border-color: var(--palette-55aa92);
  background: var(--palette-55aa92);
}

.primary {
  background: var(--palette-4da88f);
  color: var(--palette-ffffff);
  box-shadow: var(--shadow-primary);
}

.secondary {
  border-color: var(--palette-cce6dc);
  background: var(--palette-ffffff);
  color: var(--palette-387663);
}

.divider text {
  background: var(--palette-f5fcf9);
}

@media (max-width: 860px) {
  .brand-panel {
    background:
      linear-gradient(150deg, var(--wash-light-32), transparent 55%),
      var(--palette-d9f2e9);
  }
}

/* Hallmark Dose redesign: a warm clinical ledger, not a marketing hero. */
.auth-page {
  min-height: 100vh;
  padding: var(--space-lg);
  background:
    linear-gradient(var(--color-rule) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-rule) 1px, transparent 1px),
    var(--color-paper);
  background-size: 48px 48px;
  color: var(--color-ink);
}

.ambient {
  display: none;
}

.auth-shell {
  display: grid;
  width: min(1240px, 100%);
  min-height: calc(100vh - 48px);
  margin: 0 auto;
  overflow: clip;
  grid-template-columns: minmax(0, 1.12fr) minmax(400px, 0.88fr);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 24px;
  background: var(--palette-fffdf6);
  box-shadow: var(--shadow-lift);
}

.brand-panel,
.form-panel {
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.brand-panel {
  position: relative;
  padding: 40px 48px;
  justify-content: flex-start;
  border-right: var(--rule-hair) solid var(--color-rule);
  background:
    radial-gradient(circle at 90% 16%, var(--wash-accent-18), transparent 28%),
    var(--palette-fffdf6);
  color: var(--color-ink);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.brand-name,
.brand-en,
.kicker,
.headline,
.description,
.preview-note,
.form-title,
.form-subtitle,
.field-label,
.error-text,
.help-text {
  display: block;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
  box-shadow: none;
}

.brand-name {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 20px;
  letter-spacing: -0.02em;
}

.brand-en {
  margin-top: 0;
  color: var(--color-muted);
  font-family: var(--font-outlier);
  font-size: 11px;
  letter-spacing: 0;
}

.brand-copy {
  max-width: 620px;
  margin: clamp(64px, 10vh, 112px) 0 0;
}

.kicker {
  display: inline-flex;
  min-height: 28px;
  padding: 0 var(--space-xs);
  align-items: center;
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 6px;
  background: var(--color-paper-2);
  color: var(--color-accent-deep);
  font-size: 11px;
  font-weight: 650;
  line-height: 1;
}

.headline {
  max-width: 100%;
  margin-top: var(--space-lg);
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: clamp(42px, 3.6vw, 58px);
  font-weight: 700;
  line-height: 1.06;
  letter-spacing: -0.045em;
  text-wrap: balance;
}

.description {
  max-width: 44ch;
  margin-top: var(--space-lg);
  color: var(--color-ink-2);
  font-size: 16px;
  line-height: 1.7;
}

.feature-list {
  display: grid;
  max-width: none;
  margin-top: auto;
  padding-top: 56px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  border-bottom: var(--rule-hair) solid var(--color-rule);
}

.feature-item {
  display: flex;
  min-height: 108px;
  padding: var(--space-md) var(--space-lg) var(--space-md) 0;
  border: 0;
  border-top: var(--rule-hair) solid var(--color-rule);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  color: var(--color-ink-2);
  font-size: 13px;
  line-height: 1.6;
  flex-direction: column;
  justify-content: space-between;
}

.feature-item + .feature-item {
  padding-left: 20px;
  border-left: var(--rule-hair) solid var(--color-rule);
}

.feature-number {
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
  font-size: 11px;
}

.preview-note {
  margin-top: var(--space-md);
  color: var(--color-muted);
  font-size: 11px;
}

.form-panel {
  padding: 48px clamp(40px, 6vw, 80px);
  justify-content: center;
  background: var(--palette-fffdf7);
}

.tabs {
  display: flex;
  width: fit-content;
  padding: 4px;
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 10px;
  background: var(--color-paper-2);
}

.tab {
  min-width: 76px;
  height: 34px;
  margin: 0;
  border-radius: 7px;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 34px;
}

.tab.active {
  background: var(--palette-fffdf6);
  color: var(--color-ink);
  box-shadow: 0 1px 2px var(--surface-shadow-edge);
}

.form-heading {
  margin-top: clamp(40px, 7vh, 72px);
}

.form-title {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.035em;
}

.form-subtitle {
  margin-top: var(--space-xs);
  color: var(--color-muted);
  font-size: 14px;
}

.field {
  margin-top: var(--space-lg);
}

.field-label {
  margin-bottom: var(--space-xs);
  color: var(--color-ink-2);
  font-size: 12px;
  font-weight: 650;
}

.input {
  height: 50px;
  padding: 0 var(--space-md);
  border: var(--rule-hair) solid var(--color-muted);
  border-radius: 9px;
  background: var(--surface-input);
  color: var(--color-ink);
  font-size: 15px;
}

.input::placeholder,
.input :deep(.uni-input-placeholder) {
  color: var(--color-ink-2);
  opacity: 1;
}

.input:focus,
.input:focus-within {
  border-color: var(--color-focus);
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.consent {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.checkbox {
  display: flex;
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  align-items: center;
  justify-content: center;
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 4px;
  background: var(--surface-input);
  color: var(--color-accent-ink);
  font-size: 11px;
}

.checkbox.checked {
  border-color: var(--color-accent-deep);
  background: var(--color-accent-deep);
}

.consent-text,
.policy-links,
.help-text {
  color: var(--color-muted);
}

.policy-links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-md);
  margin-top: var(--space-sm);
}

.policy-links text {
  color: var(--color-accent-deep);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 0.18em;
}

.primary {
  width: 100%;
  margin-top: var(--space-lg);
  border-radius: 9px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
  font-size: 14px;
  font-weight: 650;
  white-space: nowrap;
  box-shadow: none;
}

.secondary {
  width: 100%;
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 9px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 13px;
}

.divider {
  height: 36px;
  margin-top: var(--space-sm);
  color: var(--color-muted);
  line-height: 44px;
}

.divider::before {
  top: 22px;
  background: var(--color-rule);
}

.divider text {
  padding: 0 var(--space-sm);
  background: var(--palette-fffdf7);
}

.error-text {
  margin-top: var(--space-md);
  padding: var(--space-xs) var(--space-sm);
  border: var(--rule-hair) solid var(--border-accent-15);
  border-radius: 6px;
  background: var(--palette-fff7f4);
  color: var(--color-error);
}

.help-text {
  margin-top: var(--space-md);
  font-size: 11px;
  line-height: 1.65;
}

.tab:focus-visible,
.primary:focus-visible,
.secondary:focus-visible,
.consent:focus-visible,
.policy-links text:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.tab:active,
.primary:active,
.secondary:active {
  transform: translateY(1px);
}

.primary[disabled],
.primary[loading],
.secondary[disabled] {
  opacity: 0.58;
  cursor: not-allowed;
}

@media (max-width: 900px) {
  .auth-page {
    padding: var(--space-md);
    background-size: 32px 32px;
  }

  .auth-shell {
    display: block;
    min-height: calc(100vh - 32px);
    border-radius: 18px;
  }

  .brand-panel {
    padding: 28px 24px 32px;
    border-right: 0;
    border-bottom: var(--rule-hair) solid var(--color-rule);
    background: var(--palette-fffdf6);
  }

  .brand-copy {
    margin-top: 56px;
  }

  .headline {
    max-width: 100%;
    font-size: clamp(38px, 10vw, 50px);
  }

  .description {
    margin-top: var(--space-md);
    font-size: 14px;
  }

  .feature-list,
  .preview-note {
    display: none;
  }

  .form-panel {
    padding: 36px 24px 40px;
  }

  .form-heading {
    margin-top: 40px;
  }
}
</style>
