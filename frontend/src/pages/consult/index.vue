<template>
  <view class="page">
    <QFlowHeader
      :step="1"
      title="描述您现在的不适"
      subtitle="先说出最困扰您的情况，后续会继续追问。"
      :show-back="false"
    />

    <view class="content">
      <view class="patient-card">
        <view class="patient-avatar">王</view>
        <view class="patient-info">
          <text class="patient-name">{{ store.data.patient.name }}</text>
          <text class="patient-meta">
            {{ store.data.patient.gender }} · {{ store.data.patient.age }}岁 ·
            {{ store.data.patient.chronicCondition }}
          </text>
        </view>
        <view class="vital">
          <text class="vital-label">家庭血压</text>
          <text class="vital-value">{{ store.data.vitals.bloodPressure }}</text>
        </view>
      </view>

      <view class="input-card">
        <text class="section-label">主诉原文</text>
        <textarea
          v-model="complaint"
          class="complaint-input"
          maxlength="300"
          placeholder="例如：这两天有点头晕，我想把降压药停两天"
        />
        <text class="counter">{{ complaint.length }} / 300</text>

        <view class="quick-list">
          <button
            v-for="item in quickPrompts"
            :key="item"
            class="quick"
            @click="complaint = item"
          >
            {{ item }}
          </button>
        </view>

        <button class="primary" @click="continueFlow">继续确认信息</button>
      </view>

      <view class="safety-note">
        <text class="safety-title">安全说明</text>
        <text class="safety-text">
          本页面使用模拟数据展示产品流程，不进行疾病诊断，不开具处方，也不建议自行调整长期用药。
        </text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import QFlowHeader from '@/components/QFlowHeader.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()
const complaint = ref(store.data.originalText)

const quickPrompts = [
  '这两天有点头晕，想停降压药',
  '最近总是睡不好，白天没精神',
  '吃完药后有点不舒服',
]

function continueFlow() {
  store.start(complaint.value)
  uni.navigateTo({ url: '/pages/consult/clarify' })
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

.patient-card,
.input-card,
.safety-note {
  border-radius: 22rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(25, 65, 52, 0.06);
}

.patient-card {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 22rpx;
}

.patient-avatar {
  display: flex;
  width: 62rpx;
  height: 62rpx;
  align-items: center;
  justify-content: center;
  border-radius: 18rpx;
  background: #dff2ea;
  color: #1e6956;
  font-size: 28rpx;
  font-weight: 700;
}

.patient-info {
  min-width: 0;
  flex: 1;
}

.patient-name,
.patient-meta,
.vital-label,
.vital-value,
.section-label,
.counter,
.safety-title,
.safety-text {
  display: block;
}

.patient-name {
  color: #1e3d33;
  font-size: 28rpx;
  font-weight: 700;
}

.patient-meta {
  margin-top: 5rpx;
  color: #7b8d86;
  font-size: 21rpx;
}

.vital {
  text-align: right;
}

.vital-label {
  color: #82918b;
  font-size: 19rpx;
}

.vital-value {
  margin-top: 3rpx;
  color: #1b654f;
  font-size: 25rpx;
  font-weight: 700;
}

.input-card {
  margin-top: 20rpx;
  padding: 26rpx 24rpx;
}

.section-label {
  color: #1e4639;
  font-size: 25rpx;
  font-weight: 700;
}

.complaint-input {
  width: 100%;
  height: 220rpx;
  margin-top: 15rpx;
  padding: 22rpx;
  border: 2rpx solid #dbe7e2;
  border-radius: 16rpx;
  background: #f8fbfa;
  color: #233d34;
  font-size: 27rpx;
  line-height: 1.65;
  box-sizing: border-box;
}

.counter {
  margin-top: 8rpx;
  color: #9aa7a2;
  font-size: 20rpx;
  text-align: right;
}

.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 14rpx;
}

.quick {
  width: auto;
  margin: 0;
  padding: 0 17rpx;
  border: 1rpx solid #cee1da;
  border-radius: 999rpx;
  background: #f2f8f5;
  color: #427064;
  font-size: 21rpx;
  line-height: 58rpx;
}

.primary {
  margin-top: 28rpx;
  border-radius: 15rpx;
  background: #136d59;
  color: #ffffff;
  font-size: 28rpx;
}

.safety-note {
  margin-top: 20rpx;
  padding: 22rpx;
  border-left: 5rpx solid #ddc26e;
  background: #fffdf6;
}

.safety-title {
  color: #6b5a1b;
  font-size: 22rpx;
  font-weight: 700;
}

.safety-text {
  margin-top: 8rpx;
  color: #81764f;
  font-size: 22rpx;
  line-height: 1.65;
}
</style>
