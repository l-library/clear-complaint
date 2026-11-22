import { request } from '@/request'

export interface ExportResponse {
  url: string
  expires_at: string
  size_bytes: number
}

export function exportAccountData(): Promise<ExportResponse> {
  return request('/export', { auth: true })
}

export function clearAccountData(): Promise<{
  cleared: { episodes: number; vitals: number; medications: number; reminders: number }
}> {
  return request('/data', {
    method: 'DELETE',
    data: { confirm: '删除' },
    auth: true,
  })
}

export function deleteAccount(): Promise<null> {
  return request('/account', {
    method: 'DELETE',
    data: { confirm: '删除' },
    auth: true,
  })
}
