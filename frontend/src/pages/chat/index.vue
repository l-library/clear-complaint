<template><QWorkspace /></template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import QWorkspace from '@/components/QWorkspace.vue'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'
import { getReminders } from '@/api/archive'

const store = useLiveWorkspaceStore()
onLoad(async (options) => {
  store.openWorkspace('chat')
  if (options?.conversation_id) await store.openConversation(options.conversation_id)
  if (options?.reminder_id && options?.date && store.auth.isLoggedIn && store.followUpReminder?.id !== Number(options.reminder_id)) {
    try {
      const data = await getReminders(options.date)
      const reminder = data.groups.followup.find((item) => item.id === Number(options.reminder_id))
      if (reminder) store.startFollowUp(reminder)
      else store.error = '未找到此随访提醒。'
    } catch (cause) { store.error = cause instanceof Error ? cause.message : '随访读取失败。' }
  }
})
</script>
