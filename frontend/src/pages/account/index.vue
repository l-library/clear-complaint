<template>
  <view class="account-page">
    <view class="account-shell">
      <header class="header">
        <button class="back" @click="goBack">←</button>
        <view>
          <text class="title">数据与账户</text>
          <text class="subtitle">导出、清理和删除真实后端中的数据</text>
        </view>
      </header>

      <view class="info-card">
        <text class="card-title">当前账户</text>
        <text class="phone">{{ auth.user?.phone || '未登录' }}</text>
        <text class="info-text">
          数据导出包含档案、体征、用药、问诊、证据引用、随访和提醒。
        </text>
      </view>

      <view class="action-card">
        <view class="action-copy">
          <text class="action-title">导出全部数据</text>
          <text class="action-text">生成一次性下载链接，24 小时内有效。</text>
        </view>
        <button class="action-button" :loading="exporting" @click="exportData">导出</button>
      </view>

      <view class="action-card danger-zone">
        <view class="action-copy">
          <text class="action-title">清空健康数据</text>
          <text class="action-text">删除档案、问诊、提醒等数据，但保留账户。</text>
        </view>
        <button class="action-button danger" @click="clearData">清空</button>
      </view>

      <view class="action-card danger-zone">
        <view class="action-copy">
          <text class="action-title">注销账户</text>
          <text class="action-text">全部数据硬删除，无法恢复，所有登录令牌立即失效。</text>
        </view>
        <button class="action-button danger" @click="removeAccount">注销</button>
      </view>

      <text v-if="message" class="message" :class="{ error: isError }">{{ message }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { clearAccountData, deleteAccount, exportAccountData } from '@/api/account'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const exporting = ref(false)
const message = ref('')
const isError = ref(false)

async function exportData() {
  exporting.value = true
  message.value = ''
  try {
    const response = await exportAccountData()
    // #ifdef H5
    window.open(response.url, '_blank', 'noopener,noreferrer')
    // #endif
    // #ifndef H5
    uni.setClipboardData({ data: response.url })
    // #endif
    message.value = `导出包已生成，有效期至 ${response.expires_at}`
    isError.value = false
  } catch (error) {
    message.value = error instanceof Error ? error.message : '导出失败'
    isError.value = true
  } finally {
    exporting.value = false
  }
}

async function clearData() {
  const confirmed = await askDelete('清空健康数据后无法恢复，确认继续？')
  if (!confirmed) return
  try {
    const response = await clearAccountData()
    message.value = `已清空：问诊 ${response.cleared.episodes}，体征 ${response.cleared.vitals}，用药 ${response.cleared.medications}，提醒 ${response.cleared.reminders}`
    isError.value = false
  } catch (error) {
    message.value = error instanceof Error ? error.message : '清空失败'
    isError.value = true
  }
}

async function removeAccount() {
  const confirmed = await askDelete('账户和全部数据将被永久删除，确认注销？')
  if (!confirmed) return
  try {
    await deleteAccount()
    auth.clearLocalSession()
    uni.reLaunch({ url: '/pages/auth/index' })
  } catch (error) {
    message.value = error instanceof Error ? error.message : '注销失败'
    isError.value = true
  }
}

function askDelete(content: string) {
  return new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '高风险操作',
      content,
      confirmText: '删除',
      confirmColor: '#b45f4d',
      success: (result) => resolve(result.confirm),
      fail: () => resolve(false),
    })
  })
}

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.account-page {
  min-height: 100vh;
  padding: 32px 24px 60px;
  background: #eff9f5;
  box-sizing: border-box;
}

.account-shell {
  width: min(760px, 100%);
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
.card-title,
.phone,
.info-text,
.action-title,
.action-text,
.message {
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

.info-card,
.action-card {
  margin-top: 18px;
  padding: 20px;
  border: 1px solid #deeee7;
  border-radius: 16px;
  background: #ffffff;
}

.card-title {
  color: #70877d;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1px;
}

.phone {
  margin-top: 8px;
  color: #245c4b;
  font-size: 22px;
  font-weight: 800;
}

.info-text,
.action-text {
  margin-top: 7px;
  color: #7f9189;
  font-size: 10px;
  line-height: 1.65;
}

.action-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.action-copy {
  min-width: 0;
  flex: 1;
}

.action-title {
  color: #2c5043;
  font-size: 12px;
  font-weight: 800;
}

.action-button {
  width: auto;
  flex: 0 0 auto;
  margin: 0;
  padding: 0 16px;
  border-radius: 9px;
  background: #4ba58d;
  color: #ffffff;
  font-size: 10px;
  line-height: 36px;
}

.action-button.danger {
  background: #b86651;
}

.danger-zone {
  border-color: #f0dfd8;
}

.message {
  margin-top: 16px;
  padding: 11px 13px;
  border-radius: 10px;
  background: #e8f6f0;
  color: #38755f;
  font-size: 10px;
  line-height: 1.55;
}

.message.error {
  background: #fff5f2;
  color: #a35d49;
}
</style>
