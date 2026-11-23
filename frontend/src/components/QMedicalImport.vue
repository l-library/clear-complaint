<template>
  <view class="import-panel">
    <button role="button" tabindex="0" @keydown="activateButton" class="back-button" @click="emit('cancel')">‹ 返回档案（保留本页填写）</button>
    <view class="panel-heading">
      <QIcon name="file" />
      <view><text class="title">导入医院病历</text><text class="muted">逐项核对原文，让就诊记录与后续随访连在一起。</text></view>
    </view>
    <view class="notice"><QIcon name="info" /><text>文字识别待接入，可手动核对填写。图片仅供本次预览，原图不会存入档案；保存文件名和核对后的文字。本地演示未接入医院系统。</text></view>
    <view v-show="!medicalDraft.pendingRecordId">
    <view class="image-area">
      <image v-if="previewPath" class="document-preview" :src="previewPath" mode="aspectFit" aria-label="本次选择的病历图片" />
      <QIcon v-else name="file" />
      <text>{{ sourceFileName || '可选一张病历照片，也可以直接手动录入' }}</text>
      <view class="actions"><button role="button" tabindex="0" @keydown="activateButton" class="secondary" @click="chooseImage">{{ previewPath ? '重新选择照片' : '选择病历照片' }}</button><button role="button" tabindex="0" @keydown="activateButton" class="text-button" @click="fillExample">填入演示样例</button></view>
    </view>
    <view class="form-grid">
      <view class="field full"><text class="label">关联健康问题 *</text><picker :range="episodeOptions" :value="episodeIndex" @change="changeEpisode"><view class="picker-value">{{ episodeOptions[episodeIndex] }}<text>⌄</text></view></picker></view>
      <view v-if="episodeIndex === 0" class="field full"><label class="label" for="import-episode">新健康问题名称 *</label><input id="import-episode" v-model="form.episodeTitle" class="input" maxlength="60" placeholder="如：近期反复头晕" /></view>
      <view class="field"><label class="label" for="import-title">病历标题 *</label><input id="import-title" v-model="form.title" class="input" maxlength="80" placeholder="如：门诊就诊记录" /></view>
      <view class="field"><text class="label">就诊日期（病历记载）*</text><picker mode="date" :value="form.date" :end="today" @change="form.date = String($event.detail.value)"><view class="picker-value">{{ form.date || '请选择就诊日期' }}<QIcon name="calendar" /></view></picker></view>
      <view class="field"><label class="label" for="import-institution">就诊机构 *</label><input id="import-institution" v-model="form.institution" class="input" maxlength="80" placeholder="按病历原文填写" /></view>
      <view class="field"><label class="label" for="import-department">科室（选填）</label><input id="import-department" v-model="form.department" class="input" maxlength="60" placeholder="按病历原文填写" /></view>
      <view class="field full"><label class="label" for="import-diagnosis">病历记载诊断（选填）</label><textarea id="import-diagnosis" v-model="form.documentedDiagnosis" class="textarea" maxlength="2000" placeholder="照录原文，保留“考虑”“疑似”等措辞；未记载可留空" /><text class="hint">核对转录内容，不代表对诊断作出新的确认。</text></view>
      <view class="field full"><label class="label" for="import-summary">就诊情况摘要 *</label><textarea id="import-summary" v-model="form.summary" class="textarea" maxlength="3000" placeholder="按原文记录症状、检查和就诊经过，避免补写推测" /></view>
      <view class="field full"><label class="label" for="import-instructions">病历医嘱（选填）</label><textarea id="import-instructions" v-model="form.medicalInstructions" class="textarea" maxlength="3000" placeholder="逐项核对原文，未记载可留空。保存后可另行确认并创建计划" /></view>
    </view>
    <button tabindex="0" @keydown="activateButton" class="confirmation" role="checkbox" :aria-checked="confirmed" @click="confirmed = !confirmed"><view class="check-box" :class="{ checked: confirmed }"><QIcon v-if="confirmed" name="check" /></view><text>我已对照原始病历核对转录内容，并保留原文中的不确定表述。</text></button>
    </view>
    <text v-if="error || medicalDraft.pendingRecordId" class="error" role="alert">{{ error || '记录尚未写入本地，当前填写已保留。请重试保存，不会重复创建。' }}</text>
    <view class="actions"><button role="button" tabindex="0" @keydown="activateButton" class="primary" @click="save"><QIcon name="save" />{{ medicalDraft.pendingRecordId ? '重试本地保存' : '保存核对归档' }}</button><button role="button" tabindex="0" @keydown="activateButton" class="secondary" @click="emit('cancel')">暂存填写，返回档案</button></view>
    <text class="footnote">归档保存在当前设备。未提交内容在本次打开应用期间暂存，刷新后会丢失；图片预览仅限本次页面。就诊日期按原病历保留。</text>
  </view>
