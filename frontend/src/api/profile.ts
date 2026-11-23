import { request } from '@/request'

export type Sex = 'male' | 'female' | 'undisclosed'

export interface Profile {
  name: string | null
  birth_date: string | null
  age_years: number | null
  sex: Sex | null
  city_code: string | null
  city_name: string | null
  conditions: string[] | null
  condition_note: string | null
  allergies: string[] | null
  allergy_note: string | null
  required_missing: string[]
  updated_at: string | null
}

export interface ProfileUpdate {
  name?: string
  birth_date?: string
  sex?: Sex
  city_code?: string
  city_name?: string
  conditions?: string[] | null
  condition_note?: string
  allergies?: string[] | null
  allergy_note?: string
}

export function getProfile(): Promise<{ profile: Profile | null }> {
  return request('/profile', { auth: true })
}

export function updateProfile(payload: ProfileUpdate): Promise<Profile> {
  return request('/profile', {
    method: 'PUT',
    data: payload,
    auth: true,
  })
}
