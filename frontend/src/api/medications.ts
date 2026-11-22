import { request } from '@/request'

export interface Medication {
  id: number
  name: string
  dosage_text: string | null
  frequency_text: string | null
  kind: 'long_term' | 'short_term'
  status: 'active' | 'stopped' | 'expired'
  started_on: string
  ended_on: string | null
}

export interface MedicationPayload {
  name: string
  dosage_text?: string
  frequency_text?: string
  kind: 'long_term' | 'short_term'
  started_on: string
  ended_on?: string
}

export function getMedications(): Promise<{ records: Medication[] }> {
  return request('/medications', { auth: true })
}

export function createMedication(payload: MedicationPayload): Promise<Medication> {
  return request('/medications', {
    method: 'POST',
    data: payload,
    auth: true,
  })
}

export function updateMedication(
  id: number,
  payload: Partial<MedicationPayload> & { status?: Medication['status'] },
): Promise<Medication> {
  return request(`/medications/${id}`, {
    method: 'PUT',
    data: payload,
    auth: true,
  })
}
