<template>
  <view
    v-if="visible"
    class="message-transition"
    :class="{ 'is-moving': moving }"
    :style="boxStyle"
    aria-hidden="true"
  >
    <text class="transition-content">{{ content }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'

interface MessageRect {
  left: number
  top: number
  width: number
  height: number
}

const emit = defineEmits<{ (e: 'complete'): void }>()
const visible = ref(false)
const moving = ref(false)
const content = ref('')
const box = ref<MessageRect>({ left: 0, top: 0, width: 0, height: 0 })
const boxStyle = computed(() => ({
  left: `${box.value.left}px`,
  top: `${box.value.top}px`,
  width: `${box.value.width}px`,
  height: `${box.value.height}px`,
}))

let moveTimer: ReturnType<typeof setTimeout> | undefined
let completionTimer: ReturnType<typeof setTimeout> | undefined
let currentRun = 0

function clearTimers() {
  if (moveTimer !== undefined) clearTimeout(moveTimer)
  if (completionTimer !== undefined) clearTimeout(completionTimer)
  moveTimer = undefined
  completionTimer = undefined
}

function complete() {
  clearTimers()
  visible.value = false
  moving.value = false
  emit('complete')
}

function hasValidSize(rect: MessageRect) {
  return [rect.left, rect.top, rect.width, rect.height].every(Number.isFinite)
    && rect.width > 0 && rect.height > 0
}

async function play(message: string, origin: MessageRect, target: MessageRect) {
  clearTimers()
  const run = ++currentRun
  let reducedMotion = false
  // #ifdef H5
  reducedMotion = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  // #endif

  if (reducedMotion || !message || !hasValidSize(origin) || !hasValidSize(target)) {
    complete()
    return
  }

  content.value = message
  box.value = { ...origin }
  moving.value = false
  visible.value = true
  await nextTick()
  if (run !== currentRun) return

  // The origin needs one painted frame before applying the destination styles.
  moveTimer = setTimeout(() => {
    moving.value = true
    box.value = { ...target }
    completionTimer = setTimeout(complete, 620)
  }, 20)
}

onBeforeUnmount(() => {
  currentRun += 1
  clearTimers()
})

defineExpose({ play })
</script>

<style scoped>
.message-transition {
  position: fixed;
  z-index: 1000;
  pointer-events: none;
  box-sizing: border-box;
  overflow: hidden;
  padding: max(12px, calc(24 * var(--u, 1px)));
  border: 1px solid #dce5f2;
  border-radius: calc(24 * var(--u, 1px));
  color: #30466c;
  background: #fff;
  box-shadow: 0 12px 32px #2a4f8a12;
  will-change: left, top, width, height;
}

.is-moving {
  padding: calc(24 * var(--u, 1px));
  border-color: transparent;
  border-radius: calc(24 * var(--u, 1px)) calc(5 * var(--u, 1px)) calc(24 * var(--u, 1px)) calc(24 * var(--u, 1px));
  background: #e7f0ff;
  box-shadow: 0 2px 8px #2a4f8a00;
  transition:
    left 600ms cubic-bezier(.22, 1, .36, 1),
    top 600ms cubic-bezier(.22, 1, .36, 1),
    width 600ms cubic-bezier(.22, 1, .36, 1),
    height 600ms cubic-bezier(.22, 1, .36, 1),
    padding 600ms cubic-bezier(.22, 1, .36, 1),
    border-radius 600ms cubic-bezier(.22, 1, .36, 1),
    border-color 600ms ease,
    background-color 600ms ease,
    box-shadow 600ms ease;
}

.transition-content {
  display: block;
  font-size: clamp(14px, calc(20 * var(--u, 1px)), 26px);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.is-moving .transition-content {
  font-size: clamp(15px, calc(24 * var(--u, 1px)), 28px);
  line-height: 1.65;
  transition: font-size 600ms cubic-bezier(.22, 1, .36, 1), line-height 600ms ease;
}

@media (max-width: 1000px) {
  .message-transition { padding: 22px 20px; border-radius: 18px; }
  .is-moving { padding: 12px 16px; border-radius: 16px 3px 16px 16px; }
  .transition-content, .is-moving .transition-content { font-size: 16px; }
}

@media (prefers-reduced-motion: reduce) {
  .is-moving {
    transition: none;
  }
}
</style>
