import { ApiError, getApiBaseUrl, refreshAccessToken, invalidateSession } from '@/request'
import { getAccessToken, readSession } from '@/auth/session'
import { createSseParser, createUtf8Decoder, type SseEvent } from '@/request/sseParser'
export type { SseEvent } from '@/request/sseParser'
interface StreamOptions { path: string; data?: string | AnyObject | ArrayBuffer; header?: Record<string, string>; timeout?: number }
function responseError(status: number, text: string) {
  try { const body = JSON.parse(text) as { code?: number; message?: string }; return new ApiError(body.code ?? status, body.message || `请求失败（HTTP ${status}）`) }
  catch { return new ApiError(status, `请求失败（HTTP ${status}）`) }
}
function processor(onEvent: (event: SseEvent) => void) {
  let finished = false
  let error: Error | undefined
  const parser = createSseParser((event) => {
    if (finished) return
    onEvent(event)
    if (event.event === 'done' || event.event === 'question') finished = true
    if (event.event === 'error') {
      const data = event.data as { code?: number; message?: string }
      error = new ApiError(data.code ?? -1, data.message || '本轮生成失败，请重试。'); finished = true
    }
  })
  return { consume: parser.push, finished: () => finished, finish() { parser.finish(); if (error) throw error; if (!finished) throw new ApiError(-1, '流式连接中断，请恢复问诊或重试。') } }
}
// #ifdef H5
async function streamH5(options: StreamOptions, onEvent: (event: SseEvent) => void) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), options.timeout ?? 65000)
  const process = processor(onEvent), decode = createUtf8Decoder()
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  try {
    const response = await fetch(`${getApiBaseUrl()}${options.path}`, {
      method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', Authorization: `Bearer ${getAccessToken()}`, ...options.header },
      body: options.data ? JSON.stringify(options.data) : undefined,
    })
    if (!response.ok) throw responseError(response.status, await response.text())
    if (!response.body) throw new ApiError(-1, '此浏览器无法读取流式响应。')
    reader = response.body.getReader()
    while (!process.finished()) {
      const { value, done } = await reader.read()
      if (value) process.consume(decode(value))
      if (done) { process.consume(decode(new Uint8Array(), true)); break }
    }
    process.finish()
  } catch (cause) {
    if (cause instanceof ApiError) throw cause
    if (cause instanceof Error && cause.name === 'AbortError') throw new ApiError(-1, '问诊连接超时，请恢复记录或重试。')
    throw cause instanceof Error ? cause : new ApiError(-1, '暂时无法连接，请稍后重试。')
  } finally { clearTimeout(timer); if (reader) { try { await reader.cancel() } catch { /* The response may already be closed. */ } } controller.abort() }
}
// #endif
// #ifndef H5
function streamUni(options: StreamOptions, onEvent: (event: SseEvent) => void): Promise<void> {
  const decode = createUtf8Decoder(), process = processor(onEvent)
  let settled = false, received = false
  let task: { abort(): void; onChunkReceived?: (callback: (event: { data: ArrayBuffer }) => void) => void } | undefined
  return new Promise((resolve, reject) => {
    const finish = (error?: unknown) => { if (settled) return; settled = true; task?.abort(); if (error) reject(error); else resolve() }
    const consume = (text: string) => { try { process.consume(text); if (process.finished()) { process.finish(); finish() } } catch (cause) { finish(cause) } }
    task = uni.request({
      url: `${getApiBaseUrl()}${options.path}`, method: 'POST', data: options.data, timeout: options.timeout ?? 65000,
      enableChunked: true, responseType: 'arraybuffer',
      header: { 'Content-Type': 'application/json', Accept: 'text/event-stream', Authorization: `Bearer ${getAccessToken()}`, ...options.header },
      success(response) {
        if (settled) return
        const text = typeof response.data === 'string' ? response.data : response.data instanceof ArrayBuffer ? decode(new Uint8Array(response.data), true) : JSON.stringify(response.data)
        if (response.statusCode < 200 || response.statusCode >= 300) { finish(responseError(response.statusCode, text)); return }
        if (!received) consume(text)
        if (!settled) { try { process.consume(decode(new Uint8Array(), true)); process.finish(); finish() } catch (cause) { finish(cause) } }
      },
      fail: () => finish(new ApiError(-1, '暂时无法连接，请稍后重试。')),
    }) as unknown as typeof task
    task?.onChunkReceived?.((event) => { if (!settled) { received = true; consume(decode(new Uint8Array(event.data))) } })
  })
}
// #endif
export async function streamSse(options: StreamOptions, onEvent: (event: SseEvent) => void): Promise<void> {
  const token = getAccessToken()
  const owner = readSession()?.user.id
  if (!token) throw new ApiError(1004, '请先登录账户。')
  let transport: (options: StreamOptions, onEvent: (event: SseEvent) => void) => Promise<void>
  // #ifdef H5
  transport = streamH5
  // #endif
  // #ifndef H5
  transport = streamUni
  // #endif
  try { await transport(options, onEvent) }
  catch (cause) {
    if (cause instanceof ApiError && (cause.code === 1004 || cause.code === 401) && getAccessToken() === token) {
      if (await refreshAccessToken() && readSession()?.user.id === owner) { await transport(options, onEvent); return }
      invalidateSession(token)
    }
    throw cause
  }
}
