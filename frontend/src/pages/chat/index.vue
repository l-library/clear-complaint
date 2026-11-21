<template><QWorkspace /></template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import QWorkspace from '@/components/QWorkspace.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()
onLoad((options) => {
  store.openWorkspace('chat')
  if (options?.conversation_id && !store.openConversation(options.conversation_id)) {
    uni.showToast({ title: '未找到该对话，已打开新问诊', icon: 'none' })
    store.newConversation()
  }
})
</script>
