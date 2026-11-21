<template><QWorkspace /></template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import QWorkspace from '@/components/QWorkspace.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()
onLoad(() => { store.screen = 'landing' })
</script>
