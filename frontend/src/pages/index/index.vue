<template>
  <view class="home">
    <view class="page-shell">
      <view class="hero">
        <view class="hero-glow glow-one" />
        <view class="hero-glow glow-two" />

        <view class="topbar">
          <view class="brand">
            <text class="brand-mark">清</text>
            <view>
              <text class="brand-name">清诉</text>
              <text class="brand-en">ClearComplaint</text>
            </view>
          </view>
          <text class="demo-badge">MOCK 演示</text>
        </view>

        <view class="hero-copy">
          <text class="eyebrow">认知风险识别 · 证据约束 · 安全纠偏</text>
          <text class="headline">先弄清楚，再决定怎么办。</text>
          <text class="description">
            说出您的不适。清诉会识别模糊表达和风险归因，先追问关键信息，再给出有依据、可追溯的就医建议。
          </text>
        </view>

        <button class="hero-action" @click="openDemo">
          <text>开始模拟问诊</text>
          <text class="hero-arrow">→</text>
        </button>

        <view class="trust-row">
          <text class="trust-item">不诊断疾病</text>
          <text class="trust-item">不推荐处方</text>
          <text class="trust-item">不替代医生</text>
        </view>
      </view>

      <view class="content">
        <view class="section-heading">
          <view>
            <text class="section-eyebrow">DEMO PATIENT</text>
            <text class="section-title">本次演示病例</text>
          </view>
          <text class="section-note">模拟数据</text>
        </view>

        <view class="patient-card">
          <view class="patient-main">
            <view class="avatar">王</view>
            <view class="patient-copy">
              <text class="patient-name">王阿姨 · 68岁</text>
              <text class="patient-meta">高血压随访 · 已记录家庭血压</text>
            </view>
          </view>
          <view class="patient-divider" />
          <view class="patient-reading">
            <view>
              <text class="reading-label">家庭血压</text>
              <text class="reading-value">162/98</text>
            </view>
            <view>
              <text class="reading-label">心率</text>
              <text class="reading-value">88 <text class="reading-unit">bpm</text></text>
            </view>
            <view>
              <text class="reading-label">测量时间</text>
              <text class="reading-time">今天 08:30</text>
            </view>
          </view>
          <view class="patient-quote">
            “这两天有点头晕，我想把降压药停两天。”
          </view>
        </view>

        <view class="section-heading feature-heading">
          <view>
            <text class="section-eyebrow">WHY CLEARCOMPLAINT</text>
            <text class="section-title">不只是回答问题</text>
          </view>
        </view>

        <view class="feature-grid">
          <view class="feature-card">
            <text class="feature-index">01</text>
            <text class="feature-title">识别风险表达</text>
            <text class="feature-text">区分客观症状、主观归因和缺失信息。</text>
          </view>
          <view class="feature-card">
            <text class="feature-index">02</text>
            <text class="feature-title">先追问再判断</text>
            <text class="feature-text">关键条件不足时停止猜测，继续澄清。</text>
          </view>
          <view class="feature-card">
            <text class="feature-index">03</text>
            <text class="feature-title">用证据做纠偏</text>
            <text class="feature-text">删除无依据结论，并重新验证稳定性。</text>
          </view>
        </view>

        <view class="journey-card">
          <view class="journey-heading">
            <text class="journey-title">一次咨询，三步完成</text>
            <text class="journey-caption">约 2 分钟</text>
          </view>
          <view class="journey-list">
            <view class="journey-item">
              <text class="journey-number">1</text>
              <view>
                <text class="journey-label">说清不适</text>
                <text class="journey-desc">用自己的话描述症状和担心</text>
              </view>
            </view>
            <view class="journey-line" />
            <view class="journey-item">
              <text class="journey-number">2</text>
              <view>
                <text class="journey-label">补充信息</text>
                <text class="journey-desc">回答 Agent 的关键追问</text>
              </view>
            </view>
            <view class="journey-line" />
            <view class="journey-item">
              <text class="journey-number">3</text>
              <view>
                <text class="journey-label">查看结果</text>
                <text class="journey-desc">核对科室、依据和就医准备</text>
              </view>
            </view>
          </view>
        </view>

        <view class="dev-card">
          <view class="dev-copy">
            <text class="dev-label">开发调试</text>
            <text class="dev-title">接口与 Vue 练习</text>
            <text class="dev-status" :class="{ success: backendOk, error: backendError }">
              {{ result }}
            </text>
          </view>
          <view class="dev-actions">
            <button class="dev-button" :loading="loading" @click="checkBackend">
              检查后端
            </button>
            <button class="dev-button ghost" @click="openPractice">Vue 02</button>
          </view>
        </view>

        <view class="footer-note">
          <text class="footer-mark">清诉</text>
          <text class="footer-text">
            当前为比赛 Mock 原型。所有病例和指标均为模拟数据，不构成诊断或治疗建议。
          </text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ping } from '@/api/ping'

