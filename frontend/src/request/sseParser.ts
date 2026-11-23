export interface SseEvent<T = unknown> { id?: string; event: string; data: T }

export function createSseParser(onEvent: (event: SseEvent) => void) {
  let buffer = ''
  function frame(text: string) {
    let event = 'message', id: string | undefined
    const data: string[] = []
    for (const line of text.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('id:')) id = line.slice(3).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!data.length) return
    let payload: unknown
    try { payload = JSON.parse(data.join('\n')) } catch { throw new Error('服务返回的事件格式不正确，请重试。') }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('服务返回的事件数据不正确。')
    onEvent({ id, event, data: payload })
  }
  return {
    push(text: string) {
      buffer = (buffer + text).replace(/\r\n/g, '\n')
      if (buffer.length > 1024 * 1024) throw new Error('服务返回的事件过大。')
      let index = buffer.indexOf('\n\n')
      while (index >= 0) { frame(buffer.slice(0, index)); buffer = buffer.slice(index + 2); index = buffer.indexOf('\n\n') }
    },
    finish() { if (buffer.trim()) frame(buffer.replace(/\r\n/g, '\n')); buffer = '' },
  }
}

// WeChat does not consistently provide TextDecoder; preserve partial UTF-8 characters across chunks.
export function createUtf8Decoder() {
  let pending: number[] = []
  let first = true
  return (bytes: Uint8Array, final = false) => {
    const input = pending.concat(Array.from(bytes)), output: string[] = []
    pending = []
    for (let i = 0; i < input.length;) {
      const lead = input[i]
      const length = lead < 0x80 ? 1 : lead >= 0xc2 && lead <= 0xdf ? 2 : lead >= 0xe0 && lead <= 0xef ? 3 : lead >= 0xf0 && lead <= 0xf4 ? 4 : 0
      if (!length) { output.push('\ufffd'); i += 1; continue }
      if (i + length > input.length && !final) { pending = input.slice(i); break }
      let code = lead & (length === 1 ? 0x7f : 0x7f >> length), valid = i + length <= input.length
      for (let j = 1; valid && j < length; j += 1) {
        const next = input[i + j]
        if ((next & 0xc0) !== 0x80) valid = false
        else code = (code << 6) | (next & 0x3f)
      }
      if (!valid || (length === 2 && code < 0x80) || (length === 3 && code < 0x800) || (length === 4 && code < 0x10000) || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) { output.push('\ufffd'); i += 1; continue }
      output.push(String.fromCodePoint(code)); i += length
    }
    let result = output.join('')
    if (first && result) { first = false; result = result.replace(/^\uFEFF/, '') }
    return result
  }
}
