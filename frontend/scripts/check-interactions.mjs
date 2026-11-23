import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(import.meta.url)
const ts = require('typescript'), vue = require('vue'), pinia = require('pinia')
const { parse, compileScript } = require('vue/compiler-sfc')
const src = new URL('../src/', import.meta.url)
function h5(source) {
  const flags = [true]
  return source.split('\n').filter((line) => {
    const match = line.match(/(?:\/\/|<!--)\s*#(ifdef|ifndef)\s+(\S+)/)
    if (match) { flags.push(flags[flags.length - 1] && (match[2] === 'H5' ? match[1] === 'ifdef' : match[1] === 'ifndef')); return false }
    if (/#endif/.test(line)) { flags.pop(); return false }
    return flags[flags.length - 1]
  }).join('\n')
}
function loader(overrides = {}, globals = {}) {
  const cache = new Map()
  function load(name) {
    if (Object.hasOwn(overrides, name)) return overrides[name]
    if (name === 'vue') return vue
    if (name === 'pinia') return pinia
    if (!name.startsWith('@/')) return require(name)
    if (name.endsWith('.vue') && name !== '@/components/QWorkspace.vue') return {}
    if (cache.has(name)) return cache.get(name)
    let url = new URL(name.slice(2) + (name.endsWith('.vue') ? '' : '.ts'), src)
    if (!existsSync(url)) url = new URL(name.slice(2) + '/index.ts', src)
    let source = readFileSync(url, 'utf8')
    if (name.endsWith('.vue')) source = compileScript(parse(source).descriptor, { id: 'live-interaction-test' }).content
    const result = {}
    cache.set(name, result)
    const compiled = ts.transpileModule(h5(source), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
    vm.runInNewContext(compiled, { exports: result, require: load, console, Date, Error, setTimeout, clearTimeout, ArrayBuffer, Uint8Array, URLSearchParams, ...globals })
    return result
  }
  return load
}

// Synthetic transport fixtures are used only here, never in the running app.
const stored = new Map()
let network
const baseUni = {
  getStorageSync: (key) => stored.get(key) || '',
  setStorageSync: (key, value) => stored.set(key, JSON.parse(JSON.stringify(value))),
  removeStorageSync: (key) => stored.delete(key),
  request: (options) => { queueMicrotask(() => network(options)); return { abort() {} } },
}
const loadRequest = loader({}, { uni: baseUni })
const sessions = loadRequest('@/auth/session'), api = loadRequest('@/request')
const tokens = { access_token: 'SYNTHETIC-OLD', refresh_token: 'SYNTHETIC-REFRESH', token_type: 'Bearer', access_expires_at: '2099-01-01 00:00:00', refresh_expires_at: '2099-02-01 00:00:00' }
sessions.writeSession({ user: { id: 1, phone: '10000000000', is_demo: false, created_at: '2026-11-22 00:00:00' }, tokens, profileComplete: true })
let refreshes = 0
network = (options) => {
  if (options.url === '/api/auth/refresh') { refreshes += 1; options.success({ statusCode: 200, data: { code: 0, data: { tokens: { ...tokens, access_token: 'SYNTHETIC-NEW' } } } }); return }
  assert.equal(options.url, '/api/profile')
  options.success(options.header.Authorization.endsWith('OLD')
    ? { statusCode: 401, data: { code: 1004, message: 'expired' } }
    : { statusCode: 200, data: { code: 0, data: { profile: null } } })
}
await Promise.all([api.request('/profile', { auth: true }), api.request('/profile', { auth: true })])
assert.equal(refreshes, 1, 'Concurrent failures must share a single token rotation')
assert.equal(sessions.getAccessToken(), 'SYNTHETIC-NEW')
let finishOldRefresh
network = (options) => {
  if (options.url === '/api/auth/refresh') { finishOldRefresh = () => options.success({ statusCode: 200, data: { code: 0, data: { tokens: { ...tokens, access_token: 'SYNTHETIC-LATE-OLD' } } } }); return }
  options.success({ statusCode: 401, data: { code: 1004, message: 'expired' } })
}
const oldAccountRequest = api.request('/profile', { auth: true })
for (let i = 0; i < 4; i += 1) await Promise.resolve()
sessions.writeSession({ user: { id: 2, phone: '10000000001', is_demo: false, created_at: '2026-11-22 00:00:00' }, tokens: { ...tokens, access_token: 'SYNTHETIC-ACCOUNT-B', refresh_token: 'SYNTHETIC-B-REFRESH' }, profileComplete: true })
finishOldRefresh()
await assert.rejects(oldAccountRequest)
assert.equal(sessions.getAccessToken(), 'SYNTHETIC-ACCOUNT-B', 'An old refresh must not overwrite or clear the new account')
network = (options) => options.fail({ errMsg: 'network failed' })
await assert.rejects(api.request('/profile', { auth: true }), /无法连接本机后端/)
let expired = false
api.setAuthExpiredHandler(() => { expired = true })
network = (options) => options.success({ statusCode: 401, data: { code: 1004, message: 'expired' } })
await assert.rejects(api.request('/profile', { auth: true }))
assert.equal(expired, true)
assert.equal(sessions.readSession(), null)
let callsWithoutToken = 0
network = () => { callsWithoutToken += 1 }
await assert.rejects(api.request('/profile', { auth: true }), /请先登录/)
assert.equal(callsWithoutToken, 0)

const parseModule = loadRequest('@/request/sseParser')
const events = []
const parser = parseModule.createSseParser((event) => events.push(event))
const decode = parseModule.createUtf8Decoder()
const text = 'id: 1\r\nevent: stage\r\ndata: {"text":"合成中文🗣️"}\r\n\r\nevent: done\r\ndata: {"episode_id":71}\r\n\r\n'
for (const byte of new TextEncoder().encode(text)) parser.push(decode(new Uint8Array([byte])))
parser.finish()
assert.equal(events.length, 2)
assert.equal(events[0].data.text, '合成中文🗣️')
assert.equal(events[1].data.episode_id, 71)
assert.throws(() => parseModule.createSseParser(() => {}).push('event: done\ndata: invalid\n\n'), /格式/)
const profile = { name: 'SYNTHETIC USER', birth_date: '2000-01-01', sex: 'undisclosed', city_code: null, age_years: 26, required_missing: [], conditions: null, allergies: null }
const detail = { episode: { id: 71, status: 'ready', created_at: '2026-11-22 10:00:00', complaint_text: 'SYNTHETIC UI TEST', saved_at: null, expires_at: '2026-11-23 10:00:00' }, clarify: null, result: { triage: 'clinic', triage_label: '门诊', urgency_note: 'SYNTHETIC ONLY', department_primary: 'SYNTHETIC', department_secondary: null, conditions: [], prep: { bring: [], describe: [], go_now: [] }, disclaimer: 'SYNTHETIC ONLY' } }
const clone = (value) => JSON.parse(JSON.stringify(value))
const settle = async () => { for (let i = 0; i < 16; i += 1) { await Promise.resolve(); await vue.nextTick() } }
function setup(route = 'pages/index/index') {
  const auth = vue.reactive({ user: { id: 1 }, isLoggedIn: true, ensureFreshSession: async () => true })
  let failCreate = false, detailResolver, delayedDetail = false
  const creations = [], saves = [], routes = [], flights = []
  let page = { route, options: {} }
  const episodes = {
    listEpisodes: async () => ({ records: [], total: 0, page: 1, size: 20 }),
    createEpisodeStream: async (complaint, event, city, key) => {
      creations.push({ complaint, key })
      if (failCreate) throw new Error('SYNTHETIC transport failure')
      event({ event: 'stage', data: { episode_id: 71, text: 'SYNTHETIC stage' } })
      event({ event: 'done', data: { episode_id: 71 } })
    },
    getEpisode: () => delayedDetail ? new Promise((resolve) => { detailResolver = resolve }) : Promise.resolve(clone(detail)),
    saveEpisode: async (...args) => { saves.push(args) },
    clarifyEpisodeStream: async () => {}, skipClarifyStream: async () => {}, retryEpisodeStream: async () => {},
  }
  const uni = {
    ...baseUni,
    redirectTo(options) { routes.push(options.url); const [route, query] = options.url.slice(1).split('?'); page = { route, options: Object.fromEntries(new URLSearchParams(query)) }; options.complete?.() },
    createSelectorQuery() { let selector; return { select(value) { selector = value; return this }, boundingClientRect(callback) { callback(selector.startsWith('#bubble-') ? { left: 640, top: 90, width: 180, height: 60 } : { left: 400, top: 350, width: 500, height: 120 }); return this }, exec() {} } },
  }
  const modules = loader({
    '@/stores/auth': { useAuthStore: () => auth },
    '@/api/episodes': episodes,
    '@/api/profile': { getProfile: async () => ({ profile: clone(profile) }) },
    vue: { ...vue, onMounted() {} },
  }, { uni, getCurrentPages: () => [page], document: { activeElement: null, querySelector: () => null, querySelectorAll: () => [] }, HTMLElement: class {} })
  pinia.setActivePinia(pinia.createPinia())
  const scope = vue.effectScope()
  const store = scope.run(() => modules('@/stores/liveWorkspace').useLiveWorkspaceStore())
  if (route !== 'pages/index/index') store.openWorkspace('chat')
  const component = scope.run(() => modules('@/components/QWorkspace.vue').default.setup({}, { expose() {} }))
  component.messageTransition.value = { play: (...args) => flights.push(args) }
  return { auth, store, component, creations, saves, routes, flights, stop: () => scope.stop(), setFail: (value) => { failCreate = value }, delay: () => { delayedDetail = true }, resolve: () => detailResolver?.(clone(detail)) }
}
for (const route of ['pages/index/index', 'pages/chat/index']) {
  const app = setup(route)
  await app.store.initialize()
  app.store.draft = 'SYNTHETIC UI TEST'
  await app.component.handleSend()
  assert.equal(app.store.messages[0].content, 'SYNTHETIC UI TEST')
  assert.equal(app.flights.length, 1)
  assert.equal(app.routes.length, 0, 'Navigation must wait for the message flight')
  await app.component.handleSend()
  assert.equal(app.creations.length, 1, 'A repeated click must not send another request')
  app.component.finishTransfer()
  await settle()
  assert.match(app.routes[0], /^\/pages\/chat\/index\?conversation_id=71/)
  assert.equal(app.store.result.triage, 'clinic')
  assert.equal(app.store.messages.length, 1, 'No canned assistant messages may appear')
  await app.store.saveConversation(false, '2026-11-25')
  assert.deepEqual(app.saves[0], [71, false, '2026-11-25'])
  app.stop()
}
const failed = setup()
await failed.store.initialize()
failed.setFail(true)
failed.store.draft = 'SYNTHETIC RETRY'
failed.store.sendMessage()
await settle()
assert.match(failed.store.error, /transport failure/)
assert.equal(failed.store.messages.length, 1)
assert.equal(failed.store.result, null)
const key = failed.creations[0].key
await failed.store.retry()
assert.equal(failed.creations[1].key, key, 'A network retry must reuse the original idempotency key')
failed.stop()
const late = setup()
await late.store.initialize()
late.delay()
late.store.draft = 'SYNTHETIC SESSION'
late.store.sendMessage()
await settle()
late.auth.isLoggedIn = false
late.auth.user = null
await settle()
late.resolve()
await settle()
assert.equal(late.store.result, null, 'Late responses must not reinsert data after logout')
assert.equal(late.store.messages.length, 0)
late.stop()
const anonymous = setup()
anonymous.auth.isLoggedIn = false
anonymous.auth.user = null
await settle()
anonymous.store.draft = 'SYNTHETIC UNSENT'
assert.equal(anonymous.store.sendMessage(), false)
assert.equal(anonymous.creations.length, 0)
assert.equal(anonymous.store.draft, 'SYNTHETIC UNSENT')
assert.equal(anonymous.store.accountOpen, true)
anonymous.stop()
class Button { disabled = false; clicks = 0; hasAttribute() { return this.disabled } click() { this.clicks += 1 } }
const keyboard = loader({}, { HTMLElement: Button })('@/components/buttonKeyboard')
const control = new Button()
for (const key of ['Enter', ' ', 'Tab']) keyboard.activateButton({ key, currentTarget: control, preventDefault() {} })
control.disabled = true
keyboard.activateButton({ key: 'Enter', currentTarget: control, preventDefault() {} })
assert.equal(control.clicks, 2)
console.log('Live interaction checks passed: authenticated requests, refresh rotation, no offline fixtures, UTF-8/SSE framing, message flight, stable retry keys and logout isolation.')
