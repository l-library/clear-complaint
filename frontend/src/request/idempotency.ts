function randomHex(length: number) {
  let value = ''
  while (value.length < length) {
    value += Math.floor(Math.random() * 16).toString(16)
  }
  return value.slice(0, length)
}

export function createIdempotencyKey() {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }

  return [
    randomHex(8),
    randomHex(4),
    `4${randomHex(3)}`,
    `8${randomHex(3)}`,
    randomHex(12),
  ].join('-')
}
