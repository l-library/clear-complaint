import { request } from '@/request'
import type { Profile } from '@/api/profile'

export interface BloodPressure {
  measured_at: string
  systolic: number
  diastolic: number
  pulse?: number | null
}

export interface ArchiveOverview {
  profile: Profile | null
  vitals: {
    latest_height_cm: number | null
    latest_weight_kg: number | null
    bmi: number | null
    latest_bp: BloodPressure | null
  }
  trend_summary: {
    episodes_90d: number
    latest_triage: string | null
  }
  pending: {
    total: number
    medication: number
    followup: number
    recheck: number
  }
}

export interface ArchiveTrend {
  triage_points: Array<{ at: string; triage: string }>
  weight_points: Array<{ at: string; weight_kg: number }>
  bp_points: Array<{ at: string; systolic: number; diastolic: number }>
  symptom_keywords: Array<{ term: string; count: number }>
}

export interface ReminderItem {
  id: number
  kind: 'medication' | 'followup' | 'recheck'
  due_at: string
  status: 'pending' | 'done' | 'skipped' | 'missed' | 'expired'
  title: string
  body: string | null
  snooze_count: number
}

export interface ReminderResponse {
  groups: {
    medication: ReminderItem[]
    followup: ReminderItem[]
    recheck: ReminderItem[]
  }
  pending_count: number
}

export interface ReminderResponseResult {
  status: 'pending' | 'done'
  due_at?: string
  advice?: { level: string; text: string }
  supplement?: { watch_for: string[]; prepare_idx: number[]; next_question: string } | null
}

export interface VitalRecord {
  id: number
  kind: 'bp' | 'height' | 'weight'
  measured_at: string
  systolic: number | null
  diastolic: number | null
  pulse: number | null
  height_cm: number | null
  weight_kg: number | null
}

export function getArchiveOverview(): Promise<ArchiveOverview> {
  return request('/archive/overview', { auth: true })
}

export function getArchiveTrend(days = 90, limit = 10): Promise<ArchiveTrend> {
  return request(`/archive/trend?days=${days}&limit=${limit}`, { auth: true })
}

export function getReminders(date?: string): Promise<ReminderResponse> {
  return request(`/reminders${date ? `?date=${encodeURIComponent(date)}` : ''}`, { auth: true })
}

export function respondReminder(
  id: number,
  payload: Record<string, unknown>,
): Promise<ReminderResponseResult> {
  return request(`/reminders/${id}/respond`, {
    method: 'POST',
    data: payload,
    auth: true,
  })
}
