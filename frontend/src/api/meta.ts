import { request } from '@/request'

export interface PrivacyMeta {
  current_version: string
  policy_url: string
  sensitive_policy_url: string
}

export function getPrivacyMeta(): Promise<PrivacyMeta> {
  return request<PrivacyMeta>('/meta/privacy')
}
