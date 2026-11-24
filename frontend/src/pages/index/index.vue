<template><QWorkspace /></template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import QWorkspace from '@/components/QWorkspace.vue'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'

const store = useLiveWorkspaceStore()
onLoad(() => { store.screen = 'landing' })
</script>
