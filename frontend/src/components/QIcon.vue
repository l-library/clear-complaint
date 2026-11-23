<template>
  <image class="q-icon" :src="`/static/icons/${name}.svg`" mode="aspectFit" aria-hidden="true" />
</template>

<script setup lang="ts">
defineProps<{ name: string }>()
</script>

<style scoped>
.q-icon { display: inline-block; width: 22px; height: 22px; flex-shrink: 0; vertical-align: middle; }
</style>
