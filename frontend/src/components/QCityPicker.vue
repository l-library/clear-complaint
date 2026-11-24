<template>
  <view>
    <text class="live-label">所在城市（选填）</text>
    <picker mode="multiSelector" :range="ranges" :value="indices" @columnchange="changeColumn" @change="choose">
      <view class="live-select">{{ name || '选择省份和城市' }}</view>
    </picker>
    <button v-if="code || name" role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="$emit('change', { code: '', name: '' })">暂不填写城市</button>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { activateButton } from '@/components/buttonKeyboard'
import cities from '@/data/cities.json'

const props = defineProps<{ code: string; name: string }>()
const emit = defineEmits<{ (e: 'change', value: { code: string; name: string }): void }>()
const indices = ref([0, 0])
const ranges = computed(() => [cities.map((province) => province.name), cities[indices.value[0]].children.map((city) => city.name)])
watch(() => props.code, (code) => {
  const province = cities.findIndex((item) => item.children.some((city) => city.code.padEnd(6, '0') === code))
  if (province >= 0) indices.value = [province, cities[province].children.findIndex((city) => city.code.padEnd(6, '0') === code)]
}, { immediate: true })
function changeColumn(event: { detail: { column: number; value: number } }) {
  if (event.detail.column === 0) indices.value = [event.detail.value, 0]
  else indices.value = [indices.value[0], event.detail.value]
}
function choose(event: { detail: { value: number[] } }) {
  const [province, cityIndex] = event.detail.value
  const city = cities[province]?.children[cityIndex]
  if (city) { indices.value = [province, cityIndex]; emit('change', { code: city.code.padEnd(6, '0'), name: city.name === '市辖区' ? cities[province].name : city.name }) }
}
</script>
