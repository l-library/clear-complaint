import { request } from '@/request'
import type { PageResult } from '@/api/episodes'
import type { VitalRecord } from '@/api/archive'

export interface VitalInput {
  kind: 'bp' | 'height' | 'weight'
  measured_at: string
  systolic?: number
  diastolic?: number
  pulse?: number | null
  height_cm?: number
  weight_kg?: number
}

export function listVitals(page = 1): Promise<PageResult<VitalRecord>> {
  return request(`/vitals?page=${page}&size=20`, { auth: true })
}
export function saveVital(input: VitalInput, id?: number): Promise<VitalRecord> {
  // Pickers and API responses use Shanghai wall time; writes require an explicit offset.
  const measured_at = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(input.measured_at)
    ? input.measured_at.replace(' ', 'T') + '+08:00' : input.measured_at
  const data = { ...input, measured_at }
  const { kind, ...changes } = data
  return request(id ? `/vitals/${id}` : '/vitals', { method: id ? 'PUT' : 'POST', data: id ? changes : data, auth: true })
}
export function deleteVital(id: number): Promise<null> {
  return request(`/vitals/${id}`, { method: 'DELETE', auth: true })
}

export interface MedicationSchedule {
  id: number
  medication_id: number
  times: string[]
  started_on: string
  ended_on: string | null
  status: 'active' | 'stopped'
  note: string | null
}
export interface ScheduleInput {
  medication_id: number
  times: string[]
  started_on: string
  ended_on?: string | null
  note?: string
}
export function listSchedules(): Promise<{ records: MedicationSchedule[] }> {
  return request('/medication-plans', { auth: true })
}
export function createSchedule(data: ScheduleInput): Promise<MedicationSchedule> {
  return request('/medication-plans', { method: 'POST', data, auth: true })
}
export function updateSchedule(id: number, data: Partial<Omit<ScheduleInput, 'medication_id'>> & { status?: string }): Promise<MedicationSchedule> {
  return request(`/medication-plans/${id}`, { method: 'PUT', data, auth: true })
}
export function deleteSchedule(id: number): Promise<null> {
  return request(`/medication-plans/${id}`, { method: 'DELETE', auth: true })
}
export function deleteMedication(id: number): Promise<null> {
  return request(`/medications/${id}`, { method: 'DELETE', auth: true })
}
export interface ConsentRecord {
  current_version: string
  consented_version: string | null
  consented_at: string | null
  outdated: boolean
}
export function getConsentRecord(): Promise<ConsentRecord> {
  return request('/profile/privacy', { auth: true })
}
