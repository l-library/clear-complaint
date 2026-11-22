<template>
  <view class="page">
    <QFlowHeader
      :step="4"
      title="健康档案"
      subtitle="查看模拟血压趋势、历史问诊和随访安排。"
    />

    <view class="content">
      <view class="profile-card">
        <view class="avatar">王</view>
        <view class="profile-main">
          <text class="name">{{ store.data.patient.name }}</text>
          <text class="meta">
            {{ store.data.patient.gender }} · {{ store.data.patient.age }}岁 ·
            {{ store.data.patient.chronicCondition }}
          </text>
          <text class="medication">{{ store.data.patient.medication }}</text>
        </view>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">家庭血压趋势</text>
          <text class="unit">mmHg</text>
        </view>
        <view class="trend">
          <view
            v-for="(item, index) in store.data.record.bloodPressureTrend"
            :key="item.label"
            class="trend-item"
          >
            <view class="bar-wrap">
              <view
                class="bar"
                :class="{ high: index === store.data.record.bloodPressureTrend.length - 1 }"
                :style="{ height: `${84 + index * 34}rpx` }"
              />
            </view>
            <text class="trend-value">{{ item.value }}</text>
            <text class="trend-label">{{ item.label }}</text>
          </view>
        </view>
      </view>

      <view class="card">
        <text class="card-title">历史问诊</text>
        <view
          v-for="item in store.data.record.episodes"
          :key="item.date"
          class="episode"
        >
          <view class="episode-dot" />
          <view class="episode-main">
            <view class="episode-head">
              <text class="date">{{ item.date }}</text>
              <text class="triage">{{ item.triage }}</text>
            </view>
            <text class="summary">{{ item.summary }}</text>
          </view>
        </view>
      </view>

      <view class="follow-card">
        <text class="follow-title">下一次随访</text>
        <text class="follow-time">48小时后 · 模拟提醒</text>
        <text class="follow-desc">重新记录血压、头晕变化和用药情况。</text>
      </view>

      <button class="primary" @click="openAudit">查看本轮纠偏与评估</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import QFlowHeader from '@/components/QFlowHeader.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()

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

.profile-card,
.card,
.follow-card {
  border-radius: 22rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(25, 65, 52, 0.06);
}

.profile-card {
  display: flex;
  gap: 17rpx;
  padding: 23rpx;
}

.avatar {
  display: flex;
  width: 70rpx;
  height: 70rpx;
  flex: 0 0 70rpx;
  align-items: center;
  justify-content: center;
  border-radius: 20rpx;
  background: #dcefe8;
  color: #1d6753;
  font-size: 30rpx;
  font-weight: 700;
}

.profile-main {
  min-width: 0;
}

.name,
.meta,
.medication,
.card-title,
.unit,
.trend-value,
.trend-label,
.date,
.summary,
.follow-title,
.follow-time,
.follow-desc {
  display: block;
}

.name {
  color: #203e34;
  font-size: 28rpx;
  font-weight: 700;
}

.meta,
.medication {
  color: #7a8a84;
  font-size: 21rpx;
}

.meta {
  margin-top: 5rpx;
}

.medication {
  margin-top: 7rpx;
  color: #4e7568;
}

.card {
  margin-top: 19rpx;
  padding: 24rpx;
}

.card-head,
.episode-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  color: #28483d;
  font-size: 26rpx;
  font-weight: 700;
}

.unit {
  color: #9aa7a2;
  font-size: 19rpx;
}

.trend {
  display: flex;
  height: 260rpx;
  align-items: flex-end;
  justify-content: space-around;
  gap: 12rpx;
  margin-top: 22rpx;
  padding-top: 10rpx;
  border-bottom: 1rpx solid #e4ece8;
}

.trend-item {
  display: flex;
  flex: 1;
  align-items: center;
  flex-direction: column;
}

.bar-wrap {
  display: flex;
  height: 205rpx;
  align-items: flex-end;
}

.bar {
  width: 38rpx;
  min-height: 84rpx;
  border-radius: 8rpx 8rpx 3rpx 3rpx;
  background: #8ec9b6;
}

.bar.high {
  background: #d6986e;
}

.trend-value {
  margin-top: 8rpx;
  color: #4a625a;
  font-size: 18rpx;
}

.trend-label {
  margin-top: 4rpx;
  color: #93a09b;
  font-size: 18rpx;
}

.episode {
  display: flex;
  gap: 14rpx;
  margin-top: 20rpx;
}

.episode-dot {
  width: 13rpx;
  height: 13rpx;
  flex: 0 0 13rpx;
  margin-top: 11rpx;
  border-radius: 50%;
  background: #4ba986;
}

.episode-main {
  flex: 1;
}

.date {
  color: #48685d;
  font-size: 22rpx;
  font-weight: 700;
}

.triage {
  padding: 4rpx 10rpx;
  border-radius: 999rpx;
  background: #edf5f2;
  color: #4d7c6d;
  font-size: 18rpx;
}

.summary {
  margin-top: 7rpx;
  color: #788981;
  font-size: 22rpx;
  line-height: 1.55;
}

.follow-card {
  margin-top: 19rpx;
  padding: 22rpx;
  border: 1rpx dashed #d7c275;
  background: #fffdf6;
}

.follow-title {
  color: #76631f;
  font-size: 22rpx;
  font-weight: 700;
}

.follow-time {
  margin-top: 6rpx;
  color: #8b7427;
  font-size: 26rpx;
  font-weight: 700;
}

.follow-desc {
  margin-top: 6rpx;
  color: #81764f;
  font-size: 21rpx;
}

.primary {
  margin-top: 24rpx;
  border-radius: 14rpx;
  background: #136d59;
  color: #ffffff;
  font-size: 27rpx;
}
</style>
