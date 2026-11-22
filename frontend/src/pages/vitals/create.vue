<template>
  <view class="vital-page">
    <view class="vital-shell">
      <header class="header">
        <button class="back" @click="goBack">←</button>
        <view>
          <text class="title">录入血压</text>
          <text class="subtitle">记录后会更新健康档案与趋势</text>
        </view>
      </header>

      <view class="form-card">
        <view class="reading-preview">
          <text class="preview-value">{{ systolic || '--' }}/{{ diastolic || '--' }}</text>
          <text class="preview-label">mmHg</text>
        </view>

        <view class="form-row">
          <view class="field">
            <text class="label">收缩压</text>
            <input v-model.number="systolic" class="input" type="number" placeholder="60–260" />
          </view>
          <view class="field">
            <text class="label">舒张压</text>
            <input v-model.number="diastolic" class="input" type="number" placeholder="30–160" />
          </view>
          <view class="field">
            <text class="label">脉搏</text>
            <input v-model.number="pulse" class="input" type="number" placeholder="选填" />
          </view>
        </view>

        <view class="form-row">
          <view class="field">
            <text class="label">测量日期</text>
            <picker mode="date" :value="measuredDate" @change="changeDate">
              <view class="picker-value">{{ measuredDate }}</view>
            </picker>
          </view>
          <view class="field">
            <text class="label">测量时间</text>
            <picker mode="time" :value="measuredTime" @change="changeTime">
              <view class="picker-value">{{ measuredTime }}</view>
            </picker>
          </view>
        </view>

        <text v-if="errorText" class="error-text">{{ errorText }}</text>
        <button class="primary" :loading="loading" @click="save">保存血压记录</button>
        <text class="tip">请按规范方法测量；单次数据不能替代医生判断。</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'

const store = useWorkspaceStore()
const now = new Date()
const pad = (value: number) => String(value).padStart(2, '0')
const measuredDate = ref(`${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`)
const measuredTime = ref(`${pad(now.getHours())}:${pad(now.getMinutes())}`)
const systolic = ref<number | string>('')
const diastolic = ref<number | string>('')
const pulse = ref<number | string>('')
const loading = ref(false)
const errorText = ref('')

function changeDate(event: { detail: { value: string } }) {
  measuredDate.value = event.detail.value
}

function changeTime(event: { detail: { value: string } }) {
  measuredTime.value = event.detail.value
}

async function save() {
  errorText.value = ''
  const sys = Number(systolic.value)
  const dia = Number(diastolic.value)
  const hr = pulse.value === '' ? undefined : Number(pulse.value)
  if (!Number.isFinite(sys) || !Number.isFinite(dia)) {
    errorText.value = '请填写收缩压和舒张压。'
    return
  }

  loading.value = true
  try {
    const response = await store.addBloodPressure({
      measured_at: `${measuredDate.value} ${measuredTime.value}:00`,
      systolic: sys,
      diastolic: dia,
      ...(hr ? { pulse: hr } : {}),
    })
    if (response.demo) {
      errorText.value = '当前为预览模式，不会写入真实档案。'
      return
    }
    uni.showToast({ title: '血压记录已保存', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 500)
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '保存失败'
  } finally {
    loading.value = false
  }
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.vital-page {
  min-height: 100vh;
  padding: 34px 24px 60px;
  background: #eff9f5;
  box-sizing: border-box;
}

.vital-shell {
  width: min(720px, 100%);
  margin: 0 auto;
}

.header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.back {
  width: 38px;
  height: 38px;
  margin: 0;
  padding: 0;
  border-radius: 12px;
  background: #ffffff;
  color: #347663;
  font-size: 18px;
}

.title,
.subtitle,
.preview-value,
.preview-label,
.label,
.error-text,
.tip {
  display: block;
}

.title {
  color: #21483c;
  font-size: 25px;
  font-weight: 800;
}

.subtitle {
  margin-top: 3px;
  color: #7f978e;
  font-size: 10px;
}

.form-card {
  margin-top: 24px;
  padding: 24px;
  border: 1px solid #deeee7;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 16px 40px rgba(67, 139, 119, 0.06);
}

.reading-preview {
  padding: 20px;
  border-radius: 15px;
  background: linear-gradient(135deg, #d8f3e9, #bfe9dc);
  text-align: center;
}

.preview-value {
  color: #245a49;
  font-size: 34px;
  font-weight: 800;
}

.preview-label {
  margin-top: 3px;
  color: #5b7d70;
  font-size: 9px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}

.form-row + .form-row {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.label {
  margin-bottom: 7px;
  color: #476158;
  font-size: 10px;
  font-weight: 700;
}

.input,
.picker-value {
  width: 100%;
  height: 42px;
  padding: 0 11px;
  border: 1px solid #d4e8df;
  border-radius: 10px;
  background: #fbfefc;
  color: #29483d;
  font-size: 11px;
  line-height: 42px;
  box-sizing: border-box;
}

.error-text {
  margin-top: 15px;
  padding: 10px 12px;
  border-radius: 9px;
  background: #fff6f2;
  color: #a35d49;
  font-size: 10px;
}

.primary {
  margin-top: 20px;
  border-radius: 11px;
  background: #4ba58d;
  color: #ffffff;
  font-size: 12px;
}

.tip {
  margin-top: 11px;
  color: #94a39d;
  font-size: 9px;
  text-align: center;
}

@media (max-width: 620px) {
  .vital-page {
    padding: 20px 14px 40px;
  }

  .form-row,
  .form-row + .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
