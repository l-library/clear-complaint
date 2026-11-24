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
  const editing = ref(false), busy = ref(false), error = ref(''), notice = ref('')
  const dirty = computed(() => JSON.stringify(form) !== baseline.value)
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
  watch(() => auth.user?.id, () => {
    Object.assign(form, emptyForm()); baseline.value = JSON.stringify(form)
    editing.value = false; busy.value = false; error.value = ''; notice.value = ''
  })
  return { form, editing, busy, error, notice, dirty, hydrate, accept }
})
