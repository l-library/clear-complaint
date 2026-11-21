import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(import.meta.url)
const ts = require('typescript')
const { createPinia, setActivePinia } = require('pinia')
const source = readFileSync(new URL('../src/stores/consultation.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const legacyKey = 'clear-complaint.demo-archive.v1'
const storageKey = 'clear-complaint.workspace.v2'
const clone = (value) => JSON.parse(JSON.stringify(value))

function setup(stored = new Map(), options = {}) {
  let timestamp = Date.parse('2026-11-21T10:30:00Z')
  let failWrites = false
  let failReads = Boolean(options.failReads)
  let failRecoveryWrites = Boolean(options.failRecoveryWrites)
  let timerId = 0
  const timers = new Map()
  class Clock extends Date {
    constructor(...args) { super(...(args.length ? args : [timestamp])) }
    static now() { return timestamp }
  }
  const context = {
    exports: {}, require, Date: Clock,
    setTimeout(callback) { timers.set(++timerId, callback); return timerId },
    clearTimeout(key) { timers.delete(key) },
    uni: {
      getStorageSync(key) {
        if (failReads) throw new Error('storage read unavailable')
        return stored.has(key) ? clone(stored.get(key)) : ''
      },
      setStorageSync(key, value) {
        if (failWrites || (failRecoveryWrites && key.startsWith(`${storageKey}.recovery.`))) {
          throw new Error('storage unavailable')
        }
        stored.set(key, clone(value))
      },
    },
  }
  vm.runInNewContext(compiled, context, { filename: 'consultation.ts' })
  setActivePinia(createPinia())
  return {
    store: context.exports.useConsultationStore(), stored, timers,
    flush() {
      const callbacks = [...timers.values()]
      timers.clear()
      callbacks.forEach((callback) => callback())
    },
    failWrites(value) { failWrites = value },
    failReads(value) { failReads = value },
    failRecoveryWrites(value) { failRecoveryWrites = value },
    setTime(value) { timestamp = Date.parse(value) },
  }
}

const app = setup()
const store = app.store
assert.equal(store.today(), '2026-11-21')
assert.equal(store.now(), '2026-11-21 18:30:00')
assert.equal(store.episodes.length, 1)
assert.equal(store.plans.length, 2)
assert.equal(store.records.length, 2)

store.draft = '合成演示：记录不适出现时间'
store.sendMessage()
const firstId = store.activeConversation.id
assert.equal(store.pending, true)
assert.equal(store.messages.length, 1)
assert.equal(store.openConversation(firstId), true)
assert.equal(store.pending, true, 'Opening the active route must keep its pending reply')
assert.equal(app.timers.size, 1)
store.openWorkspace('archive')
assert.equal(store.pending, true, 'Changing workspace tabs must keep the conversation reply running')
assert.equal(store.saveConversation(), undefined)
assert.equal(store.pending, true, 'Saving during a pending reply must not cancel that reply')
assert.equal(app.timers.size, 1)
store.openWorkspace('chat')
app.flush()
assert.equal(store.messages.length, 2)
const firstRecord = store.saveConversation()
assert.ok(firstRecord)
assert.equal(store.saved, true)
const recordCount = store.records.length
assert.equal(store.saveConversation().id, firstRecord.id)
assert.equal(store.records.length, recordCount)
store.draft = '合成演示：补充持续时间'
store.sendMessage()
app.flush()
assert.equal(store.saveConversation().id, firstRecord.id)
assert.equal(store.records.length, recordCount, 'Saving more messages updates the same health record')
store.draft = '留在第一段对话的草稿'
const secondId = store.newConversation()
assert.equal(store.draft, '')
store.draft = '第二段对话内容'
store.sendMessage()
assert.equal(store.pending, true)
store.openConversation(firstId)
assert.equal(store.pending, false)
assert.equal(app.timers.size, 0)
assert.equal(store.draft, '留在第一段对话的草稿')
app.flush()
assert.equal(store.messages.length, 4, 'Switching a conversation cannot write the old reply into this chat')
assert.equal(store.conversations.find((item) => item.id === secondId).messages.length, 1)

const followUpId = store.startFollowUp('demo-follow-up')
assert.ok(followUpId)
assert.equal(store.startFollowUp('demo-follow-up'), followUpId)
assert.equal(store.activeConversation.type, 'follow_up')
assert.ok(store.messages[0].content.includes('随访目标'))
assert.ok(store.messages[0].content.includes(store.currentEpisode.title))
assert.equal(store.saveConversation(), undefined, 'An unanswered follow-up cannot be completed')
store.draft = '合成演示：补充这段时间的变化'
store.sendMessage()
app.flush()
const followUpRecord = store.saveConversation()
assert.equal(followUpRecord.source, 'ai_follow_up')
assert.equal(followUpRecord.healthEpisodeId, 'demo-stomach')
assert.equal(store.activeConversation.status, 'completed')
assert.equal(store.plans.find((item) => item.id === 'demo-follow-up').status, 'completed')
assert.equal(store.setPlanStatus('demo-follow-up', 'in_progress'), false)
assert.equal(store.activeConversation.status, 'completed', 'A completed follow-up cannot be resumed by a status change')
const afterFollowUp = store.records.length
assert.equal(store.startFollowUp('demo-follow-up'), followUpId)
assert.equal(store.saveConversation().id, followUpRecord.id)
assert.equal(store.records.length, afterFollowUp)
store.draft = '完成后尝试补充'
store.sendMessage()
assert.match(store.error, /已完成/)
assert.equal(store.draft, '完成后尝试补充')
assert.equal(store.pending, false)
assert.equal(store.conversations.filter((item) => item.followUpPlanId === 'demo-follow-up').length, 1)
const completedMessages = store.messages.length
store.screen = 'landing'
assert.equal(store.draft, '', 'The home composer has its own draft even when a follow-up is selected')
store.draft = '从首页开始的独立合成咨询'
assert.equal(store.conversations.find((item) => item.id === followUpId).draft, '完成后尝试补充')
store.sendMessage()
assert.notEqual(store.activeConversation.id, followUpId)
assert.equal(store.activeConversation.type, 'consultation')
assert.equal(store.activeConversation.followUpPlanId, undefined)
assert.equal(store.activeConversation.healthEpisodeId, undefined)
assert.equal(store.conversations.find((item) => item.id === followUpId).messages.length, completedMessages)
app.flush()
store.screen = 'landing'
store.draft = '重新打开首页时保留的独立草稿'
const homeReload = setup(app.stored).store
assert.equal(homeReload.screen, 'landing')
assert.equal(homeReload.draft, '重新打开首页时保留的独立草稿')
homeReload.openConversation(followUpId)
assert.equal(homeReload.draft, '完成后尝试补充', 'Opening a selected historical chat restores that chat draft')
store.openWorkspace('chat')

const imported = store.importMedicalRecord({
  healthEpisodeId: '', episodeTitle: '虚构第二健康事件', title: '手动录入的虚构门诊记录',
  date: '2026-11-20', institution: '虚构机构', department: '', documentedDiagnosis: '',
  medicalInstructions: '', summary: '只保存手动核对的合成资料',
})
assert.ok(imported)
assert.equal(store.activeTab, 'archive')
assert.equal(store.selectedRecordId, imported.id)
assert.ok(store.episodes.some((item) => item.id === imported.healthEpisodeId))
assert.equal(store.createFollowUpPlan({
  healthEpisodeId: 'demo-stomach', sourceRecordId: imported.id, title: '错误关联',
  scheduledAt: '2026-11-22 09:00', goal: '合成目标', questions: ['合成问题'],
}), undefined, 'A source record from a different episode must be rejected')
assert.ok(store.createFollowUpPlan({
  healthEpisodeId: imported.healthEpisodeId, sourceRecordId: imported.id, title: '手动随访',
  scheduledAt: '2026-11-22T09:00', goal: '回顾合成记录', questions: ['有新的资料吗？'],
}))

const medicationInput = {
  healthEpisodeId: 'demo-stomach', medicineName: '合成示例药物', instructions: '仅合成流程说明，无真实剂量',
  reminderTimes: ['08:00', '08:00', '22:00'], startDate: '2026-11-21', endDate: '2026-11-23',
  sourceLabel: '虚构个人医嘱', sourceConfirmed: true,
}
assert.equal(store.createMedicationPlan({ ...medicationInput, sourceConfirmed: false }), undefined)
assert.equal(store.createMedicationPlan({ ...medicationInput, sourceLabel: '药品说明书' }), undefined)
assert.equal(store.createMedicationPlan({ ...medicationInput, reminderTimes: ['25:00'] }), undefined)
assert.equal(store.createMedicationPlan({ ...medicationInput, endDate: '2026-02-30' }), undefined)
const medication = store.createMedicationPlan(medicationInput)
assert.ok(medication)
assert.equal(medication.reminderTimes.length, 2)
assert.equal(store.markMedication(medication.id, '22:00', 'taken'), false, 'Future occurrences cannot be checked in')
assert.equal(store.markMedication(medication.id, '08:00', 'taken'), true)
assert.equal(store.markMedication(medication.id, '08:00', 'taken'), true)
assert.equal(store.markMedication(medication.id, '08:00', 'skipped'), false)
assert.equal(store.medicationCheckIns.length, 1)
assert.equal(store.medicationOutcome(medication.id, '08:00'), 'taken')
assert.equal(store.setPlanStatus(medication.id, 'completed'), false)
assert.equal(store.setPlanStatus(medication.id, 'paused'), true)
assert.equal(store.markMedication(medication.id, '08:00', 'taken'), false)
store.setPlanStatus(medication.id, 'active')
app.setTime('2026-11-24T10:00:00Z')
assert.equal(store.markMedication(medication.id, '08:00', 'taken'), false, 'Ended date ranges cannot be checked in')

const restored = setup(app.stored).store
assert.equal(restored.error, '')
assert.equal(restored.conversations.length, store.conversations.length)
assert.equal(restored.records.length, store.records.length)
assert.equal(restored.medicationCheckIns.length, 1)
restored.openConversation(firstId)
assert.equal(restored.draft, '留在第一段对话的草稿')

app.failWrites(true)
store.newConversation()
store.draft = '存储失败时仍保留的合成内容'
store.sendMessage()
app.flush()
const inMemoryRecord = store.saveConversation()
assert.ok(inMemoryRecord)
assert.equal(store.messages.length, 2)
assert.ok(store.records.some((item) => item.id === inMemoryRecord.id))
assert.match(store.error, /本地保存失败/)
app.failWrites(false)
assert.equal(store.persist(), true)

const legacy = [{
  id: 'legacy-synthetic', title: '旧版合成记录', date: '2026-11-18 09:30', summary: '合成摘要',
  complaint: '合成主诉', status: '已归档', messages: [{ id: 'legacy-message', role: 'user', content: '迁移保留的合成消息' }],
}]
const migrated = setup(new Map([[legacyKey, legacy]]))
assert.equal(migrated.store.records.some((item) => item.id === 'legacy-synthetic'), true)
assert.equal(migrated.store.conversations.some((item) => item.messages[0]?.content === '迁移保留的合成消息'), true)
assert.deepEqual(migrated.stored.get(legacyKey), legacy, 'Migration must leave the old storage key untouched')
assert.equal(migrated.stored.get(storageKey).version, 2)
assert.equal(setup(migrated.stored).store.error, '')
const originalCorrupted = { version: 2, conversations: 'invalid', preserved: '损坏快照中的合成原始内容' }
const corrupted = new Map([[storageKey, originalCorrupted]])
const invalid = setup(corrupted)
assert.match(invalid.store.error, /格式异常/)
assert.deepEqual(corrupted.get(storageKey), originalCorrupted)
invalid.store.draft = '异常恢复后继续填写的合成内容'
invalid.store.sendMessage()
invalid.flush()
const recoveryEntries = [...corrupted].filter(([key]) => key.startsWith(`${storageKey}.recovery.`))
assert.equal(recoveryEntries.length, 1)
assert.deepEqual(recoveryEntries[0][1], originalCorrupted, 'The original malformed value must survive every later edit')
assert.equal(corrupted.get(storageKey).version, 2)
assert.equal(setup(corrupted).store.error, '')

const failedBackup = setup(new Map([[storageKey, originalCorrupted]]), { failRecoveryWrites: true })
failedBackup.store.draft = '备份失败时的合成草稿'
failedBackup.store.sendMessage()
failedBackup.flush()
assert.equal(failedBackup.store.persist(), false)
assert.match(failedBackup.store.error, /本地保存失败/)
assert.deepEqual(failedBackup.stored.get(storageKey), originalCorrupted, 'A failed backup must prevent replacing the original')
assert.equal([...failedBackup.stored.keys()].some((key) => key.startsWith(`${storageKey}.recovery.`)), false)
assert.equal(failedBackup.store.messages.length, 2)
failedBackup.failRecoveryWrites(false)
assert.equal(failedBackup.store.persist(), true)
assert.deepEqual([...failedBackup.stored].find(([key]) => key.startsWith(`${storageKey}.recovery.`))[1], originalCorrupted)

const failedRead = setup(new Map([[storageKey, originalCorrupted]]), { failReads: true })
assert.match(failedRead.store.error, /本地保存失败/)
failedRead.store.draft = '无法读取原存储时的合成草稿'
assert.equal(failedRead.store.persist(), false)
assert.deepEqual(failedRead.stored.get(storageKey), originalCorrupted)
failedRead.failReads(false)
assert.equal(failedRead.store.persist(), true)
assert.deepEqual([...failedRead.stored].find(([key]) => key.startsWith(`${storageKey}.recovery.`))[1], originalCorrupted)

console.log('Workspace checks passed: conversations, archive, follow-up, medication, persistence and migration.')
