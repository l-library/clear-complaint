<template>
  <view class="consultation-flow live-ui">
    <view v-if="workspace.followUpReminder" class="live-card">
      <text class="live-subtitle">{{ workspace.followUpReminder.title }}</text>
      <template v-if="workspace.followUpReminder.status === 'pending'">
        <view v-for="question in followUpQuestions" :key="question.field" class="question-field"><text class="live-label">{{ question.text }}</text><view class="answer-options"><button v-for="option in question.options" :key="option.value" role="button" tabindex="0" @keydown="activateButton" :aria-pressed="workspace.followUpAnswers[question.field] === option.value" :class="{ selected: workspace.followUpAnswers[question.field] === option.value }" @click="workspace.followUpAnswers[question.field] = option.value">{{ option.text }}</button></view></view>
        <label class="live-label" for="followup-note">补充说明（选填）</label><textarea id="followup-note" v-model="workspace.followUpNote" class="live-textarea" maxlength="200" />
        <button role="button" tabindex="0" @keydown="activateButton" class="live-primary" :disabled="workspace.pending" @click="workspace.submitFollowUp">提交随访</button>
      </template>
      <text v-else class="live-notice">本次随访已处理，记录已保存。</text>
      <view v-if="workspace.followUpResponse?.advice" class="result-section"><text class="live-label">复评建议</text><text class="live-preserve">{{ workspace.followUpResponse.advice.text }}</text><text v-for="item in workspace.followUpResponse.supplement?.watch_for || []" :key="item" class="prep-item">{{ item }}</text><text class="prep-item">{{ workspace.followUpResponse.supplement?.next_question || '' }}</text></view>
      <view v-if="workspace.followUpResponse?.supplement?.prepare_idx.length" class="result-section">
        <text class="live-label">就医准备</text><text class="live-muted">本次随访关联了 {{ workspace.followUpResponse.supplement.prepare_idx.length }} 项原问诊准备事项，请在原问诊清单中查看。</text>
        <button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="workspace.openWorkspace('archive')">查看问诊记录</button>
      </view>
    </view>
    <view v-if="workspace.safety" class="live-card crisis-card" role="alert">
      <text class="live-subtitle">这里有一份想对你说的</text>
      <text v-for="(line, index) in workspace.safety.copy" :key="index" class="crisis-line">{{ line }}</text>
    </view>
    <view v-if="workspace.pendingQuestion" class="live-card clarification-card">
      <text class="live-subtitle">{{ workspace.pendingQuestion.not_understood ? '没太听懂你的描述' : '想再确认一点' }}</text>
      <text class="question-text">{{ workspace.pendingQuestion.text }}</text>
      <input id="clarify-answer" v-model="workspace.answerText" class="live-input" maxlength="500" :disabled="workspace.pending" placeholder="一句话说说就好，可以顺带提到别的感受" @keydown.enter="workspace.submitAnswer('answer')" />
      <view class="live-actions">
        <button role="button" tabindex="0" @keydown="activateButton" class="live-primary" :disabled="workspace.pending" @click="workspace.submitAnswer('answer')">提交回答</button>
        <button role="button" tabindex="0" @keydown="activateButton" class="live-secondary" :disabled="workspace.pending" @click="workspace.submitAnswer('unknown')">不知道</button>
        <button v-if="workspace.pendingQuestion.can_skip" role="button" tabindex="0" @keydown="activateButton" class="live-secondary" :disabled="workspace.pending" @click="workspace.submitAnswer('skip')">跳过此问</button>
      </view>
    </view>
    <view v-if="workspace.result" class="live-card result-card">
      <text v-if="workspace.result.degraded || workspace.detail?.gate?.fallback" class="live-notice" role="status">智能生成未完成，当前提供保守的就医建议。</text>
      <view class="live-row"><text class="live-subtitle">就医建议</text><text class="triage-badge" :class="{ emergency: workspace.result.triage === 'emergency' }">{{ workspace.result.triage_label }}</text></view>
      <text class="urgency">{{ workspace.result.urgency_note }}</text>
      <view class="result-section"><text class="live-label">建议科室</text><text>{{ workspace.result.department_primary }}<text v-if="workspace.result.department_secondary"> / {{ workspace.result.department_secondary }}</text></text></view>
      <view v-if="workspace.result.conditions.length" class="result-section"><text class="live-label">可能相关情况与依据</text><view v-for="condition in workspace.result.conditions" :key="condition.name" class="condition"><text>{{ condition.name }}</text><view v-for="(evidence, index) in condition.evidence" :key="index" class="evidence"><text class="live-preserve">{{ evidence.quote }}</text><text class="live-muted">{{ evidence.doc_title }} · {{ evidence.section }}</text></view></view></view>
      <view v-for="section in prepSections" :key="section.key" class="result-section"><text class="live-label">{{ section.title }}</text><text v-for="(item, index) in workspace.result.prep[section.key]" :key="index" class="prep-item">{{ item }}</text><text v-if="!workspace.result.prep[section.key].length" class="live-muted">暂无额外准备项</text></view>
      <text class="live-notice">{{ workspace.detail?.disclaimer || '清诉不构成诊断，最终判断以医生为准。' }}</text>
      <text v-if="workspace.result.out_of_coverage" class="live-notice" role="status">资料库暂不覆盖你描述的这类表现，以上仅按紧急程度与就诊科室作参考，不包含病因判断。</text>
      <text v-if="workspace.result.triage !== 'emergency'" class="live-muted">按建议就诊前会收到提醒；时间可在健康计划里查看和调整。</text>
      <text class="live-muted">继续补充新的情况会更新这份建议；想换个问题，点左侧“新建问诊”。</text>
    </view>
    <view v-if="workspace.notice && workspace.notice.kind === 'not_understood' && !workspace.result" class="live-card">
      <text class="live-subtitle">这次没太听懂你的描述</text>
      <text class="live-preserve">{{ workspace.notice.text }}</text>
      <view class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-primary" @click="workspace.retry">重新描述</button></view>
    </view>
    <view v-if="workspace.noConclusionText" class="live-card">
      <text class="live-subtitle">这次没有核验出有依据的结论</text>
      <text class="live-preserve">{{ workspace.noConclusionText }}</text>
    </view>
    <view v-if="workspace.error && !workspace.pending" class="live-actions"><button role="button" tabindex="0" @keydown="activateButton" class="live-secondary" @click="workspace.retry">重试／恢复问诊</button></view>
  </view>
