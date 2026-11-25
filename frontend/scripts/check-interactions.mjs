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
    if (name.endsWith('.json')) return { default: JSON.parse(readFileSync(new URL(name.slice(2), src), 'utf8')) }
    if (name.endsWith('.vue') && !['QWorkspace', 'QLiveArchive', 'QLivePlans', 'QAccountPanel', 'QCityPicker', 'QEpisodeReview', 'QConsultationFlow'].some((component) => name === `@/components/${component}.vue`)) return {}
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

async function renderComponent(name, props = {}, overrides = {}) {
  const descriptor = parse(readFileSync(new URL(`components/${name}.vue`, src), 'utf8')).descriptor
  const script = compileScript(descriptor, { id: 'live-render-test', inlineTemplate: true, templateOptions: { compilerOptions: { isCustomElement: (tag) => /^[a-z]/.test(tag) } } }).content
  const compiled = ts.transpileModule(h5(script), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  const result = {}
  vm.runInNewContext(compiled, { exports: result, require: loader({ '@/components/QIcon.vue': { default: { render: () => null } }, ...overrides }), Date })
  const app = vue.createSSRApp(result.default, props)
  for (const tag of ['picker', 'checkbox', 'checkbox-group']) app.component(tag, { setup: (_, { slots }) => () => vue.h(tag, slots.default?.()) })
  return require('@vue/server-renderer').renderToString(app)
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
await assert.rejects(api.request('/profile', { auth: true }), (cause) => cause.code === -1)
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

const filterCalls = []
const filteredApi = loader({ '@/request': { request: async (path, options) => { filterCalls.push({ path, options }); return {} } } })
await filteredApi('@/api/episodes').listEpisodes('ready,saved', 2, 'clinic')
await filteredApi('@/api/health').listVitals(3, 'bp')
await filteredApi('@/api/medications').getMedications('long_term', 'stopped')
await filteredApi('@/api/archive').getArchiveTrend(30, 50)
await filteredApi('@/api/medications').updateMedication(8, { status: 'active' })
assert.deepEqual(filterCalls.map((item) => item.path), ['/episodes?page=2&size=20&status=ready%2Csaved&triage=clinic', '/vitals?page=3&size=20&kind=bp', '/medications?kind=long_term&status=stopped', '/archive/trend?days=30&limit=50', '/medications/8'])
assert.equal(filterCalls[4].options.data.status, 'active')

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
  const creations = [], routes = [], flights = []
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
  return { auth, store, component, creations, routes, flights, stop: () => scope.stop(), setFail: (value) => { failCreate = value }, delay: () => { delayedDetail = true }, resolve: () => detailResolver?.(clone(detail)) }
}
for (const route of ['pages/index/index', 'pages/chat/index']) {
  const app = setup(route)
  await app.store.initialize()
  assert.equal(app.store.screen, route === 'pages/index/index' ? 'landing' : 'workspace')
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
  // 生成完成即自动归档（issue #24）：详情带 saved_at，没有任何保存请求要发
  app.store.detail.episode.saved_at = '2026-11-22 10:00:00'
  assert.equal(app.store.saved, true, 'A completed consult must read as archived')
  app.component.goHome()
  await settle()
  assert.equal(app.store.screen, 'landing', 'Returning home must restore the separate landing page')
  assert.equal(app.routes.at(-1), '/pages/index/index')
  assert.equal(app.store.messages[0].content, 'SYNTHETIC UI TEST', 'Returning home must preserve the active consultation')
  app.stop()
}

const archiveAuth = vue.reactive({ user: { id: 8 }, isLoggedIn: true })
const archiveWorkspace = vue.reactive({ auth: archiveAuth, activeTab: 'archive', history: [{ id: 900 }], historyTotal: 1 })
const archiveCalls = [], statusChanges = []
let releasePage, deferPage = false
const archiveModules = loader({
  vue: { ...vue, onMounted() {} },
  '@/stores/liveWorkspace': { useLiveWorkspaceStore: () => archiveWorkspace },
  '@/api/archive': { getArchiveOverview: async () => ({}), getArchiveTrend: async (...args) => { archiveCalls.push(['trend', ...args]); return {} } },
  '@/api/episodes': { listEpisodes: async (...args) => { archiveCalls.push(['episodes', ...args]); const result = { records: [{ id: args[1] }], total: 50 }; return deferPage ? new Promise((resolve) => { releasePage = () => resolve(result) }) : result } },
  '@/api/health': { listVitals: async (...args) => { archiveCalls.push(['vitals', ...args]); return { records: [], total: 50 } } },
  '@/api/medications': { getMedications: async (...args) => { archiveCalls.push(['medications', ...args]); return { records: [] } }, updateMedication: async (...args) => statusChanges.push(args) },
}, { uni: { showModal(options) { options.success({ confirm: true }) } } })
const archiveScope = vue.effectScope()
const archive = archiveScope.run(() => archiveModules('@/components/QLiveArchive.vue').default.setup({}, { expose() {} }))
archive.episodeStatusIndex.value = 4; archive.triageIndex.value = 2; archive.vitalFilterIndex.value = 1
archive.medicationKindIndex.value = 1; archive.medicationStatusIndex.value = 2; archive.trendDayIndex.value = 1; archive.trendLimitIndex.value = 2
await archive.load()
assert.deepEqual(archiveCalls.slice(-4).map((item) => Array.from(item)), [['episodes', 'saved', 1, 'clinic'], ['vitals', 1, 'bp'], ['medications', 'long_term', 'stopped'], ['trend', 30, 50]])
await archive.moreEpisodes()
assert.deepEqual(archiveCalls.at(-1), ['episodes', 'saved', 2, 'clinic'])
assert.equal(archive.episodes.value.length, 2)
assert.equal(archiveWorkspace.history[0].id, 900, 'Archive filters must not replace sidebar history')
await archive.moreVitals()
assert.deepEqual(archiveCalls.at(-1), ['vitals', 2, 'bp'])
archive.restoreMedication({ id: 8, status: 'stopped' })
await settle()
assert.equal(statusChanges[0][0], 8)
assert.equal(statusChanges[0][1].status, 'active')
deferPage = true
const stalePage = archive.moreEpisodes()
archiveAuth.user = null; archiveAuth.isLoggedIn = false
await settle()
releasePage()
await stalePage
assert.equal(archive.episodes.value.length, 0, 'A page response after logout must not restore health records')
archiveScope.stop()

const reviewProps = vue.reactive({ detail: { ...clone(detail), normalized: { symptom: ['SYNTHETIC SYMPTOM'], duration_text: 'unknown' }, self_attribution: 'SYNTHETIC ATTRIBUTION', gate: { red_flags: [{ rule_id: 'SYNTHETIC', name: 'SYNTHETIC FLAG' }], citations_verified: 0, citations_dropped: 2, clarify_rounds: 1 } }, pending: false })
const review = loader()('@/components/QEpisodeReview.vue').default.setup(reviewProps, { expose() {} })
assert.equal(review.fields.value[0].value, 'SYNTHETIC SYMPTOM')
assert.equal(review.fields.value[1].value, '本人暂不确定')
assert.equal(review.gate.value.citations_verified, 0)
assert.equal(review.gate.value.citations_dropped, 2)
assert.equal(review.gate.value.red_flags[0].name, 'SYNTHETIC FLAG')
const reviewHtml = await renderComponent('QEpisodeReview', reviewProps)
assert.match(reviewHtml, /SYNTHETIC ATTRIBUTION/)
assert.match(reviewHtml, /SYNTHETIC FLAG/)
assert.match(reviewHtml, /本人暂不确定/)
assert.doesNotMatch(reviewHtml, /待接入|待补充/)
reviewProps.detail = null
assert.equal(review.fields.value.length, 0)
assert.equal(review.hasGate.value, false)

const renderedWorkspace = { detail: clone(detail), result: clone(detail.result), questions: [], saved: true, pending: false, followUpReminder: null }
const renderFlow = () => renderComponent('QConsultationFlow', {}, { '@/stores/liveWorkspace': { useLiveWorkspaceStore: () => renderedWorkspace } })
assert.match(await renderFlow(), /按建议就诊前会收到提醒/)
renderedWorkspace.result.triage = 'emergency'
assert.doesNotMatch(await renderFlow(), /按建议就诊前会收到提醒|补建就诊提醒/)
renderedWorkspace.result = null
renderedWorkspace.followUpReminder = { title: 'SYNTHETIC FOLLOWUP', status: 'done' }
renderedWorkspace.followUpResponse = { advice: { text: 'SYNTHETIC ADVICE' }, supplement: { prepare_idx: [0, 2], watch_for: [], next_question: '' } }
assert.match(await renderFlow(), /2 项原问诊准备事项/)
assert.match(await renderFlow(), /查看问诊记录/)
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
await anonymous.component.handleSend()
assert.equal(anonymous.store.screen, 'landing', 'A sign-in prompt must keep the user on the landing page')
assert.equal(anonymous.routes.length, 0)
assert.equal(anonymous.flights.length, 0)
assert.equal(anonymous.creations.length, 0)
assert.equal(anonymous.store.draft, 'SYNTHETIC UNSENT')
assert.equal(anonymous.store.accountOpen, true)
anonymous.stop()

const formAuth = vue.reactive({ user: { id: 43 }, isLoggedIn: true, updateProfileComplete() {} })
const formWorkspace = vue.reactive({ patientProfile: clone(profile), initialized: true, error: '' })
const profileWrites = [], policyRoutes = [], bodyWrites = []
const bodyVitals = { latest_height_cm: 170, latest_weight_kg: 65 }
let rejectWeight = true
let rejectProfile = true
const formModules = loader({
  vue: { ...vue, onMounted() {} },
  '@/stores/auth': { useAuthStore: () => formAuth },
  '@/stores/liveWorkspace': { useLiveWorkspaceStore: () => formWorkspace },
  '@/api/profile': { updateProfile: async (payload) => { profileWrites.push(payload); if (rejectProfile) throw new Error('SYNTHETIC SAVE FAILED'); return { ...clone(profile), ...payload } } },
  '@/api/archive': { getArchiveOverview: async () => ({ vitals: { ...bodyVitals } }) },
  '@/api/health': { saveVital: async (payload) => {
    bodyWrites.push(payload)
    if (payload.kind === 'weight' && rejectWeight) throw new Error('SYNTHETIC WEIGHT SAVE FAILED')
    if (payload.kind === 'height') bodyVitals.latest_height_cm = payload.height_cm
    else bodyVitals.latest_weight_kg = payload.weight_kg
    return { height_cm: payload.height_cm ?? null, weight_kg: payload.weight_kg ?? null }
  } },
}, { uni: { navigateTo: ({ url }) => policyRoutes.push(url) } })
pinia.setActivePinia(pinia.createPinia())
const firstFormScope = vue.effectScope()
const firstForm = firstFormScope.run(() => formModules('@/components/QAccountPanel.vue').default.setup({}, { expose() {} }))
firstForm.form.value.name = 'SYNTHETIC UNSAVED'
firstForm.editing.value = true
firstForm.saveProfile()
await settle()
assert.match(firstForm.error.value, /SAVE FAILED/)
firstFormScope.stop()
const secondFormScope = vue.effectScope()
const secondForm = secondFormScope.run(() => formModules('@/components/QAccountPanel.vue').default.setup({}, { expose() {} }))
assert.equal(secondForm.form.value.name, 'SYNTHETIC UNSAVED', 'Reopening a failed form must retain the draft')
assert.equal(secondForm.editing.value, true)
assert.equal(profileWrites[0].city_code, null, 'An unselected optional city must be submitted as null')
assert.equal(profileWrites[0].city_name, null)
rejectProfile = false
secondForm.saveProfile()
await settle()
assert.equal(secondForm.error.value, '')
secondForm.openPolicy(false)
assert.equal(policyRoutes[0], '/pages/privacy/index?section=privacy')
await secondForm.loadMeasurements()
assert.equal(secondForm.measurements.value.height_cm, '170')
secondForm.measurements.value.height_cm = '172'
secondForm.measurements.value.weight_kg = '67'
secondForm.editing.value = true
secondForm.saveProfile()
await settle()
assert.match(secondForm.error.value, /尚未全部保存/)
assert.equal(secondForm.editor.savedMeasurements.height_cm, '172')
assert.equal(secondForm.editor.savedMeasurements.weight_kg, '65')
assert.equal(secondForm.measurements.value.weight_kg, '67', 'A failed weight save must preserve the draft')
secondFormScope.stop()
const reopenedFormScope = vue.effectScope()
const reopenedForm = reopenedFormScope.run(() => formModules('@/components/QAccountPanel.vue').default.setup({}, { expose() {} }))
await reopenedForm.loadMeasurements()
assert.equal(reopenedForm.measurements.value.weight_kg, '67', 'Reopening and reloading must not replace an unsaved measurement')
rejectWeight = false
reopenedForm.saveProfile()
await settle()
assert.equal(reopenedForm.error.value, '')
assert.deepEqual(bodyWrites.map((item) => item.kind), ['height', 'weight', 'weight'], 'Retry only measurements that have not already been saved')
reopenedForm.measurements.value.height_cm = '172.0'
reopenedForm.measurements.value.weight_kg = ''
reopenedForm.saveProfile()
await settle()
assert.equal(bodyWrites.length, 3, 'Equivalent numbers and empty optional fields must not create duplicate measurements')
assert.equal(reopenedForm.measurements.value.height_cm, '172')
assert.equal(reopenedForm.measurements.value.weight_kg, '67')
const previousProfileWrites = profileWrites.length
reopenedForm.measurements.value.height_cm = '40'
reopenedForm.saveProfile()
await settle()
assert.match(reopenedForm.error.value, /50–250/)
assert.equal(profileWrites.length, previousProfileWrites, 'Validate both measurements before writing any part of the form')
const cityChanges = []
const city = formModules('@/components/QCityPicker.vue').default.setup({ code: '', name: '' }, { expose() {}, emit: (...args) => cityChanges.push(args) })
city.choose({ detail: { value: [0, 0] } })
assert.equal(cityChanges[0][1].code, '110100')
assert.equal(cityChanges[0][1].name, '北京市')
formAuth.user = null; formAuth.isLoggedIn = false
await settle()
assert.equal(secondForm.form.value.name, '', 'Logout must clear the in-memory health draft')
assert.equal(reopenedForm.measurements.value.height_cm, '')
assert.equal(reopenedForm.measurements.value.weight_kg, '')
reopenedFormScope.stop()

const requestedDays = []
const weekModules = loader({
  vue: { ...vue, onMounted() {} },
  '@/stores/liveWorkspace': { useLiveWorkspaceStore: () => ({ auth: { user: { id: 5 }, isLoggedIn: true }, activeTab: 'plans', selectedPlanTab: 'all' }) },
  '@/api/archive': { getReminders: async (date) => { requestedDays.push(date); return { groups: { medication: [], followup: [{ id: Number(date.slice(-2)), due_at: `${date} 09:00:00` }], recheck: [] } } } },
  '@/api/health': { listSchedules: async () => ({ records: [] }) },
  '@/api/medications': { getMedications: async () => ({ records: [] }) },
})
const weekScope = vue.effectScope()
const week = weekScope.run(() => weekModules('@/components/QLivePlans.vue').default.setup({}, { expose() {} }))
week.day.value = '2026-12-28'
await week.load()
assert.equal(requestedDays.length, 7)
assert.equal(requestedDays[6], '2027-01-03')
assert.equal(week.reminders.value.length, 7)
assert.equal(week.reminders.value[0].due_at, '2026-12-28 09:00:00')
weekScope.stop()
class Button { disabled = false; clicks = 0; hasAttribute() { return this.disabled } click() { this.clicks += 1 } }
const keyboard = loader({}, { HTMLElement: Button })('@/components/buttonKeyboard')
const control = new Button()
for (const key of ['Enter', ' ', 'Tab']) keyboard.activateButton({ key, currentTarget: control, preventDefault() {} })
control.disabled = true
keyboard.activateButton({ key: 'Enter', currentTarget: control, preventDefault() {} })
assert.equal(control.clicks, 2)
console.log('Live interaction checks passed: authentication, SSE, message flight, retries, archive filters and pagination, reminder requests, medication status, review data and logout isolation.')
