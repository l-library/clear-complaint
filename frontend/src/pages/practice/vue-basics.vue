<template>
  <view class="page">
    <view class="card">
      <text class="eyebrow">VUE 02 · 新手练习</text>
      <text class="heading">模拟健康咨询</text>
      <text class="intro">
        输入一句症状描述，点击发送。这个页面暂时不调用后端，只练习 Vue 的输入、按钮、条件和列表。
      </text>

      <textarea
        v-model="question"
        class="question-input"
        maxlength="200"
        placeholder="例如：这两天有点头晕"
      />

      <view class="quick-list">
        <button
          v-for="item in quickQuestions"
          :key="item"
          class="quick-button"
          @click="chooseQuestion(item)"
        >
          {{ item }}
        </button>
      </view>

      <button class="send-button" :disabled="loading" @click="sendQuestion">
        {{ loading ? '正在模拟…' : '发送问题' }}
      </button>

      <view v-if="answer" class="answer-card">
        <text class="answer-label">模拟回答</text>
        <text class="answer-text">{{ answer }}</text>
      </view>

      <view v-if="suggestions.length" class="suggestion-card">
        <text class="answer-label">需要继续确认</text>
        <view
          v-for="(item, index) in suggestions"
          :key="item"
          class="suggestion-item"
        >
          <text class="suggestion-number">{{ index + 1 }}</text>
          <text>{{ item }}</text>
        </view>
      </view>

      <text class="notice">这是前端模拟页面，不构成医疗建议。</text>
    </view>

    <button class="back-button" @click="goBack">返回首页</button>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const question = ref('')
const answer = ref('')
const loading = ref(false)
const suggestions = ref<string[]>([])

const quickQuestions = [
  '这两天有点头晕',
  '我想把降压药停两天',
  '没有其他不舒服',
]

function chooseQuestion(text: string) {
  question.value = text
}

function sendQuestion() {
  const text = question.value.trim()

  if (!text) {
    answer.value = '请先输入您现在的不适或想咨询的问题。'
    suggestions.value = []
    return
  }

  loading.value = true
  answer.value = `已收到：“${text}”。当前是 Vue 练习页，后续会由后端 Agent 生成真实的分诊建议。`

  if (text.includes('停药') || text.includes('药停')) {
    suggestions.value = [
      '最近一次测量血压是多少？',
      '有没有头晕、胸闷或其他不舒服？',
      '停药前是否咨询过医生？',
    ]
  } else {
    suggestions.value = [
      '这种情况持续多久了？',
      '有没有其他伴随症状？',
      '最近是否测量过血压？',
    ]
  }

  loading.value = false
}

function goBack() {
  uni.navigateBack()
}
</script>

<style>
.page {
  min-height: 100vh;
  padding: 40rpx 28rpx 70rpx;
  background: #f2f5f3;
  box-sizing: border-box;
}

.card {
  padding: 38rpx 30rpx;
  border-radius: 24rpx;
  background: #ffffff;
  box-shadow: 0 16rpx 50rpx rgba(17, 62, 48, 0.08);
}

.eyebrow {
  display: block;
  color: #0c6f5a;
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
}

.heading {
  display: block;
  margin-top: 16rpx;
  color: #173a30;
  font-size: 46rpx;
  font-weight: 700;
}

.intro {
  display: block;
  margin-top: 18rpx;
  color: #62736d;
  font-size: 27rpx;
  line-height: 1.75;
}

.question-input {
  width: 100%;
  height: 210rpx;
  margin-top: 28rpx;
  padding: 24rpx;
  border: 2rpx solid #dce7e2;
  border-radius: 16rpx;
  background: #f8faf9;
  color: #213b32;
  font-size: 28rpx;
  box-sizing: border-box;
}

.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 18rpx;
}

.quick-button {
  width: auto;
  margin: 0;
  padding: 0 20rpx;
  border: 1rpx solid #cfe1da;
  border-radius: 999rpx;
  background: #f3f8f6;
  color: #37665a;
  font-size: 23rpx;
  line-height: 62rpx;
}

.send-button {
  margin-top: 26rpx;
  border-radius: 14rpx;
  background: #0c6f5a;
  color: #ffffff;
  font-size: 29rpx;
}

.answer-card,
.suggestion-card {
  margin-top: 24rpx;
  padding: 24rpx;
  border-radius: 16rpx;
}

.answer-card {
  background: #eaf5f1;
}

.suggestion-card {
  border: 1rpx dashed #d8c78e;
  background: #fffaf0;
}

.answer-label {
  display: block;
  color: #2d5c50;
  font-size: 23rpx;
  font-weight: 700;
}

.answer-text {
  display: block;
  margin-top: 12rpx;
  color: #24463d;
  font-size: 27rpx;
  line-height: 1.7;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-top: 14rpx;
  color: #5c573e;
  font-size: 26rpx;
  line-height: 1.6;
}

.suggestion-number {
  display: flex;
  flex: 0 0 34rpx;
  width: 34rpx;
  height: 34rpx;
  align-items: center;
  justify-content: center;
  margin-top: 3rpx;
  border-radius: 50%;
  background: #f0df9e;
  color: #67510b;
  font-size: 20rpx;
  font-weight: 700;
}

.notice {
  display: block;
  margin-top: 26rpx;
  color: #929d99;
  font-size: 22rpx;
  text-align: center;
}

.back-button {
  margin-top: 28rpx;
  border: 1rpx solid #c7d8d1;
  border-radius: 14rpx;
  background: transparent;
  color: #4d6f65;
  font-size: 26rpx;
}
</style>
