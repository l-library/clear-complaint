<template><QWorkspace /></template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import QWorkspace from '@/components/QWorkspace.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()
onLoad((options) => {
  store.openWorkspace('plans')
  if (options?.tab === 'follow_up' || options?.tab === 'medication') store.selectedPlanTab = options.tab
})
</script>
