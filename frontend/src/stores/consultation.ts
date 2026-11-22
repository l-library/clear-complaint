import { ref } from 'vue'
import { defineStore } from 'pinia'
import { createMockConsultation, type ConsultationCase } from '@/mock/consultation'

export const useConsultationStore = defineStore('consultation', () => {
  const data = ref<ConsultationCase>(createMockConsultation())
  const started = ref(false)

  function start(text: string) {
    data.value = createMockConsultation()
    data.value.originalText = text.trim() || data.value.originalText
    started.value = true
  }

  function saveClarification(values: ConsultationCase['clarification']) {
    data.value.clarification = { ...values }
    started.value = true
  }

  function reset() {
    data.value = createMockConsultation()
    started.value = false
  }

  return {
    data,
    started,
    start,
    saveClarification,
    reset,
  }
})
