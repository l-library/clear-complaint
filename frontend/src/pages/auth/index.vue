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
          <text class="kicker">AI HEALTH COMPANION</text>
          <text class="headline">把模糊的不适，<br />整理成清楚的就医线索。</text>
          <text class="description">
            先追问关键信息，再匹配建议科室与可信证据。所有结果均标明“不构成诊断”。
          </text>
        </view>

        <view class="feature-list">
          <view class="feature-item">
            <text class="feature-number">01</text>
            <text>信息不足时先追问，不急着下结论</text>
          </view>
          <view class="feature-item">
            <text class="feature-number">02</text>
            <text>每条建议都能查看信息来源</text>
          </view>
          <view class="feature-item">
            <text class="feature-number">03</text>
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
          {{ mode === 'login' ? '登录健康账户' : '注册并继续' }}
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
.auth-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background: #eef3ef;
  color: #173a30;
}

.ambient {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.ambient-one {
  top: -180rpx;
  right: -180rpx;
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, rgba(72, 151, 124, 0.18), transparent 68%);
}

.ambient-two {
  bottom: -260rpx;
  left: -220rpx;
  width: 640rpx;
  height: 640rpx;
  background: radial-gradient(circle, rgba(201, 177, 96, 0.12), transparent 70%);
}

.auth-shell {
  position: relative;
  z-index: 1;
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
}

.brand-panel {
  display: flex;
  min-height: 100vh;
  padding: 54px 64px 42px;
  flex-direction: column;
  justify-content: space-between;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.055), transparent 42%),
    #103f35;
  color: #ffffff;
  box-sizing: border-box;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  display: flex;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: #e3f4ed;
  color: #103f35;
  font-size: 23px;
  font-weight: 800;
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
.help-text {
  display: block;
}

.error-text {
  display: block;
  margin-top: 14px;
  padding: 10px 12px;
  border: 1px solid #f0d4cc;
  border-radius: 9px;
  background: #fff7f4;
  color: #a45b48;
  font-size: 11px;
  line-height: 1.55;
  text-align: center;
}

.policy-links {
  display: flex;
  gap: 14px;
  margin-top: 8px;
  padding-left: 28px;
}

.policy-links text {
  color: #3d8d76;
  font-size: 10px;
  text-decoration: underline;
}

.brand-name {
  font-size: 22px;
  font-weight: 700;
}

.brand-en {
  margin-top: 1px;
  color: #a9cbbf;
  font-size: 11px;
  letter-spacing: 1px;
}

.brand-copy {
  max-width: 680px;
  margin: auto 0;
}

.kicker {
  color: #7ec8af;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2.5px;
}

.headline {
  margin-top: 20px;
  font-size: clamp(36px, 4vw, 60px);
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -1.5px;
}

.description {
  max-width: 580px;
  margin-top: 22px;
  color: #c3dbd3;
  font-size: 16px;
  line-height: 1.8;
}

.feature-list {
  display: grid;
  max-width: 620px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.feature-item {
  display: flex;
  min-height: 116px;
  padding: 16px;
  flex-direction: column;
  justify-content: space-between;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.055);
  color: #d7e9e3;
  font-size: 13px;
  line-height: 1.55;
  box-sizing: border-box;
}

.feature-number {
  color: #73bea5;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1px;
}

.preview-note {
  margin-top: 28px;
  color: #84a79d;
  font-size: 11px;
}

.form-panel {
  display: flex;
  padding: 64px clamp(38px, 7vw, 110px);
  flex-direction: column;
  justify-content: center;
  box-sizing: border-box;
}

.tabs {
  display: inline-flex;
  width: fit-content;
  padding: 4px;
  border-radius: 999px;
  background: #e1ebe6;
}

.tab {
  width: auto;
  margin: 0;
  padding: 0 20px;
  border-radius: 999px;
  background: transparent;
  color: #6d8179;
  font-size: 13px;
  line-height: 38px;
}

.tab::after {
  border: 0;
}

.tab.active {
  background: #ffffff;
  color: #164e3e;
  box-shadow: 0 5px 18px rgba(29, 66, 53, 0.08);
}

.form-heading {
  margin-top: 34px;
}

.form-title {
  font-size: 32px;
  font-weight: 800;
}

.form-subtitle {
  margin-top: 8px;
  color: #7b8c85;
  font-size: 14px;
}

.field {
  margin-top: 24px;
}

.field-label {
  margin-bottom: 8px;
  color: #435c52;
  font-size: 13px;
  font-weight: 700;
}

