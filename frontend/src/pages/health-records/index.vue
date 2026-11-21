<template><QWorkspace /></template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import QWorkspace from '@/components/QWorkspace.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()
onLoad((options) => {
  store.openWorkspace('archive')
  if (options?.record_id) {
    const record = store.records.find((item) => item.id === options.record_id)
    if (record) store.openRecord(record)
    else uni.showToast({ title: '未找到该健康记录', icon: 'none' })
  }
  if (options?.mode === 'import') store.archiveMode = 'import'
})
</script>
