import { computed, reactive, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import type { Profile, Sex } from '@/api/profile'

const emptyForm = () => ({ name: '', birth_date: '', sex: '' as Sex | '', city_code: '', city_name: '', conditions: '', allergies: '', condition_note: '', allergy_note: '', conditionState: 0, allergyState: 0 })
function fromProfile(profile: Profile | null) {
  return { name: profile?.name || '', birth_date: profile?.birth_date || '', sex: profile?.sex || '' as Sex | '', city_code: profile?.city_code || '', city_name: profile?.city_name || '', conditions: profile?.conditions?.join('、') || '', allergies: profile?.allergies?.join('、') || '', condition_note: profile?.condition_note || '', allergy_note: profile?.allergy_note || '', conditionState: profile?.conditions == null ? 0 : profile.conditions.length ? 2 : 1, allergyState: profile?.allergies == null ? 0 : profile.allergies.length ? 2 : 1 }
}

export const useProfileDraftStore = defineStore('profile-draft', () => {
  const auth = useAuthStore()
  const form = reactive(emptyForm())
  const baseline = ref(JSON.stringify(form))
  const measurements = reactive({ height_cm: '', weight_kg: '' })
  const savedMeasurements = reactive({ height_cm: '', weight_kg: '' })
  const measurementsLoaded = ref(false)
  const editing = ref(false), busy = ref(false), error = ref(''), notice = ref('')
  const dirty = computed(() => JSON.stringify(form) !== baseline.value || JSON.stringify(measurements) !== JSON.stringify(savedMeasurements))
  function hydrate(profile: Profile | null) {
    if (dirty.value) return
    Object.assign(form, fromProfile(profile)); baseline.value = JSON.stringify(form)
  }
  function accept(profile: Profile, submitted: string) {
    const saved = fromProfile(profile)
    // Do not overwrite edits made while the save request was in flight.
    if (JSON.stringify(form) === submitted) Object.assign(form, saved)
    baseline.value = JSON.stringify(saved); editing.value = dirty.value
  }
  function hydrateMeasurements(vitals: { latest_height_cm: number | null; latest_weight_kg: number | null }) {
    for (const key of ['height_cm', 'weight_kg'] as const) {
      const value = vitals[`latest_${key}`]
      const saved = value == null ? '' : String(value)
      if (measurements[key] === savedMeasurements[key]) measurements[key] = saved
      savedMeasurements[key] = saved
    }
    measurementsLoaded.value = true
  }
  function acceptMeasurement(key: 'height_cm' | 'weight_kg', value: number, submitted: string) {
    const saved = String(value)
    if (measurements[key] === submitted) measurements[key] = saved
    savedMeasurements[key] = saved; editing.value = dirty.value
  }
  function reset() {
    Object.assign(form, emptyForm()); baseline.value = JSON.stringify(form)
    Object.assign(measurements, { height_cm: '', weight_kg: '' })
    Object.assign(savedMeasurements, { height_cm: '', weight_kg: '' }); measurementsLoaded.value = false
    editing.value = false; busy.value = false; error.value = ''; notice.value = ''
  }
  watch(() => auth.user?.id, reset)
  return { form, measurements, savedMeasurements, measurementsLoaded, editing, busy, error, notice, dirty, hydrate, accept, hydrateMeasurements, acceptMeasurement, reset }
})