const loading = ref(false)
const result = ref('尚未连接后端')
const backendOk = computed(() => result.value.startsWith('后端已连接'))
const backendError = computed(() => result.value.startsWith('连接失败'))

async function checkBackend() {
  loading.value = true
  result.value = '正在连接后端'
  try {
    const data = await ping()
    result.value = `后端已连接 · ${data.status}`
  } catch (error) {
    result.value = `连接失败 · ${(error as Error).message}`
  } finally {
    loading.value = false
  }
}

function openDemo() {
  uni.navigateTo({ url: '/pages/auth/index' })
}

function openPractice() {
  uni.navigateTo({ url: '/pages/practice/vue-basics' })
}
</script>

<style>
.home {
  min-height: 100vh;
  background:
    radial-gradient(circle at 85% 8%, rgba(74, 145, 121, 0.08), transparent 28%),
    #f3f6f4;
}

.page-shell {
  width: 100%;
  max-width: 980rpx;
  margin: 0 auto;
}

.hero {
  position: relative;
  overflow: hidden;
  padding: calc(30rpx + env(safe-area-inset-top)) 30rpx 30rpx;
  border-radius: 0 0 42rpx 42rpx;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.04), transparent 42%),
    #103f35;
  color: #ffffff;
}

.hero-glow {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.glow-one {
  top: -110rpx;
  right: -80rpx;
  width: 380rpx;
  height: 380rpx;
  background: radial-gradient(circle, rgba(104, 205, 169, 0.28), transparent 68%);
}

.glow-two {
  right: 140rpx;
  bottom: -180rpx;
  width: 430rpx;
  height: 430rpx;
  background: radial-gradient(circle, rgba(216, 196, 118, 0.1), transparent 66%);
}

.topbar,
.brand,
.hero-action,
.trust-row,
.patient-main,
.section-heading,
.patient-reading,
.journey-heading,
.journey-item,
.dev-card,
.dev-actions,
.footer-note {
  display: flex;
}

.topbar,
.section-heading,
.journey-heading,
.dev-card {
  align-items: center;
  justify-content: space-between;
}

.topbar {
  position: relative;
  z-index: 1;
}

.brand {
  align-items: center;
  gap: 14rpx;
}

.brand-mark {
  display: flex;
  width: 58rpx;
  height: 58rpx;
  align-items: center;
  justify-content: center;
  border-radius: 18rpx;
  background: #dff4eb;
  color: #123f35;
  font-size: 31rpx;
  font-weight: 800;
}

.brand-name,
.brand-en,
.eyebrow,
.headline,
.description,
.trust-item,
.section-eyebrow,
.section-title,
.patient-name,
.patient-meta,
.reading-label,
.reading-value,
.reading-time,
.patient-quote,
.feature-index,
.feature-title,
.feature-text,
.journey-title,
.journey-caption,
.journey-label,
.journey-desc,
.dev-label,
.dev-title,
.dev-status,
.footer-mark,
.footer-text {
  display: block;
}

.brand-name {
  font-size: 29rpx;
  font-weight: 700;
}

.brand-en {
  margin-top: 1rpx;
  color: #a9cbbf;
  font-size: 17rpx;
  letter-spacing: 1rpx;
}

.demo-badge {
  padding: 8rpx 14rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.06);
  color: #cce5dc;
  font-size: 18rpx;
}

.hero-copy {
  position: relative;
  z-index: 1;
  margin-top: 66rpx;
}

.eyebrow {
  color: #85cdb5;
  font-size: 20rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}

.headline {
  max-width: 620rpx;
  margin-top: 17rpx;
  font-size: 52rpx;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: -1rpx;
}