</template>

<script setup lang="ts">
import { activateButton } from '@/components/buttonKeyboard'
import { useLiveWorkspaceStore } from '@/stores/liveWorkspace'
const workspace = useLiveWorkspaceStore()
const followUpQuestions = [
  { field: 'relieved', text: '症状是否缓解？', options: [{ value: 'yes', text: '已缓解' }, { value: 'no', text: '未缓解' }, { value: 'worse', text: '加重' }] },
  { field: 'visited', text: '是否已经就诊？', options: [{ value: 'yes', text: '是' }, { value: 'no', text: '否' }] },
  { field: 'new_symptom', text: '是否出现新症状？', options: [{ value: 'yes', text: '是' }, { value: 'no', text: '否' }] },
] as const
const prepSections = [{ key: 'bring', title: '就医携带' }, { key: 'describe', title: '向医生描述' }, { key: 'go_now', title: '需要及时就医的情况' }] as const
</script>

<style scoped>
.consultation-flow { margin-left: max(0px, calc(46 * var(--u))); }
.consultation-flow .live-card { padding: 22px; border-radius: 18px; box-shadow: 0 4px 20px #1b1b1803; }
.question-text { display: block; margin: 14px 0 18px; font-size: 17px; line-height: 1.8; }
.crisis-card { border-color: #f0e3d8; }
.crisis-line { display: block; margin-top: 12px; font-size: 15px; line-height: 2; }
.question-field { margin-top: 18px; }
.answer-options { display: flex; flex-wrap: wrap; gap: 6px; margin: 9px 0; }
.answer-options button { padding: 8px 12px; border: 1px solid #e4e4df; border-radius: 20px; background: #fff; }
.answer-options .selected { border-color: #9bb7ff; background: #f0f5ff; color: #2463eb; }
.triage-badge { padding: 4px 12px; border-radius: 18px; background: #f0f5ff; color: #2463eb; font-size: 12px; }
.triage-badge.emergency { background: #fff0ed; color: #aa3d31; }
.urgency { display: block; margin: 10px 0 20px; font-size: 14px; }
.result-section { margin: 24px 0; }
.condition { margin-top: 13px; }
.evidence { margin: 10px 0; padding: 12px 14px; border-left: 2px solid #d9e5ff; background: #fafbff; font-size: 13px; line-height: 1.9; }
.evidence .live-muted { margin-top: 7px; }
.prep-item { display: block; margin-top: 7px; font-size: 14px; }
@media (max-width: 600px) { .consultation-flow { margin-left: 0; } .consultation-flow .live-card { padding: 18px 16px; } }
</style>
