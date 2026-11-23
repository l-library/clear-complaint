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
const offset = ref({ x: 0, y: 0 })
const boxStyle = computed(() => ({
  left: `${box.value.left}px`,
  top: `${box.value.top}px`,
  width: `${box.value.width}px`,
  height: `${box.value.height}px`,
  transform: moving.value ? 'translate3d(0, 0, 0)' : `translate3d(${offset.value.x}px, ${offset.value.y}px, 0)`,
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
  box.value = { ...target }
  offset.value = { x: origin.left + 18 - target.left, y: origin.top + 18 - target.top }
  moving.value = false
  visible.value = true
  await nextTick()
  if (run !== currentRun) return

  // The origin needs one painted frame before applying the destination styles.
  moveTimer = setTimeout(() => {
    moving.value = true
    completionTimer = setTimeout(complete, 440)
  }, 20)
}

onBeforeUnmount(() => {
  currentRun += 1
  clearTimers()
})

defineExpose({ play })
</script>

<style scoped>
.message-transition { position: fixed; z-index: 1000; pointer-events: none; box-sizing: border-box; overflow: hidden; padding: max(12px, calc(24 * var(--u, 1px))); border-radius: max(18px, calc(24 * var(--u, 1px))) 4px max(18px, calc(24 * var(--u, 1px))) max(18px, calc(24 * var(--u, 1px))); color: #1b1b18; background: #f0f5ff; will-change: transform; }
.is-moving { transition: transform 420ms cubic-bezier(.22, 1, .36, 1); }
.transition-content { display: block; font-size: clamp(15px, calc(24 * var(--u, 1px)), 28px); line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (prefers-reduced-motion: reduce) { .is-moving { transition: none; } }
</style>