.description {
  max-width: 650rpx;
  margin-top: 18rpx;
  color: #c5dcd4;
  font-size: 24rpx;
  line-height: 1.75;
}

.hero-action {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100rpx;
  align-items: center;
  justify-content: space-between;
  margin-top: 32rpx;
  padding: 0 30rpx;
  border-radius: 18rpx;
  background: #e7f4ee;
  color: #123f35;
  font-size: 30rpx;
  font-weight: 700;
  box-shadow: 0 14rpx 34rpx rgba(0, 0, 0, 0.16);
}

.hero-arrow {
  font-size: 38rpx;
  font-weight: 400;
}

.trust-row {
  position: relative;
  z-index: 1;
  gap: 12rpx;
  margin-top: 22rpx;
}

.trust-item {
  flex: 1;
  padding: 12rpx 8rpx;
  border-radius: 11rpx;
  background: rgba(255, 255, 255, 0.055);
  color: #bcd5cc;
  font-size: 19rpx;
  text-align: center;
}

.content {
  padding: 30rpx 24rpx 60rpx;
}

.section-heading {
  margin-top: 8rpx;
}

.feature-heading {
  margin-top: 38rpx;
}

.section-eyebrow {
  color: #6e9386;
  font-size: 17rpx;
  font-weight: 800;
  letter-spacing: 2rpx;
}

.section-title {
  margin-top: 6rpx;
  color: #203d33;
  font-size: 31rpx;
  font-weight: 700;
}

.section-note {
  padding: 6rpx 12rpx;
  border-radius: 999rpx;
  background: #e5ece8;
  color: #6e837b;
  font-size: 18rpx;
}

.patient-card,
.feature-card,
.journey-card,
.dev-card {
  border-radius: 23rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 32rpx rgba(31, 66, 54, 0.055);
}

.patient-card {
  margin-top: 17rpx;
  padding: 24rpx;
}

.patient-main {
  align-items: center;
  gap: 15rpx;
}

.avatar {
  display: flex;
  width: 64rpx;
  height: 64rpx;
  align-items: center;
  justify-content: center;
  border-radius: 19rpx;
  background: #dff1e9;
  color: #216b56;
  font-size: 28rpx;
  font-weight: 700;
}

.patient-name {
  color: #234038;
  font-size: 27rpx;
  font-weight: 700;
}

.patient-meta {
  margin-top: 4rpx;
  color: #85958f;
  font-size: 20rpx;
}

.patient-divider {
  height: 1rpx;
  margin: 21rpx 0;
  background: #e9efec;
}

.patient-reading {
  justify-content: space-between;
}

.reading-label {
  color: #8b9a94;
  font-size: 18rpx;
}

.reading-value {
  margin-top: 6rpx;
  color: #185d4b;
  font-size: 27rpx;
  font-weight: 700;
}

.reading-unit {
  font-size: 17rpx;
  font-weight: 400;
}

.reading-time {
  margin-top: 8rpx;
  color: #526b61;
  font-size: 20rpx;
}

.patient-quote {
  margin-top: 20rpx;
  padding: 16rpx 18rpx;
  border-left: 4rpx solid #80bbaa;
  border-radius: 4rpx 12rpx 12rpx 4rpx;
  background: #f5f9f7;
  color: #5f726b;
  font-size: 22rpx;
  line-height: 1.6;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12rpx;
  margin-top: 17rpx;
}

.feature-card {
  min-width: 0;
  padding: 20rpx 16rpx;
}

.feature-index {
  color: #8ec1b0;
  font-size: 18rpx;
  font-weight: 800;
  letter-spacing: 1rpx;
}

.feature-title {
  margin-top: 11rpx;
  color: #28453b;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1.45;
}

.feature-text {
  margin-top: 8rpx;
  color: #81908a;
  font-size: 19rpx;
  line-height: 1.6;
}

.journey-card {
  margin-top: 20rpx;
  padding: 24rpx;
}

.journey-title {
  color: #29463c;
  font-size: 25rpx;
  font-weight: 700;
}

.journey-caption {
  color: #8b9a94;
  font-size: 19rpx;
}

.journey-list {
  display: flex;
  align-items: flex-start;
  margin-top: 23rpx;
}

.journey-item {
  width: 30%;
  align-items: flex-start;
  gap: 10rpx;
}

