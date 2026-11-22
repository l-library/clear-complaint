<template>
  <view class="page">
    <QFlowHeader
      :step="3"
      title="模拟分诊结果"
      subtitle="根据模拟数据生成，仅用于展示产品交互与技术闭环。"
    />

    <view class="content">
      <view class="result-hero" :class="store.data.result.triageTone">
        <view>
          <text class="hero-label">建议就医层级</text>
          <text class="hero-value">{{ store.data.result.triage }}</text>
          <text class="hero-dept">首推科室 · {{ store.data.result.department }}</text>
        </view>
        <view class="hero-icon">十</view>
      </view>

      <view class="card">
        <text class="card-title">可能相关情况</text>
        <view
          v-for="(item, index) in store.data.result.conditions"
          :key="item.name"
          class="condition"
        >
          <view class="condition-head">
            <text class="condition-index">0{{ index + 1 }}</text>
            <text class="condition-name">{{ item.name }}</text>
          </view>
          <text class="condition-note">{{ item.note }}</text>
          <view class="evidence">
            <text class="evidence-title">{{ item.evidence.title }}</text>
            <text class="evidence-text">“{{ item.evidence.excerpt }}”</text>
            <text class="evidence-source">来源：{{ item.evidence.source }}</text>
          </view>
        </view>
      </view>

      <view class="card">
        <text class="card-title">就医前准备</text>
        <view
          v-for="(item, index) in store.data.result.preparation"
          :key="item"
          class="prepare-item"
        >
          <text class="check">✓</text>
          <text>{{ item }}</text>
        </view>
      </view>

      <view class="follow-up">
        <text class="follow-title">后续观察</text>
        <text class="follow-text">{{ store.data.result.followUp }}</text>
      </view>

      <view class="actions">
        <button class="secondary" @click="openRecord">查看健康档案</button>
        <button class="primary" @click="openAudit">查看纠偏与评估</button>
      </view>

      <text class="notice">模拟演示 · 不构成诊断 · 如有危险症状请及时就医</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import QFlowHeader from '@/components/QFlowHeader.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()

function openRecord() {
  uni.navigateTo({ url: '/pages/record/index' })
}

function openAudit() {
  uni.navigateTo({ url: '/pages/audit/index' })
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

.result-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx;
  border-radius: 24rpx;
  color: #ffffff;
}

.result-hero.clinic {
  background: linear-gradient(135deg, #1a725b, #2d8a70);
}

.result-hero.warning {
  background: linear-gradient(135deg, #a9523b, #ca654b);
}

.result-hero.observe {
  background: linear-gradient(135deg, #68734a, #85905f);
}

.hero-label,
.hero-value,
.hero-dept {
  display: block;
}

.hero-label {
  color: rgba(255, 255, 255, 0.7);
  font-size: 21rpx;
}

.hero-value {
  margin-top: 7rpx;
  font-size: 42rpx;
  font-weight: 700;
}

.hero-dept {
  margin-top: 9rpx;
  color: #dcf0e9;
  font-size: 24rpx;
}

.hero-icon {
  display: flex;
  width: 82rpx;
  height: 82rpx;
  align-items: center;
  justify-content: center;
  border: 1rpx solid rgba(255, 255, 255, 0.25);
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.12);
  font-size: 34rpx;
  font-weight: 700;
}

.card {
  margin-top: 20rpx;
  padding: 24rpx;
  border-radius: 22rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(25, 65, 52, 0.06);
}

.card-title {
  display: block;
  color: #28483d;
  font-size: 27rpx;
  font-weight: 700;
}

.condition {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid #edf1ef;
}

.condition:first-of-type {
  padding-top: 0;
  border-top: 0;
}

.condition-head {
  display: flex;
  align-items: center;
  gap: 11rpx;
}

.condition-index {
  color: #78ad9d;
  font-size: 21rpx;
  font-weight: 700;
}

.condition-name {
  color: #24473b;
  font-size: 26rpx;
  font-weight: 700;
}

.condition-note,
.evidence-title,
.evidence-text,
.evidence-source,
.follow-title,
.follow-text,
.notice {
  display: block;
}

.condition-note {
  margin-top: 9rpx;
  color: #6c7d76;
  font-size: 23rpx;
  line-height: 1.6;
}

.evidence {
  margin-top: 12rpx;
  padding: 14rpx 16rpx;
  border-radius: 12rpx;
  background: #f3f8f6;
}

.evidence-title {
  color: #356c5b;
  font-size: 21rpx;
  font-weight: 700;
}

.evidence-text {
  margin-top: 6rpx;
  color: #52675f;
  font-size: 22rpx;
  line-height: 1.55;
}

.evidence-source {
  margin-top: 5rpx;
  color: #93a09b;
  font-size: 19rpx;
}

.prepare-item {
  display: flex;
  align-items: flex-start;
  gap: 11rpx;
  margin-top: 13rpx;
  color: #52675f;
  font-size: 23rpx;
  line-height: 1.55;
}

.check {
  color: #32a078;
  font-weight: 700;
}

.follow-up {
  margin-top: 20rpx;
  padding: 20rpx 22rpx;
  border: 1rpx dashed #d7c275;
  border-radius: 16rpx;
  background: #fffdf6;
}

.follow-title {
  color: #77631e;
  font-size: 22rpx;
  font-weight: 700;
}

.follow-text {
  margin-top: 7rpx;
  color: #7d724d;
  font-size: 23rpx;
  line-height: 1.55;
}

.actions {
  display: flex;
  gap: 14rpx;
  margin-top: 24rpx;
}

.actions button {
  flex: 1;
  margin: 0;
  border-radius: 14rpx;
  font-size: 23rpx;
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
  text-align: center;
}
</style>
