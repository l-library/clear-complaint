<template>
  <view class="brand-glyph" :class="{ 'brand-speaking': animated }" role="img" aria-label="ClearComplaint，C 与发音">
    <image class="brand-layer" src="/static/brand/c.svg" mode="aspectFit" aria-hidden="true" />
    <image class="brand-layer sound-wave sound-wave-near" src="/static/brand/wave-near.svg" mode="aspectFit" aria-hidden="true" />
    <image class="brand-layer sound-wave sound-wave-far" src="/static/brand/wave-far.svg" mode="aspectFit" aria-hidden="true" />
  </view>
</template>

<script setup lang="ts">
defineProps<{ animated?: boolean }>()
</script>

<style scoped>
.brand-glyph { position: relative; display: block; flex-shrink: 0; }
.brand-layer { position: absolute; inset: 0; width: 100%; height: 100%; }
.sound-wave { transform-origin: 66% 50%; }
.brand-speaking .sound-wave { animation: voice-expand 2.4s cubic-bezier(.25, .46, .45, .94) infinite both; will-change: transform, opacity; }
.brand-speaking .sound-wave-far { animation-delay: .22s; }
@keyframes voice-expand {
  0% { opacity: 0; transform: translateX(-4%) scale(.88); }
  16% { opacity: 1; }
  48% { opacity: .8; }
  78%, 100% { opacity: 0; transform: translateX(10%) scale(1.24); }
}
@media (prefers-reduced-motion: reduce) {
  .brand-speaking .sound-wave { animation: none; opacity: 1; transform: none; will-change: auto; }
}
</style>
