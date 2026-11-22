<template>
  <view class="med-page">
    <view class="med-shell">
      <header class="header">
        <button class="back" @click="goBack">←</button>
        <view>
          <text class="title">用药管理</text>
          <text class="subtitle">仅记录用户提供的用药，不推荐处方或剂量</text>
        </view>
        <button class="add-toggle" @click="showForm = !showForm">
          {{ showForm ? '收起' : '添加用药' }}
        </button>
      </header>

      <view v-if="showForm" class="form-card">
        <view class="form-grid">
          <view class="field">
            <text class="label">药品名称</text>
            <input v-model="form.name" class="input" placeholder="例如：氨氯地平" />
          </view>
          <view class="field">
            <text class="label">剂量说明</text>
            <input v-model="form.dosage_text" class="input" placeholder="例如：1 片" />
          </view>
          <view class="field">
            <text class="label">服用频次</text>
            <input v-model="form.frequency_text" class="input" placeholder="例如：一天一次" />
          </view>
          <view class="field">
            <text class="label">开始日期</text>
            <picker mode="date" :value="form.started_on" @change="changeStartedOn">
              <view class="picker-value">{{ form.started_on }}</view>
            </picker>
          </view>
        </view>
        <text v-if="errorText" class="error-text">{{ errorText }}</text>
        <button class="primary" :loading="saving" @click="saveMedication">保存用药记录</button>
      </view>

      <view class="list-card">
        <view v-if="loading" class="empty">正在读取用药记录…</view>
        <view v-else-if="!records.length" class="empty">暂无用用药记录</view>
        <view v-for="item in records" :key="item.id" class="med-row">
          <view class="med-icon">药</view>
          <view class="med-main">
            <view class="med-title-row">
              <text class="med-name">{{ item.name }}</text>
              <text class="med-status">{{ statusLabel(item.status) }}</text>
            </view>
            <text class="med-detail">
              {{ [item.dosage_text, item.frequency_text].filter(Boolean).join(' · ') || '未填写用法' }}
            </text>
            <text class="med-date">{{ item.started_on }} 开始</text>
          </view>
          <button
            v-if="item.status === 'active'"
            class="stop-button"
            @click="stopMedication(item)"
          >
            停用
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createMedication,
  getMedications,
  updateMedication,
  type Medication,
} from '@/api/medications'

const records = ref<Medication[]>([])
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const errorText = ref('')
const today = new Date().toISOString().slice(0, 10)
const form = reactive({
  name: '',
  dosage_text: '',
  frequency_text: '',
  started_on: today,
})

onMounted(load)

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    records.value = (await getMedications()).records
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '读取用药记录失败'
  } finally {
    loading.value = false
  }
}

function changeStartedOn(event: { detail: { value: string } }) {
  form.started_on = event.detail.value
}

async function saveMedication() {
  if (!form.name.trim()) {
    errorText.value = '请填写药品名称。'
    return
  }
  saving.value = true
  errorText.value = ''
  try {
    await createMedication({
      name: form.name.trim(),
      dosage_text: form.dosage_text.trim() || undefined,
      frequency_text: form.frequency_text.trim() || undefined,
      kind: 'long_term',
      started_on: form.started_on,
    })
    form.name = ''
    form.dosage_text = ''
    form.frequency_text = ''
    showForm.value = false
    await load()
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '保存用药记录失败'
  } finally {
    saving.value = false
  }
}

async function stopMedication(item: Medication) {
  try {
    await updateMedication(item.id, { status: 'stopped' })
    await load()
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : '停用失败',
      icon: 'none',
    })
  }
}

function statusLabel(status: Medication['status']) {
  return { active: '使用中', stopped: '已停用', expired: '已过期' }[status]
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.med-page {
  min-height: 100vh;
  padding: 32px 24px 60px;
  background: #eff9f5;
  box-sizing: border-box;
}

.med-shell {
  width: min(880px, 100%);
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

.header > view {
  min-width: 0;
  flex: 1;
}

.title,
.subtitle,
.label,
.error-text,
.empty,
.med-name,
.med-detail,
.med-date {
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

.add-toggle {
  width: auto;
  margin: 0;
  padding: 0 14px;
  border-radius: 10px;
  background: #4ba58d;
  color: #ffffff;
  font-size: 10px;
  line-height: 38px;
}

.form-card,
.list-card {
  margin-top: 20px;
  padding: 22px;
  border: 1px solid #deeee7;
  border-radius: 17px;
  background: #ffffff;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
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

.primary {
  margin-top: 16px;
  border-radius: 10px;
  background: #4ba58d;
  color: #ffffff;
  font-size: 11px;
}

.error-text {
  margin-top: 12px;
  padding: 9px 11px;
  border-radius: 8px;
  background: #fff6f2;
  color: #a35d49;
  font-size: 10px;
}

.empty {
  padding: 32px 0;
  color: #8ea099;
  font-size: 11px;
  text-align: center;
}

.med-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 15px 0;
  border-bottom: 1px solid #edf2ef;
}

.med-row:last-child {
  border-bottom: 0;
}

.med-icon {
  display: flex;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #e2f4ed;
  color: #347862;
  font-size: 11px;
  font-weight: 800;
}

.med-main {
  min-width: 0;
  flex: 1;
}

.med-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.med-name {
  color: #2d5044;
  font-size: 12px;
  font-weight: 800;
}

.med-status {
  padding: 3px 7px;
  border-radius: 999px;
  background: #edf7f2;
  color: #4c7c6b;
  font-size: 8px;
}

.med-detail {
  margin-top: 5px;
  color: #6d837a;
  font-size: 10px;
}

.med-date {
  margin-top: 3px;
  color: #9aa7a2;
  font-size: 8px;
}

.stop-button {
  width: auto;
  margin: 0;
  padding: 0 10px;
  border: 1px solid #ebd8cf;
  border-radius: 8px;
  background: #fffaf8;
  color: #a06450;
  font-size: 8px;
  line-height: 28px;
}

@media (max-width: 650px) {
  .med-page {
    padding: 20px 14px 40px;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
