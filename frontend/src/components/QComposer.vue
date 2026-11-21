<template>
  <view class="composer-wrap">
    <view v-if="label" class="composer-label">{{ label }}</view>
    <view class="composer" :class="{ 'composer-invalid': error, 'composer-busy': pending }">
      <textarea
        class="message-input"
        :value="modelValue"
        :placeholder="placeholder || '描述你的不适，或写下想了解的健康问题…'"
        :maxlength="2000"
        :disabled="pending"
        :auto-height="false"
        :adjust-position="true"
        :aria-label="label || '输入咨询内容'"
        @input="updateValue"
      />
      <view class="composer-bottom">
        <view class="anonymous"><QIcon name="shield" /><text>{{ contextLabel || '本机演示' }}</text></view>
        <button class="send-button" :class="{ 'send-round': compact }" :disabled="pending" :aria-label="pending ? '正在整理' : '发送消息'" @click="$emit('send')">
          <text v-if="!compact">{{ pending ? '正在整理' : '开始咨询' }}</text>
          <QIcon :name="pending ? 'clock' : 'send'" />
        </button>
      </view>
    </view>
    <text v-if="error" class="input-error" role="alert">{{ error }}</text>
  </view>
</template>

<script setup lang="ts">
import QIcon from '@/components/QIcon.vue'

defineProps<{
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
}>()

function updateValue(event: unknown) {
  const input = event as { detail: { value: string } }
  emit('update:modelValue', input.detail.value)
}
</script>

<style scoped>
.composer-wrap { width: 100%; }
.composer-label {
  position: relative;
  z-index: 1;
  display: inline-block;
  margin: 0 0 calc(-16 * var(--u, 1px)) calc(24 * var(--u, 1px));
  padding: calc(15 * var(--u, 1px)) calc(18 * var(--u, 1px));
  border-radius: calc(22 * var(--u, 1px)) calc(22 * var(--u, 1px)) calc(22 * var(--u, 1px)) 2px;
  background: #e3edff;
  color: #304e80;
  font-size: clamp(14px, calc(20 * var(--u, 1px)), 24px);
  font-weight: 600;
  line-height: 1.4;
}
.composer {
  display: flex;
  flex-direction: column;
  height: var(--composer-height, 190px);
  min-height: 116px;
  box-sizing: border-box;
  padding: max(12px, calc(24 * var(--u, 1px)));
  border: 1px solid #dbe5f4;
  border-radius: calc(24 * var(--u, 1px));
  background: #ffffffed;
  box-shadow: 0 8px 35px #2a4f8a0c;
  transition: border-color .2s, box-shadow .2s;
}
.composer:focus-within { border-color: #7ca9ef; box-shadow: 0 0 0 2px #347be51c, 0 8px 35px #2a4f8a0c; }
.composer-invalid { border-color: #ad553d; }
.message-input { flex: 1; width: 100%; height: 0; min-height: 30px; color: #293653; font-size: clamp(14px, calc(20 * var(--u, 1px)), 26px); line-height: 1.6; }
.composer-bottom { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; gap: 12px; margin-top: max(7px, calc(12 * var(--u, 1px))); }
.anonymous { display: flex; align-items: center; gap: 7px; padding: calc(11 * var(--u, 1px)) calc(14 * var(--u, 1px)); border: 1px dashed #dce6f4; border-radius: 30px; color: #5c6e8b; font-size: clamp(12px, calc(16 * var(--u, 1px)), 20px); }
.anonymous .q-icon { width: max(16px, calc(22 * var(--u, 1px))); height: max(16px, calc(22 * var(--u, 1px))); opacity: .65; }
.send-button { display: flex; align-items: center; justify-content: center; gap: calc(12 * var(--u, 1px)); width: calc(205 * var(--u, 1px)); min-width: 110px; height: max(38px, calc(66 * var(--u, 1px))); padding: 0 12px; margin: 0; border-radius: calc(26 * var(--u, 1px)); background: #293958; color: #fff; font-size: clamp(14px, calc(22 * var(--u, 1px)), 26px); font-weight: 600; line-height: 1.4; }
.send-button { transition: background-color 220ms ease, box-shadow 220ms ease, transform 160ms ease; }
.send-button:active { transform: scale(.94); }
.send-button::after { border: 0; }
.send-button .q-icon { width: max(18px, calc(24 * var(--u, 1px))); height: max(18px, calc(24 * var(--u, 1px))); filter: brightness(0) invert(1); }
.send-button:hover { background: #344c7b; }
.send-button[disabled] { background: #dbe5f5; color: #687f9f; }
.send-button[disabled] .q-icon { filter: none; }
.send-round { width: max(44px, calc(48 * var(--u, 1px))); min-width: 0; height: max(44px, calc(48 * var(--u, 1px))); padding: 0; border-radius: 50%; }
.input-error { display: block; color: #ad553d; font-size: 14px; margin-top: 10px; }
@media (max-width: 1000px) {
  .composer { padding: 22px 20px 16px; border-radius: 18px; }
  .message-input { font-size: 16px; }
  .composer-label { margin-bottom: -12px; padding: 10px 16px; border-radius: 14px 14px 14px 2px; font-size: 15px; }
  .send-button { min-width: 125px; height: 46px; border-radius: 22px; }
  .send-round { min-width: 0; width: 44px; height: 44px; }
}
@media (max-width: 600px) {
  .composer { padding: 20px 15px 14px; border-radius: 16px; }
  .composer-label { margin-left: 15px; font-size: 14px; }
  .anonymous { padding: 5px 8px; font-size: 12px; }
}
</style>
