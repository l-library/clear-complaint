import { request } from '@/request'

export interface DailySummaryItem {
  id?: string
  label?: string
  text?: string
  source_refs?: string[]
}

export type DailySummaryContent = string | DailySummaryItem

// 板块文案由工作流模板生成，后端只核对板块与日期：前端按可缺失处理，不补写。
export interface DailySummary {
  title?: string
  greeting?: string
  highlights?: DailySummaryContent[]
  health_connections?: DailySummaryContent[]
  gentle_reminders?: DailySummaryContent[]
  tomorrow_actions?: DailySummaryContent[]
  closing?: string
  limitations?: string
}

export interface DailyReport {
  report_date: string
  status: string
  degraded: boolean
  data_source: string
  workflow_version: string
  summary: DailySummary | null
  data_quality: Record<string, unknown> | null
  used_record_ids: string[]
  created_at: string
  updated_at: string
}

// 平台单次调用预算 60 秒（docs/api.md 16.1），共享的 15 秒默认超时会在正常生成时误报失败。
export function generateDailyReport(reportDate?: string): Promise<DailyReport> {
  return request('/daily/generate', {
    method: 'POST',
    data: reportDate ? { report_date: reportDate } : {},
    auth: true,
    timeout: 60000,
  })
}

export function getDailyReport(date?: string): Promise<DailyReport> {
  return request(`/daily${date ? `?date=${encodeURIComponent(date)}` : ''}`, { auth: true })
}
