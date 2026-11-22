import { ApiError, getApiBaseUrl } from '@/request'
import { getAccessToken } from '@/auth/session'

export interface SseEvent<T = unknown> {
  id?: string
  event: string
  data: T
}

interface ChunkEvent {
  data: ArrayBuffer
}

interface ChunkTask {
  abort(): void
  onChunkReceived?: (callback: (event: ChunkEvent) => void) => void
}

interface StreamOptions {
  path: string
  data?: string | AnyObject | ArrayBuffer
  header?: Record<string, string>
  timeout?: number
}

function parseFrame(frame: string): SseEvent | null {
  let id: string | undefined
  let event = 'message'
  const data: string[] = []

  for (const line of frame.split('\n')) {
    if (line.startsWith('id:')) id = line.slice(3).trim()
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }

  if (!data.length) return null
  const raw = data.join('\n')
  try {
    return { id, event, data: JSON.parse(raw) }
  } catch {
    return { id, event, data: raw }
  }
}

function createProcessor(
  onEvent: (event: SseEvent) => void,
  onTerminal: (error?: Error) => void,
) {
  let buffer = ''
  return {
    consume(text: string) {
      buffer += text.replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const parsed = parseFrame(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (parsed) {
          onEvent(parsed)
          if (parsed.event === 'done' || parsed.event === 'question') {
            onTerminal()
            return true
          }
          if (parsed.event === 'error') {
            const payload = parsed.data as { code?: number; message?: string }
            onTerminal(
              new ApiError(payload?.code ?? -1, payload?.message ?? '流式请求失败'),
            )
            return true
          }
        }
        boundary = buffer.indexOf('\n\n')
      }
      return false
    },
    flush() {
      if (buffer.trim()) {
        const parsed = parseFrame(buffer)
        if (parsed) onEvent(parsed)
      }
      buffer = ''
    },
  }
}

// #ifdef H5
async function streamH5(
  options: StreamOptions,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), options.timeout ?? 65000)
  let terminalError: Error | undefined
  let finished = false
  const processor = createProcessor(onEvent, (error) => {
    terminalError = error
    finished = true
  })

  try {
    const response = await fetch(`${getApiBaseUrl()}${options.path}`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(getAccessToken()
          ? { Authorization: `Bearer ${getAccessToken()}` }
          : {}),
        ...(options.header ?? {}),
      },
      body: options.data ? JSON.stringify(options.data) : undefined,
    })

    if (!response.ok) {
      const text = await response.text()
      try {
        const body = JSON.parse(text) as { code?: number; message?: string }
        throw new ApiError(body.code ?? response.status, body.message ?? `HTTP ${response.status}`)
      } catch (error) {
        if (error instanceof ApiError) throw error
        throw new ApiError(response.status, text || `HTTP ${response.status}`)
      }
    }
    if (!response.body) throw new ApiError(-1, '浏览器不支持流式响应')

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    while (true) {
      const { value, done } = await reader.read()
      if (value) {
        processor.consume(decoder.decode(value, { stream: true }))
      }
      if (finished || done) {
        processor.flush()
        break
      }
    }

    if (terminalError) throw terminalError
    if (!finished) throw new ApiError(-1, '流式响应未返回结束事件')
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(-1, '流式请求超时或已取消')
    }
    throw error
  } finally {
    clearTimeout(timer)
  }
}
// #endif

// #ifndef H5
function streamUni(
  options: StreamOptions,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const decoder = new TextDecoder('utf-8')
  let settled = false
  let receivedEvents = false
  let task: ChunkTask | null = null

  return new Promise<void>((resolve, reject) => {
    const finish = (error?: Error) => {
      if (settled) return
      settled = true
      task?.abort()
      if (error) reject(error)
      else resolve()
    }
    const processor = createProcessor(onEvent, finish)

    task = uni.request({
      url: `${getApiBaseUrl()}${options.path}`,
      method: 'POST',
      data: options.data,
      timeout: options.timeout ?? 65000,
      enableChunked: true,
      responseType: 'arraybuffer',
      header: {
        Accept: 'text/event-stream',
        ...(getAccessToken()
          ? { Authorization: `Bearer ${getAccessToken()}` }
          : {}),
        ...(options.header ?? {}),
      },
      success: (response) => {
        if (settled) return
        if (response.statusCode < 200 || response.statusCode >= 300) {
          const body = response.data as { code?: number; message?: string } | string
          finish(
            typeof body === 'string'
              ? new ApiError(response.statusCode, body)
              : new ApiError(
                  body?.code ?? response.statusCode,
                  body?.message ?? `HTTP ${response.statusCode}`,
                ),
          )
          return
        }
        if (!receivedEvents) {
          if (typeof response.data === 'string') {
            processor.consume(response.data)
          } else if (response.data instanceof ArrayBuffer) {
            processor.consume(decoder.decode(new Uint8Array(response.data), { stream: true }))
          }
        }
        if (!settled) finish()
      },
      fail: (error) => finish(new ApiError(-1, error.errMsg)),
    }) as unknown as ChunkTask

    task.onChunkReceived?.((chunk) => {
      if (settled) return
      receivedEvents = true
      processor.consume(decoder.decode(new Uint8Array(chunk.data), { stream: true }))
    })
  })
}
// #endif

export function streamSse(
  options: StreamOptions,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  // #ifdef H5
  return streamH5(options, onEvent)
  // #endif
  // #ifndef H5
  return streamUni(options, onEvent)
  // #endif
}