.journey-number {
  display: flex;
  width: 37rpx;
  height: 37rpx;
  flex: 0 0 37rpx;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e3f2ec;
  color: #2b705b;
  font-size: 18rpx;
  font-weight: 700;
}

.journey-line {
  height: 1rpx;
  flex: 1;
  margin: 18rpx 10rpx 0;
  background: #dce8e3;
}

.journey-label {
  color: #3c574d;
  font-size: 21rpx;
  font-weight: 700;
}

.journey-desc {
  margin-top: 5rpx;
  color: #8a9893;
  font-size: 17rpx;
  line-height: 1.45;
}

.dev-card {
  gap: 18rpx;
  margin-top: 22rpx;
  padding: 20rpx;
  background: #e9efec;
  box-shadow: none;
}

.dev-copy {
  min-width: 0;
  flex: 1;
}

.dev-label {
  color: #81908a;
  font-size: 17rpx;
  font-weight: 700;
  letter-spacing: 1rpx;
}

.dev-title {
  margin-top: 4rpx;
  color: #405d52;
  font-size: 22rpx;
  font-weight: 700;
}

.dev-status {
  margin-top: 5rpx;
  overflow: hidden;
  color: #899691;
  font-size: 17rpx;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dev-status.success {
  color: #21815f;
}

.dev-status.error {
  color: #a95543;
}

.dev-actions {
  flex: 0 0 auto;
  gap: 8rpx;
}

.dev-button {
  width: auto;
  margin: 0;
  padding: 0 15rpx;
  border-radius: 10rpx;
  background: #ffffff;
  color: #42655a;
  font-size: 18rpx;
  line-height: 54rpx;
}

.dev-button.ghost {
  border: 1rpx solid #ccd9d4;
  background: transparent;
}

.footer-note {
  align-items: flex-start;
  gap: 13rpx;
  margin-top: 27rpx;
  padding: 0 6rpx;
}

.footer-mark {
  flex: 0 0 auto;
  color: #739187;
  font-size: 20rpx;
  font-weight: 800;
}

.footer-text {
  color: #97a29e;
  font-size: 18rpx;
  line-height: 1.65;
}

@media (min-width: 760px) {
  .hero {
    margin-top: 24rpx;
    border-radius: 32rpx;
  }

  .content {
    padding-right: 42rpx;
    padding-left: 42rpx;
  }
}
</style>

<style>
/* Mint homepage theme overrides. */
.home {
  background:
    radial-gradient(circle at 85% 8%, rgba(154, 225, 205, 0.22), transparent 30%),
    #eff9f5;
}

.hero {
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.42), transparent 46%),
    linear-gradient(135deg, #ddf5ed, #c7ebdf);
  color: #1f483c;
}

.glow-one {
  background: radial-gradient(circle, rgba(255, 255, 255, 0.5), transparent 68%);
}

.glow-two {
  background: radial-gradient(circle, rgba(127, 204, 180, 0.18), transparent 66%);
}

.brand-mark {
  background: #4ea68e;
  color: #ffffff;
}

.brand-name,
.headline,
.section-title,
.patient-name,
.feature-title,
.journey-title,
.dev-title {
  color: #21483c;
}

.brand-en,
.description,
.patient-meta,
.reading-label,
.feature-text,
.journey-caption,
.journey-desc,
.footer-text {
  color: #648277;
}

.eyebrow,
.section-eyebrow {
  color: #3f8d76;
}

.demo-badge {
  border-color: rgba(55, 119, 98, 0.18);
  background: rgba(255, 255, 255, 0.4);
  color: #477669;
}

.hero-action {
  background: #4ba58d;
  color: #ffffff;
  box-shadow: 0 14px 34px rgba(66, 148, 124, 0.2);
}

.trust-item {
  background: rgba(255, 255, 255, 0.42);
  color: #50786b;
}

.patient-card,
.feature-card,
.journey-card {
  border: 1px solid #e0eee8;
  box-shadow: 0 12px 32px rgba(68, 139, 119, 0.06);
}

.patient-quote,
.dev-card {
  background: #f1faf6;
}

.avatar,
.journey-number {
  background: #dcf1e8;
  color: #317761;
}

.reading-value {
  color: #347762;
}
</style>