.input {
  width: 100%;
  height: 52px;
  padding: 0 15px;
  border: 1px solid #d6e2dc;
  border-radius: 12px;
  background: #fbfdfc;
  color: #203b31;
  font-size: 14px;
  box-sizing: border-box;
}

.consent {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-top: 18px;
}

.checkbox {
  display: flex;
  width: 19px;
  height: 19px;
  flex: 0 0 19px;
  align-items: center;
  justify-content: center;
  border: 1px solid #bfcfc8;
  border-radius: 6px;
  color: #ffffff;
  font-size: 12px;
}

.checkbox.checked {
  border-color: #227b63;
  background: #227b63;
}

.consent-text {
  color: #74857e;
  font-size: 12px;
  line-height: 1.55;
}

.primary {
  margin-top: 26px;
  border-radius: 13px;
  background: #126c57;
  color: #ffffff;
  font-size: 15px;
}

.secondary {
  border: 1px solid #cbdcd4;
  border-radius: 13px;
  background: #ffffff;
  color: #315f50;
  font-size: 14px;
}

.divider {
  position: relative;
  height: 44px;
  margin-top: 10px;
  color: #9aa8a2;
  font-size: 12px;
  text-align: center;
  line-height: 52px;
}

.divider::before {
  content: "";
  position: absolute;
  top: 25px;
  right: 0;
  left: 0;
  height: 1px;
  background: #e2e9e5;
}

.divider text {
  position: relative;
  z-index: 1;
  padding: 0 12px;
  background: #eef3ef;
}

.help-text {
  margin-top: 22px;
  color: #97a49e;
  font-size: 11px;
  line-height: 1.7;
  text-align: center;
}

@media (max-width: 860px) {
  .auth-shell {
    display: block;
  }

  .brand-panel {
    min-height: auto;
    padding: 28px 24px 34px;
  }

  .brand-copy {
    margin-top: 50px;
  }

  .headline {
    font-size: 38px;
  }

  .description {
    font-size: 14px;
  }

  .feature-list {
    display: none;
  }

  .preview-note {
    margin-top: 24px;
  }

  .form-panel {
    padding: 34px 24px 48px;
  }

  .divider text {
    background: #eef3ef;
  }
}
</style>

<style scoped>
/* Mint theme overrides: keep the layout, replace the dark forest palette. */
.auth-page {
  background:
    radial-gradient(circle at 12% 16%, rgba(153, 226, 205, 0.3), transparent 34%),
    radial-gradient(circle at 86% 82%, rgba(209, 241, 230, 0.65), transparent 38%),
    #eef9f5;
  color: #23493e;
}

.ambient-one {
  background: radial-gradient(circle, rgba(160, 231, 210, 0.42), transparent 68%);
}

.ambient-two {
  background: radial-gradient(circle, rgba(219, 244, 235, 0.72), transparent 70%);
}

.brand-panel {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.42), transparent 48%),
    linear-gradient(135deg, #dff5ed, #cceee3);
  color: #20483d;
}

.brand-mark {
  background: #55aa92;
  color: #ffffff;
  box-shadow: 0 8px 22px rgba(78, 161, 137, 0.2);
}

.brand-name {
  color: #1d463a;
}

.brand-en {
  color: #6f9589;
}

.kicker {
  color: #328b74;
}

.headline {
  color: #193f35;
}

.description {
  color: #57796d;
}

.feature-item {
  border-color: rgba(91, 157, 138, 0.18);
  background: rgba(255, 255, 255, 0.48);
  color: #42685c;
  box-shadow: 0 8px 24px rgba(72, 136, 117, 0.055);
}

.feature-number {
  color: #2f8d75;
}

.preview-note {
  color: #6f9186;
}

.form-panel {
  background: #f5fcf9;
}

.tabs {
  background: #dcf2ea;
}

.tab {
  color: #6d8c81;
}

.tab.active {
  background: #ffffff;
  color: #2f7f69;
}

.form-title,
.field-label {
  color: #23493e;
}

.form-subtitle,
.consent-text,
.help-text {
  color: #7c978d;
}

.input {
  border-color: #cfe6dd;
  background: #ffffff;
}

.checkbox.checked {
  border-color: #55aa92;
  background: #55aa92;
}

.primary {
  background: #4da88f;
  color: #ffffff;
  box-shadow: 0 9px 24px rgba(72, 154, 130, 0.18);
}

.secondary {
  border-color: #cce6dc;
  background: #ffffff;
  color: #387663;
}

.divider text {
  background: #f5fcf9;
}

@media (max-width: 860px) {
  .brand-panel {
    background:
      linear-gradient(150deg, rgba(255, 255, 255, 0.32), transparent 55%),
      #d9f2e9;
  }
}
</style>
