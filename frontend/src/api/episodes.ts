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
  disclaimer: string
}

export interface QuestionField {
  field: string
  text: string
  options?: string[]
  allow_free_text?: boolean
}

export interface EpisodeDetail {
  episode: {
    id: number
    status: string
    created_at: string
    saved_at: string | null
    expires_at: string
    complaint_text: string
  }
  result: EpisodeResult | null
  clarify: {
    round: number
    round_limit: number
    missing_fields: string[]
    questions: QuestionField[]
  } | null
}

export interface SaveResponse {
  saved_at: string | null
  reminder: {
    id: number
    kind: string
    due_at: string
  } | null
}

export interface EpisodeSummary {
  id: number
  status: string
  created_at: string
  saved_at: string | null
  complaint_excerpt: string
  triage: string
  triage_label: string
  department_primary: string
  degraded: boolean
}

export interface PageResult<T> {
  records: T[]
  total: number
  page: number
  size: number
}

export function listEpisodes(status?: string): Promise<PageResult<EpisodeSummary>> {
  const query = status ? `?status=${encodeURIComponent(status)}&page=1&size=20` : '?page=1&size=20'
  return request(`/episodes${query}`, { auth: true })
}

export interface EpisodeStreamEvent {
  event: 'stage' | 'question' | 'citation' | 'result_section' | 'done' | 'error' | 'heartbeat'
  data: Record<string, unknown>
}

function streamEpisode(
  path: string,
  data: Record<string, unknown> | undefined,
  onEvent: (event: EpisodeStreamEvent) => void,
) {
  return streamSse(
    {
      path,
      data,
      header: { 'Idempotency-Key': createIdempotencyKey() },
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
) {
  return streamEpisode('/episodes', { complaint, ...(cityCode ? { city_code: cityCode } : {}) }, onEvent)
}

export function clarifyEpisodeStream(
  episodeId: number,
  answers: Array<{ field: string; value: string; is_unknown?: boolean }>,
  onEvent: (event: EpisodeStreamEvent) => void,
) {
  return streamEpisode(`/episodes/${episodeId}/clarify`, { answers }, onEvent)
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

export function saveEpisode(id: number, reminder = true): Promise<SaveResponse> {
  return request(`/episodes/${id}/save`, {
    method: 'POST',
    data: { save: true, reminder },
    auth: true,
  })
}
