<template><QWorkspace /></template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import QWorkspace from '@/components/QWorkspace.vue'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'

const store = useLiveWorkspaceStore()
onLoad((options) => {
  store.openWorkspace('plans')
  if (options?.tab === 'follow_up' || options?.tab === 'medication' || options?.tab === 'all') store.selectedPlanTab = options.tab
})
</script>
