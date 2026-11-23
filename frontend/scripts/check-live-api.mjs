import assert from 'node:assert/strict'
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { randomInt, randomUUID } from 'node:crypto'
import vm from 'node:vm'

// Opt-in integration check against the running app, using only a disposable synthetic account.
const origin = process.env.LIVE_APP_ORIGIN || 'http://127.0.0.1:5175'
assert(['localhost', '127.0.0.1'].includes(new URL(origin).hostname), 'Only local integration targets are allowed')
const require = createRequire(import.meta.url)
const ts = require('typescript'), vue = require('vue'), pinia = require('pinia')
const src = new URL('../src/', import.meta.url)
const cache = new Map(), storage = new Map(), checks = []
const routes = new Set()
async function liveFetch(path, options) {
  const url = new URL(path, origin)
  routes.add(`${options?.method || 'GET'} ${url.pathname.replace(/\/\d+(?=\/|$)/g, '/{id}').replace(/(\/export)\/.+/, '$1/{token}')}`)
  return fetch(url, options)
}
const uni = {
  getStorageSync: (key) => storage.get(key) || '',
  setStorageSync: (key, value) => storage.set(key, JSON.parse(JSON.stringify(value))),
  removeStorageSync: (key) => storage.delete(key),
  request(options) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), options.timeout || 15000)
    void liveFetch(options.url, {
      method: options.method || 'GET', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...options.header },
      body: options.data ? JSON.stringify(options.data) : undefined,
    }).then(async (response) => options.success({ statusCode: response.status, data: await response.json() }))
      .catch((error) => options.fail({ errMsg: error.message })).finally(() => clearTimeout(timer))
    return { abort: () => controller.abort() }
  },
}
function h5(source) {
  const flags = [true]
  return source.split('\n').filter((line) => {
    const match = line.match(/\/\/\s*#(ifdef|ifndef)\s+(\S+)/)
    if (match) { flags.push(flags.at(-1) && (match[2] === 'H5' ? match[1] === 'ifdef' : match[1] === 'ifndef')); return false }
    if (/#endif/.test(line)) { flags.pop(); return false }
    return flags.at(-1)
  }).join('\n')
}
function load(name) {
  if (name === 'vue') return vue
  if (name === 'pinia') return pinia
  if (!name.startsWith('@/')) return require(name)
  if (cache.has(name)) return cache.get(name)
  let url = new URL(name.slice(2) + '.ts', src)
  if (!existsSync(url)) url = new URL(name.slice(2) + '/index.ts', src)
  const result = {}
  cache.set(name, result)
  const compiled = ts.transpileModule(h5(readFileSync(url, 'utf8')), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  vm.runInNewContext(compiled, {
    exports: result, require: load, uni, console, Date, Error, setTimeout, clearTimeout,
    ArrayBuffer, Uint8Array, AbortController, fetch: liveFetch, crypto: { randomUUID },
    window: { addEventListener() {}, removeEventListener() {} },
  })
  return result
}
function passed(name) { checks.push(name); console.log(`PASS ${name}`) }
const meta = load('@/api/meta'), profile = load('@/api/profile'), health = load('@/api/health')
const archive = load('@/api/archive'), medications = load('@/api/medications'), account = load('@/api/account')
const episodes = load('@/api/episodes'), request = load('@/request'), sessions = load('@/auth/session')
pinia.setActivePinia(pinia.createPinia())
const auth = load('@/stores/auth').useAuthStore()
const phone = '000' + String(randomInt(0, 100000000)).padStart(8, '0')
const password = 'Synthetic1' + randomUUID().slice(0, 12)
const measuredAt = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date())
const today = measuredAt.slice(0, 10)
let registered = false, cleaned = false, failure, triageMode
try {
  assert.equal((await liveFetch('/api/health')).status, 200)
  passed('Vite /api proxy reaches the real backend')
  const privacy = await meta.getPrivacyMeta()
  await auth.register({ phone, password, consent_version: privacy.current_version, accept_privacy: true, accept_sensitive: true })
  registered = true
  assert.equal((await profile.getProfile()).profile, null)
  assert.equal((await health.getConsentRecord()).consented_version, privacy.current_version)
  passed('Register, JWT session, profile read and privacy consent')
  await auth.logout()
  await auth.login(phone, password)
  assert.equal(await request.refreshAccessToken(), true)
  await auth.ensureFreshSession()
  passed('Login, rotating refresh token and logout')
  const savedProfile = await profile.updateProfile({ name: 'SYNTHETIC', birth_date: '2000-01-01', sex: 'undisclosed', conditions: [], allergies: null })
  assert.equal(savedProfile.required_missing.length, 0)
  assert.equal(savedProfile.allergies, null)
  assert.equal(savedProfile.conditions.length, 0)
  passed('Profile update preserves unknown versus explicitly none')
  const height = await health.saveVital({ kind: 'height', height_cm: 170, measured_at: measuredAt })
  const weight = await health.saveVital({ kind: 'weight', weight_kg: 65, measured_at: measuredAt })
  await health.saveVital({ kind: 'bp', systolic: 120, diastolic: 80, measured_at: measuredAt })
  await health.saveVital({ kind: 'weight', weight_kg: 66, measured_at: measuredAt }, weight.id)
  assert.equal((await health.listVitals()).total, 3)
  const bloodPressure = await health.listVitals(1, 'bp')
  assert.equal(bloodPressure.total, 1)
  assert(bloodPressure.records.every((item) => item.kind === 'bp'))
  assert.equal((await archive.getArchiveOverview()).vitals.latest_weight_kg, 66)
  assert.equal((await archive.getArchiveTrend()).weight_points.length, 1)
  await health.deleteVital(height.id)
  passed('Vital CRUD, archive overview and trend')
  const medication = await medications.createMedication({ name: 'SYNTHETIC CHECK', dosage_text: 'SYNTHETIC ONLY', kind: 'long_term', started_on: today })
  await medications.updateMedication(medication.id, { frequency_text: 'SYNTHETIC ONLY' })
  assert.equal((await medications.getMedications()).records.length, 1)
  await medications.updateMedication(medication.id, { status: 'stopped' })
  assert.equal((await medications.getMedications('long_term', 'active')).records.length, 0)
  await medications.updateMedication(medication.id, { status: 'active' })
  assert.equal((await medications.getMedications('long_term', 'active')).records.length, 1)
  const plan = await health.createSchedule({ medication_id: medication.id, times: ['08:00'], started_on: today })
  assert.equal((await health.updateSchedule(plan.id, { status: 'stopped' })).status, 'stopped')
  await health.updateSchedule(plan.id, { status: 'active' })
  assert.equal((await health.listSchedules()).records.length, 1)
  await health.deleteSchedule(plan.id)
  await health.deleteMedication(medication.id)
  passed('Medication CRUD and reminder plan CRUD, pause and resume')
  const workspace = load('@/stores/liveWorkspace').useLiveWorkspaceStore()
  await workspace.initialize()
  workspace.draft = '【软件合成联调】我26岁，三天前早晨开始流鼻涕，持续三天。主要在鼻部，是清水样鼻涕，程度较轻。偶尔打喷嚏，除此之外没有其他不适。最近没有服用药物，没有已知过敏史。'
  assert.equal(workspace.sendMessage(), true)
  async function waitForStream() {
    const deadline = Date.now() + 70000
    while (workspace.pending && Date.now() < deadline) await new Promise((resolve) => setTimeout(resolve, 100))
  }
  await waitForStream()
  const syntheticAnswers = { symptom: '流鼻涕', onset: '三天前早晨', onset_at: '三天前早晨', duration: '三天', duration_text: '三天', location: '鼻部', site: '鼻部', character: '清水样鼻涕，程度较轻', nature: '清水样鼻涕，程度较轻', associated_symptoms: '偶尔打喷嚏，无其他不适', associated: '偶尔打喷嚏，无其他不适', medication: '最近没有服用药物', medications_text: '最近没有服用药物' }
  for (let round = 0; workspace.questions.length && round < 2; round += 1) {
    for (const question of workspace.questions) workspace.answers[question.field] = syntheticAnswers[question.field] || '不确定'
    await workspace.submitAnswers()
    await waitForStream()
  }
  assert.equal(workspace.pending, false, 'SSE must complete within the configured timeout')
  assert.equal(workspace.error, '')
  assert(workspace.episodeId > 0)
  assert(workspace.result)
  assert.equal(workspace.messages[0].role, 'user')
  triageMode = workspace.detail.gate?.fallback ? 'server_fallback' : 'generated_with_backend_gates'
  assert(workspace.detail.normalized)
  assert(Array.isArray(workspace.detail.gate.red_flags))
  assert.equal(typeof workspace.detail.gate.citations_verified, 'number')
  await workspace.saveConversation(false)
  assert(workspace.saved)
  assert.equal((await episodes.listEpisodes()).total, 1)
  assert.equal((await episodes.listEpisodes('saved', 1, workspace.result.triage)).total, 1)
  assert.equal((await episodes.listEpisodes('failed', 1, workspace.result.triage)).total, 0)
  await archive.getArchiveTrend(7, 20)
  passed(`Real frontend store, SSE parser, detail, history and save (${triageMode})`)
  const id = workspace.episodeId
  const saved = await episodes.saveEpisode(id, true)
  assert(saved.reminder)
  const reminders = await archive.getReminders(saved.reminder.due_at.slice(0, 10))
  assert(reminders.groups[saved.reminder.kind].some((item) => item.id === saved.reminder.id))
  const response = await archive.respondReminder(saved.reminder.id, saved.reminder.kind === 'followup'
    ? { action: 'answer', answers: { relieved: 'no', visited: 'no', new_symptom: 'no' }, note: 'SYNTHETIC INTEGRATION CHECK' }
    : { action: 'visited' })
  assert.equal(response.status, 'done')
  passed(`Archived episode adds a real ${saved.reminder.kind} reminder and accepts a response`)
  const emergencyEvents = []
  await episodes.createEpisodeStream('SYNTHETIC INTEGRATION CHECK: 胸口疼，没有缓解，出汗', (event) => emergencyEvents.push(event))
  const emergencyDone = emergencyEvents.find((event) => event.event === 'done')
  assert.equal(emergencyDone?.data.triage, 'emergency')
  await episodes.deleteEpisode(emergencyDone.data.episode_id)
  passed('Rule-based red flag SSE path and episode deletion')
  const exported = await account.exportAccountData()
  const download = await liveFetch(exported.url)
  assert.equal(download.status, 200)
  const bytes = new Uint8Array(await download.arrayBuffer())
  assert.deepEqual(Array.from(bytes.slice(0, 2)), [80, 75])
  assert.equal((await liveFetch(exported.url)).status, 404)
  passed('Real ZIP export and one-time download token')
  await account.clearAccountData()
  assert.equal((await episodes.listEpisodes()).total, 0)
  assert.equal((await health.listVitals()).total, 0)
  passed('Clear synthetic health data')
} catch (error) { failure = error }
finally {
  if (registered) {
    try {
      if (!auth.isLoggedIn) await auth.login(phone, password)
      await account.deleteAccount()
      auth.clearLocalSession()
      cleaned = true
      passed('Delete temporary synthetic account')
    } catch (error) { failure ||= error }
  }
  const report = { origin, synthetic_data_only: true, cleaned, triage_mode: triageMode, checks, routes: [...routes].sort(), passed: !failure, failure: failure?.message || null }
  mkdirSync(new URL('../../output/', import.meta.url), { recursive: true })
  writeFileSync(new URL('../../output/live-api-check.json', import.meta.url), JSON.stringify(report, null, 2) + '\n')
}
if (failure) throw failure
console.log(`Live integration passed: ${checks.length} checks; no synthetic account retained.`)
