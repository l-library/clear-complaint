<template>
  <view class="composer-wrap">
    <view v-if="label" class="composer-label">{{ label }}</view>
    <view class="composer" :class="{ 'composer-invalid': error, 'composer-busy': pending }">
      <textarea
        class="message-input"
        :value="modelValue"
        :placeholder="placeholder || '描述你的不适…'"
        :maxlength="2000"
        :disabled="pending"
        :auto-height="false"
        :adjust-position="true"
        :focus="focused"
        :aria-label="label || contextLabel || '输入咨询内容'"
        @input="updateValue"
        @blur="focused = false"
        @keydown="handleKeydown"
      />
      <view class="composer-bottom">
        <view class="composer-controls">
          <button role="button" tabindex="0" @keydown="activateButton" v-if="compact" class="utility-button" aria-label="添加健康资料" @click="$emit('attach')"><QIcon name="plus" /></button>
          <button role="button" tabindex="0" @keydown="activateButton" class="privacy-button" :class="{ 'utility-button': compact, 'anonymous': !compact }" aria-label="账户与隐私说明" @click="showPrivacy"><QIcon name="anonymous" /><text v-if="!compact">隐私保护</text></button>
        </view>
        <button role="button" tabindex="0" @keydown="activateButton" class="send-button" :class="{ 'send-round': compact }" :disabled="pending" :aria-label="pending ? '正在整理' : '发送消息'" @click="$emit('send')">
          <text v-if="!compact">{{ pending ? '正在整理…' : '开始交流' }}</text>
          <QIcon :name="pending ? 'clock' : compact ? 'send' : 'arrow-right'" />
        </button>
      </view>
    </view>
    <text v-if="error" class="input-error" role="alert">{{ error }}</text>
  </view>
</template>

<script setup lang="ts">
import { activateButton } from '@/components/buttonKeyboard'
import { nextTick, ref } from 'vue'
import QIcon from '@/components/QIcon.vue'

const props = defineProps<{
  modelValue: string
  label?: string
  placeholder?: string
  contextLabel?: string
  compact?: boolean
  pending?: boolean
  error?: string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'send'): void
  (e: 'attach'): void
}>()
const focused = ref(false)

function updateValue(event: unknown) {
  const input = event as { detail: { value: string } }
  emit('update:modelValue', input.detail.value)
}

function handleKeydown(event: KeyboardEvent) {
  // #ifdef H5
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    if (!props.pending) emit('send')
  }
  // #endif
}

async function focus() {
  focused.value = false
  await nextTick()
  focused.value = true
}

function showPrivacy() {
  uni.showModal({ title: '账户与隐私', content: '登录后，提交的信息由清诉处理并保存在你的账户中。可在账户信息中导出、清空数据或注销账户。', showCancel: false })
}

defineExpose({ focus })
</script>

<style scoped>
.composer-wrap { width: 100%; }
.composer-label { position: relative; z-index: 2; display: inline-block; margin: 0 0 calc(-16 * var(--u, 1px)) max(15px, calc(24 * var(--u, 1px))); padding: max(10px, calc(15 * var(--u, 1px))) max(14px, calc(18 * var(--u, 1px))); border-radius: max(18px, calc(28 * var(--u, 1px))) max(18px, calc(28 * var(--u, 1px))) max(18px, calc(28 * var(--u, 1px))) 2px; background: #ebffbd; color: #1b1b18; font-size: clamp(14px, calc(20 * var(--u, 1px)), 24px); font-weight: 600; line-height: 1.4; }
.composer { display: flex; flex-direction: column; height: var(--composer-height, 190px); min-height: 94px; box-sizing: border-box; padding: max(12px, calc(24 * var(--u, 1px))); border: 1px solid #e9e9e4; border-radius: max(16px, calc(24 * var(--u, 1px))); background: #fff; box-shadow: 0 8px 36px #1b1b1806; transition: border-color .18s, box-shadow .18s; }
.composer:focus-within { border-color: #4b85ff; box-shadow: 0 0 0 2px #2463eb20, 0 8px 36px #1b1b1806; }
.composer-invalid { border-color: #b54a3e; }
.message-input { flex: 1; width: 100%; height: 0; min-height: 25px; color: #1b1b18; font-family: var(--font-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif); font-size: clamp(14px, calc(22 * var(--u, 1px)), 26px); line-height: 1.6; }
.message-input :deep(textarea) { padding: 0; outline: 0; }
.message-input :deep(textarea:focus-visible) { outline: 0; }
.message-input :deep(.uni-textarea-placeholder) { color: #767674; }
.composer-bottom { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; gap: 12px; margin-top: max(9px, calc(12 * var(--u, 1px))); }
.composer-controls { display: flex; align-items: center; gap: max(10px, calc(18 * var(--u, 1px))); }
.utility-button { display: flex; align-items: center; justify-content: center; width: max(28px, calc(46 * var(--u, 1px))); height: max(28px, calc(46 * var(--u, 1px))); padding: 0; margin: 0; border: 1px solid #ededE8; border-radius: 50%; background: #fff; }
.utility-button .q-icon { width: max(21px, calc(28 * var(--u, 1px))); height: max(21px, calc(28 * var(--u, 1px))); }
.utility-button:hover { background: #f5f5f0; }
.anonymous { display: flex; align-items: center; gap: 7px; padding: max(7px, calc(11 * var(--u, 1px))) max(10px, calc(14 * var(--u, 1px))); margin: 0; border: 1px dashed #e9e9e4; border-radius: 30px; background: #fff; color: #2463eb; font-size: clamp(12px, calc(16 * var(--u, 1px)), 20px); line-height: 1.3; }
.anonymous .q-icon { width: max(18px, calc(24 * var(--u, 1px))); height: max(18px, calc(24 * var(--u, 1px))); filter: invert(29%) sepia(96%) saturate(3590%) hue-rotate(218deg) brightness(98%) contrast(88%); }
.send-button { display: flex; align-items: center; justify-content: center; gap: max(9px, calc(12 * var(--u, 1px))); width: max(135px, calc(205 * var(--u, 1px))); height: max(44px, calc(66 * var(--u, 1px))); padding: 0 16px; margin: 0; border-radius: 50px; background: #2463eb; color: #fff; font-size: clamp(14px, calc(22 * var(--u, 1px)), 26px); font-weight: 600; line-height: 1.4; box-shadow: 0 4px 8px #2463eb30; transition: background-color .18s, box-shadow .18s, transform .16s; }
.send-button:active { transform: scale(.94); }
.send-button .q-icon { width: max(18px, calc(24 * var(--u, 1px))); height: max(18px, calc(24 * var(--u, 1px))); filter: brightness(0) invert(1); }
.send-button:hover { background: #1955dc; box-shadow: 0 5px 12px #2463eb38; }
.send-button[disabled] { background: #e4e4df; color: #767674; box-shadow: none; }
.send-button[disabled] .q-icon { filter: none; opacity: .45; }
.send-round { width: max(28px, calc(48 * var(--u, 1px))); height: max(28px, calc(48 * var(--u, 1px))); padding: 0; border-radius: 50%; }
.input-error { display: block; color: #ad4035; font-size: 13px; margin-top: 10px; line-height: 1.6; }
@media (pointer: coarse) { .utility-button, .send-round { width: 44px; height: 44px; } }
@media (max-width: 600px) { .composer { padding: 17px 16px 14px; } .message-input { font-size: 16px; } .composer-label { margin-bottom: -12px; } .utility-button, .send-round { width: 44px; height: 44px; } }
</style>
