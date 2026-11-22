<template>
  <view class="page">
    <QFlowHeader
      :step="5"
      title="纠偏与评估"
      subtitle="对照原回答、风险发现和纠偏结果，验证系统有没有变得更稳定。"
    />

    <view class="content">
      <view class="metric-grid">
        <view
          v-for="item in store.data.audit.metrics"
          :key="item.label"
          class="metric"
        >
          <text class="metric-label">{{ item.label }}</text>
          <view class="metric-values">
            <text class="before">{{ item.before }}</text>
            <text class="arrow">→</text>
            <text class="after" :class="{ down: !item.improved }">{{ item.after }}</text>
          </view>
        </view>
      </view>

      <view class="compare-card">
        <view class="answer-block original">
          <text class="answer-label">原回答 · 存在风险</text>
          <text class="answer-text">{{ store.data.audit.originalAnswer }}</text>
        </view>
        <view class="divider">
          <text>Agent 复核</text>
        </view>
        <view class="answer-block corrected">
          <text class="answer-label">纠偏回答 · 证据约束</text>
          <text class="answer-text">{{ store.data.audit.correctedAnswer }}</text>
        </view>
      </view>

      <view class="findings-card">
        <text class="card-title">审计发现</text>
        <view
          v-for="item in store.data.audit.findings"
          :key="item.title"
          class="finding"
        >
          <view class="finding-head">
            <text
              class="finding-level"
              :class="{ fixed: item.level === '已修复' }"
            >
              {{ item.level }}
            </text>
            <text class="finding-title">{{ item.title }}</text>
          </view>
          <text class="finding-detail">{{ item.detail }}</text>
        </view>
      </view>

      <view class="explain-card">
        <text class="explain-title">本次流程完成了什么？</text>
        <view v-for="item in explainItems" :key="item" class="explain-item">
          <text class="dot">•</text>
          <text>{{ item }}</text>
        </view>
      </view>

      <view class="actions">
        <button class="secondary" @click="backHome">返回首页</button>
        <button class="primary" @click="restart">重新演示</button>
      </view>

      <text class="notice">
        页面中的病例、回答和指标均为 Mock 数据，用于展示最终产品形态。
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
import QFlowHeader from '@/components/QFlowHeader.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()

const explainItems = [
  '区分了用户主诉、主观判断和缺失信息',
  '对自行停药等高风险表达进行了拦截',
  '用证据约束替换了无依据的原回答',
  '在纠偏后重新验证一致性和正常案例通过率',
]

function restart() {
  store.reset()
  uni.reLaunch({ url: '/pages/consult/index' })
}

function backHome() {
  store.reset()
  uni.reLaunch({ url: '/pages/index/index' })
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f0f5f2;
}

.content {
  padding: 24rpx 24rpx 60rpx;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12rpx;
}

.metric {
  padding: 19rpx;
  border-radius: 17rpx;
  background: #ffffff;
  box-shadow: 0 10rpx 26rpx rgba(25, 65, 52, 0.05);
}

.metric-label,
.metric-values,
.answer-label,
.answer-text,
.card-title,
.finding-detail,
.explain-title,
.notice {
  display: block;
}

.metric-label {
  color: #7a8984;
  font-size: 20rpx;
}

.metric-values {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  margin-top: 8rpx;
}

.before {
  color: #a07e75;
  font-size: 25rpx;
}

.arrow {
  color: #9da8a4;
  font-size: 20rpx;
}

.after {
  color: #12825f;
  font-size: 30rpx;
  font-weight: 700;
}

.after.down {
  color: #8a8065;
}

.compare-card,
.findings-card,
.explain-card {
  margin-top: 18rpx;
  border-radius: 21rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(25, 65, 52, 0.06);
}

.answer-block {
  padding: 22rpx;
}

.answer-block.original {
  border-radius: 21rpx 21rpx 0 0;
  background: #fff8f6;
}

.answer-block.corrected {
  border-radius: 0 0 21rpx 21rpx;
  background: #f4fbf8;
}

.answer-label {
  font-size: 21rpx;
  font-weight: 700;
}

.original .answer-label {
  color: #a85e4b;
}

.corrected .answer-label {
  color: #27725b;
}

.answer-text {
  margin-top: 9rpx;
  color: #53645e;
  font-size: 23rpx;
  line-height: 1.65;
}

.divider {
  display: flex;
  height: 52rpx;
  align-items: center;
  justify-content: center;
  background: #eef3f1;
  color: #507166;
  font-size: 19rpx;
  font-weight: 700;
}

.findings-card,
.explain-card {
  padding: 23rpx;
}

.card-title {
  color: #28483d;
  font-size: 26rpx;
  font-weight: 700;
}

.finding {
  margin-top: 18rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid #edf1ef;
}

.finding:first-of-type {
  padding-top: 0;
  border-top: 0;
}

.finding-head {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.finding-level {
  padding: 4rpx 9rpx;
  border-radius: 999rpx;
  background: #fce8e3;
  color: #a64e3b;
  font-size: 18rpx;
}

.finding-level.fixed {
  background: #e7f5ef;
  color: #28765d;
}

.finding-title {
  color: #3e594f;
  font-size: 23rpx;
  font-weight: 700;
}

.finding-detail {
  margin-top: 7rpx;
  color: #7a8984;
  font-size: 22rpx;
  line-height: 1.55;
}

.explain-title {
  color: #28483d;
  font-size: 24rpx;
  font-weight: 700;
}

.explain-item {
  display: flex;
  gap: 8rpx;
  margin-top: 11rpx;
  color: #63766f;
  font-size: 22rpx;
  line-height: 1.55;
}

.dot {
  color: #3ca27d;
  font-weight: 700;
}

.actions {
  display: flex;
  gap: 14rpx;
  margin-top: 22rpx;
}

.actions button {
  flex: 1;
  margin: 0;
  border-radius: 14rpx;
  font-size: 24rpx;
}

.secondary {
  border: 1rpx solid #c8dcd4;
  background: #ffffff;
  color: #366b5b;
}

.primary {
  background: #136d59;
  color: #ffffff;
}

.notice {
  margin-top: 22rpx;
  color: #929f9a;
  font-size: 19rpx;
  line-height: 1.55;
  text-align: center;
}
</style>