</template>

<script lang="ts">
import { reactive } from 'vue'

const medicalDraft = reactive({
  episodeIndex: 0,
  form: { episodeTitle: '', title: '', date: '', institution: '', department: '', documentedDiagnosis: '', medicalInstructions: '', summary: '' },
  confirmed: false,
  sourceFileName: '',
  pendingRecordId: '',
})
</script>

<script setup lang="ts">
import { activateButton } from '@/components/buttonKeyboard'
import { computed, ref, toRefs } from 'vue'
import QIcon from '@/components/QIcon.vue'
import { useConsultationStore } from '@/stores/consultation'

const store = useConsultationStore()
const emit = defineEmits<{ (event: 'done', recordId: string): void; (event: 'cancel'): void }>()
const { episodeIndex, confirmed, sourceFileName } = toRefs(medicalDraft)
const episodeOptions = computed(() => ['新建健康问题', ...store.episodes.map((episode) => episode.title)])
const form = medicalDraft.form
const error = ref('')
const previewPath = ref('')
const today = computed(() => store.today())

function changeEpisode(event: { detail: { value: string | number } }) {
  episodeIndex.value = Number(event.detail.value)
}

function chooseImage() {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    success(result) {
      const path = result.tempFilePaths[0]
      if (!path) return
      previewPath.value = path
      sourceFileName.value = path.split(/[\\/]/).pop()?.split('?')[0] || '本次选择的病历图片'
      error.value = ''
    },
    fail(result) {
      if (!result.errMsg.includes('cancel')) error.value = '未能读取图片，可重试或直接手动录入。已填写内容已保留。'
    },
  })
}

function fillExample() {
  const apply = () => {
    Object.assign(form, { episodeTitle: '演示：鼻部不适', title: '演示：门诊记录', date: today.value, institution: '虚构示范医院', department: '耳鼻喉科', documentedDiagnosis: '考虑过敏性鼻炎（演示原文，非真实诊断）', summary: '虚构示例：鼻塞、流清涕数日，记录门诊沟通情况。', medicalInstructions: '演示原文：记录症状变化，如有不适及时复诊。' })
    episodeIndex.value = 0
    sourceFileName.value = '虚构演示样例（非图片识别结果）'
    previewPath.value = ''
    confirmed.value = false
    error.value = ''
  }
  if (Object.values(form).some((value) => value.trim()) || previewPath.value) {
    uni.showModal({ title: '替换当前填写？', content: '演示样例会替换本页内容。当前填写尚未归档。', confirmText: '填入样例', success: (result) => { if (result.confirm) apply() } })
  } else apply()
}

function save() {
  error.value = ''
  if (medicalDraft.pendingRecordId) {
    if (!store.persist()) { error.value = store.error; return }
    store.error = ''
    finishSave(medicalDraft.pendingRecordId)
    return
  }
  if (!form.title.trim() || !form.date || !form.institution.trim() || !form.summary.trim()) {
    error.value = '请填写病历标题、就诊日期、就诊机构和就诊情况摘要。'
    return
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(form.date) || form.date > today.value) { error.value = '请选择有效且不晚于今天的就诊日期。'; return }
  if (episodeIndex.value === 0 && !form.episodeTitle.trim()) { error.value = '请为本次记录填写健康问题名称，或选择已有问题。'; return }
  if (!confirmed.value) { error.value = '请先核对病历原文，再勾选转录核对确认。'; return }
  const record = store.importMedicalRecord({ ...form, healthEpisodeId: store.episodes[episodeIndex.value - 1]?.id || '', sourceFileName: sourceFileName.value || '手动录入' })
  if (!record) { error.value = store.error || '未能保存归档，请检查填写并重试。当前内容已保留。'; return }
  if (store.error) { medicalDraft.pendingRecordId = record.id; store.archiveMode = 'import'; error.value = `${store.error} 请点击“重试本地保存”，不会重复创建记录。`; return }
  finishSave(record.id)
}

