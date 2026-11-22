<template>
  <view class="page">
    <QFlowHeader
      :step="2"
      title="先补充关键信息"
      subtitle="Agent 识别到信息缺口，不会在信息不足时直接下结论。"
    />

    <view class="content">
      <view class="quote-card">
        <text class="quote-label">用户原话</text>
        <text class="quote-text">“{{ store.data.originalText }}”</text>
      </view>

      <view class="risk-card">
        <text class="card-title">识别到的风险表达</text>
        <view
          v-for="(item, index) in store.data.recognizedRisks"
          :key="item"
          class="risk-item"
        >
          <text class="risk-index">{{ index + 1 }}</text>
          <text>{{ item }}</text>
        </view>
      </view>

      <view class="form-card">
        <view class="field">
          <text class="field-label">症状持续多久？</text>
          <input v-model="form.duration" class="field-input" placeholder="例如：两天" />
        </view>
        <view class="field">
          <text class="field-label">最近一次血压是多少？</text>
          <input
            v-model="form.latestBloodPressure"
            class="field-input"
            placeholder="例如：162/98 mmHg"
          />
        </view>
        <view class="field">
          <text class="field-label">有没有其他伴随症状？</text>
          <textarea
            v-model="form.accompanyingSymptoms"
            class="field-textarea"
            placeholder="例如：偶尔心慌，没有胸痛"
          />
        </view>
        <view class="field">
          <text class="field-label">关于用药，您现在想怎么做？</text>
          <input
            v-model="form.medicationIntent"
            class="field-input"
            placeholder="例如：想先停药观察"
          />
        </view>

        <button class="primary" @click="continueFlow">生成模拟分诊结果</button>
      </view>

      <text class="notice">模拟流程 · 不构成医疗建议</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import QFlowHeader from '@/components/QFlowHeader.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()
const form = reactive({ ...store.data.clarification })

function continueFlow() {
  store.saveClarification({ ...form })
  uni.navigateTo({ url: '/pages/triage/result' })
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

.quote-card,
.risk-card,
.form-card {
  border-radius: 22rpx;
  background: #ffffff;
  box-shadow: 0 12rpx 34rpx rgba(25, 65, 52, 0.06);
}

.quote-card {
  padding: 22rpx 24rpx;
  border-left: 5rpx solid #77bba5;
}

.quote-label,
.quote-text,
.card-title,
.field-label,
.notice {
  display: block;
}

.quote-label,
.card-title {
  color: #356556;
  font-size: 22rpx;
  font-weight: 700;
}

.quote-text {
  margin-top: 8rpx;
  color: #28483d;
  font-size: 27rpx;
  line-height: 1.65;
}

.risk-card {
  margin-top: 18rpx;
  padding: 22rpx 24rpx;
  border: 1rpx dashed #d7c275;
  background: #fffdf6;
}

.risk-item {
  display: flex;
  gap: 13rpx;
  margin-top: 15rpx;
  color: #6e6442;
  font-size: 24rpx;
  line-height: 1.55;
}

.risk-index {
  display: flex;
  flex: 0 0 34rpx;
  width: 34rpx;
  height: 34rpx;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f2e3ae;
  color: #796316;
  font-size: 19rpx;
  font-weight: 700;
}

.form-card {
  margin-top: 18rpx;
  padding: 24rpx;
}

.field + .field {
  margin-top: 22rpx;
}

.field-label {
  color: #28483d;
  font-size: 24rpx;
  font-weight: 700;
}

.field-input,
.field-textarea {
  width: 100%;
  margin-top: 10rpx;
  padding: 18rpx;
  border: 2rpx solid #dbe7e2;
  border-radius: 13rpx;
  background: #f8fbfa;
  color: #29463c;
  font-size: 25rpx;
  box-sizing: border-box;
}

.field-input {
  height: 82rpx;
}

.field-textarea {
  height: 130rpx;
}

.primary {
  margin-top: 28rpx;
  border-radius: 15rpx;
  background: #136d59;
  color: #ffffff;
  font-size: 28rpx;
}

.notice {
  margin-top: 22rpx;
  color: #929f9a;
  font-size: 20rpx;
  text-align: center;
}
</style>
