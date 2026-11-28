import { request } from '@/request'
import { createIdempotencyKey } from '@/request/idempotency'
import { streamSse, type SseEvent } from '@/request/sse'

export interface Evidence {
  doc_title: string
  section: string
  quote: string
}

export interface Condition {
  name: string
  evidence: Evidence[]
}

export interface EpisodeResult {
  triage: 'emergency' | 'clinic' | 'self_observe'
  triage_label: string
  urgency_note: string
  department_primary: string
  department_secondary: string | null
  conditions: Condition[]
  prep: {
    bring: string[]
    describe: string[]
    go_now: string[]
  }
  disclaimer?: string
  degraded?: boolean
  /** 覆盖范围版（issue #23 三出口之二）：conditions 整节空，科室档位仅作参考 */
  out_of_coverage?: boolean
}

/** 单问协议（io.6 / request.v2）：一次一问，question_id 由后端赋号 */
export interface PendingQuestion {
  question_id: string
  purpose: string
  text: string
  can_skip: boolean
  not_understood?: boolean
}

export type AnswerAction = 'answer' | 'unknown' | 'skip'

/** 危机处置载荷：固定文案与求助渠道，无分诊段落（issue #23 第 6 节） */
export interface SafetyPayload {
  kind: 'crisis'
  rule_ids: string[]
  version: number
  copy: string[]
}

export interface EpisodeDetail {
  disclaimer: string
  normalized?: Record<string, string | string[] | null>
  self_attribution?: string | null
  episode: {
    id: number
    status: string
    created_at: string
    saved_at: string | null
    expires_at: string
    complaint_text: string
    revision?: number
  }
  result: EpisodeResult | null
  clarify: {
    asked_count: number
    limit: number
    skipped: boolean
    pending: PendingQuestion | null
  } | null
  /** 结果修订历史：保留最近三版供回看（issue #23） */
  result_history?: Array<{ revision: number; result: EpisodeResult; gate: Record<string, unknown> | null }>
  gate?: {
    red_flags?: Array<{ rule_id: string; name: string }>
    citations_verified?: number
    citations_dropped?: number
    degraded?: boolean
    fallback?: boolean
    out_of_coverage?: boolean
    not_understood?: boolean
    crisis?: SafetyPayload | null
    /** 删空不出档（约束四）：无档位无科室，前端据此渲染对应卡片 */
    no_conclusion?: boolean
  } | null
  /** 删空通知文案：后端 compose 下发的单一事实源，仅 gate.no_conclusion 时非空 */
  no_conclusion_notice?: string | null
  /** 归档时是否已建提醒（api.md 5.7）：保存行只在它为 true 时提提醒 */
  reminder_created?: boolean
}

export interface EpisodeSummary {
  id: number
  status: string
  created_at: string
  saved_at: string | null
  complaint_excerpt: string
  triage: string | null
  triage_label: string | null
  department_primary: string | null
  degraded: boolean
}

export interface PageResult<T> {
  records: T[]
  total: number
  page: number
  size: number
}

export function listEpisodes(status?: string, page = 1, triage?: string): Promise<PageResult<EpisodeSummary>> {
  const query = `?page=${page}&size=20${status ? `&status=${encodeURIComponent(status)}` : ''}${triage ? `&triage=${encodeURIComponent(triage)}` : ''}`
  return request(`/episodes${query}`, { auth: true })
}

export interface EpisodeStreamEvent {
  event: 'stage' | 'question' | 'citation' | 'result_section' | 'done' | 'error' | 'heartbeat' | 'safety' | 'notice'
  data: Record<string, unknown>
}

function streamEpisode(
  path: string,
  data: Record<string, unknown> | undefined,
  onEvent: (event: EpisodeStreamEvent) => void,
  key = createIdempotencyKey(),
) {
  return streamSse(
    {
      path,
      data,
      header: { 'Idempotency-Key': key },
    },
    (event: SseEvent) => {
      onEvent(event as EpisodeStreamEvent)
    },
  )
}

export function createEpisodeStream(
  complaint: string,
  onEvent: (event: EpisodeStreamEvent) => void,
  cityCode?: string,
  key?: string,
) {
  return streamEpisode('/episodes', { complaint, ...(cityCode ? { city_code: cityCode } : {}) }, onEvent, key)
}

export function clarifyEpisodeStream(
  episodeId: number,
  answer: { question_id: string | null; action: AnswerAction; text: string },
  onEvent: (event: EpisodeStreamEvent) => void,
) {
  return streamEpisode(`/episodes/${episodeId}/clarify`, answer, onEvent)
}

export function skipClarifyStream(
  episodeId: number,
  onEvent: (event: EpisodeStreamEvent) => void,
) {
  return streamEpisode(`/episodes/${episodeId}/skip-clarify`, undefined, onEvent)
}

export function retryEpisodeStream(
  episodeId: number,
  onEvent: (event: EpisodeStreamEvent) => void,
) {
  return streamEpisode(`/episodes/${episodeId}/retry`, undefined, onEvent)
}

export function getEpisode(id: number): Promise<EpisodeDetail> {
  return request(`/episodes/${id}`, { auth: true })
}

export function deleteEpisode(id: number): Promise<null> {
  return request(`/episodes/${id}`, { method: 'DELETE', auth: true })
}