function finishSave(recordId: string) {
  Object.keys(form).forEach((key) => { form[key as keyof typeof form] = '' })
  confirmed.value = false
  sourceFileName.value = ''
  previewPath.value = ''
  episodeIndex.value = 0
  medicalDraft.pendingRecordId = ''
  emit('done', recordId)
}
</script>

<style scoped>
.import-panel { color: var(--ink, #1b1b18); }
.back-button, .text-button { margin: 0; padding: 8px 0; background: transparent; color: var(--accent, #2463eb); text-align: left; font-size: 14px; }
.panel-heading { display: flex; gap: 14px; margin: 20px 0; align-items: flex-start; }
.title { display: block; font-size: 24px; font-weight: 650; line-height: 1.5; }
.muted, .hint, .footnote { display: block; color: var(--muted, #767674); font-size: 13px; line-height: 1.7; }
.notice { display: flex; gap: 10px; padding: 16px; background: var(--surface-soft, #f5f5f0); border: 1px solid var(--line, #e4e4df); border-radius: 14px; color: #5f5f5b; font-size: 13px; line-height: 1.8; }
.image-area { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 24px 16px; margin: 20px 0; border: 1px dashed #d0d0c8; border-radius: 16px; text-align: center; font-size: 14px; overflow-wrap: anywhere; }
.document-preview { width: 100%; max-width: 360px; height: 220px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.field { min-width: 0; }
.full { grid-column: 1 / -1; }
.label { display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600; line-height: 1.6; }
.input, .picker-value, .textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--line, #e4e4df); border-radius: 10px; background: #fff; color: var(--ink, #1b1b18); font-size: 14px; }
.input { height: 48px; padding: 0 13px; }
.picker-value { display: flex; align-items: center; justify-content: space-between; min-height: 48px; padding: 10px 13px; gap: 10px; }
.textarea { height: 112px; padding: 12px 13px; line-height: 1.8; }
.hint { margin-top: 6px; }
.confirmation { display: flex; width: 100%; align-items: flex-start; gap: 10px; margin: 22px 0 12px; padding: 10px 0; background: transparent; text-align: left; color: #5f5f5b; font-size: 14px; line-height: 1.8; }
.check-box { display: flex; flex-shrink: 0; align-items: center; justify-content: center; width: 22px; height: 22px; margin-top: 2px; border: 1px solid #c6c6bf; border-radius: 5px; }
.checked { background: var(--surface-tint, #f0f5ff); border-color: var(--accent, #2463eb); }
.check-box .q-icon { width: 18px; height: 18px; }
.actions { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
button { min-height: 44px; box-sizing: border-box; line-height: 1.6; }
.primary, .secondary { display: flex; justify-content: center; align-items: center; gap: 8px; margin: 0; border-radius: 10px; padding: 12px 18px; font-size: 14px; }
.primary { color: #fff; background: var(--accent, #2463eb); }
.primary :deep(.q-icon) { filter: brightness(0) invert(1); }
.secondary { color: var(--accent, #2463eb); border: 1px solid var(--line, #e4e4df); background: #fff; }
.error { display: block; padding: 12px 14px; margin-bottom: 14px; background: #fff1f0; color: #a13d39; border-radius: 10px; font-size: 14px; line-height: 1.7; }
.footnote { margin-top: 18px; }
@media (max-width: 620px) { .form-grid { grid-template-columns: minmax(0, 1fr); gap: 17px; } .title { font-size: 22px; } .actions { width: 100%; } .actions .primary { width: 100%; } .actions .secondary { flex: 1; } }
</style>
