<template>
  <view class="correction-panel" aria-label="纠偏与评估">
    <view class="panel-heading">
      <view class="heading-icon"><QIcon name="shield" /></view>
      <view class="heading-copy">
        <view class="heading-title-row">
          <text class="panel-title">纠偏与评估</text>
          <text class="demo-label">演示</text>
        </view>
        <text class="panel-subtitle">让症状事实与主观推测分开。</text>
      </view>
    </view>

    <view v-if="pending" class="panel-state" role="status" aria-live="polite">
      <view class="state-icon is-pending"><QIcon name="spark" /></view>
      <text class="state-title">正在整理这次表达</text>
      <text class="state-description">演示结果会在消息整理完成后展示。</text>
      <view class="pending-lines" aria-hidden="true">
        <view class="pending-line" />
        <view class="pending-line short-line" />
        <view class="pending-line" />
      </view>
    </view>

    <view v-else-if="!report" class="panel-state">
      <view class="state-icon"><QIcon name="file" /></view>
      <text class="state-title">从第一段描述开始</text>
      <text class="state-description">发送消息后，在这里查看风险表达、纠偏说明和前后对比。</text>
    </view>

    <view v-else class="report-content">
      <view class="report-summary">
        <QIcon name="check" />
        <view>
          <text class="summary-title">头晕与用药 · 固定样例</text>
          <text class="summary-detail">{{ report.risks.length ? `样例展示 ${report.risks.length} 项表达风险` : '本例未标记表达风险' }}</text>
        </view>
      </view>

      <view v-if="report.risks.length" class="risk-section">
        <text class="section-title">需要留意的表达</text>
        <view v-for="(risk, index) in report.risks" :key="index" class="risk-item">
          <view class="risk-dot" />
          <text>{{ risk }}</text>
        </view>
      </view>

      <view class="comparison-section">
        <text class="section-title">纠偏前后对比</text>
        <view class="comparison-card before-card">
          <view class="comparison-label"><view class="comparison-dot" /><text>纠偏前 · 样例回答</text></view>
          <text class="comparison-text">{{ report.original }}</text>
        </view>
        <view class="comparison-card after-card">
          <view class="comparison-label"><QIcon name="check" /><text>纠偏后 · 样例回答</text></view>
          <text class="comparison-text">{{ report.corrected }}</text>
        </view>
      </view>

      <view v-if="report.metrics.length" class="metrics-section">
        <view class="metrics-heading">
          <text class="section-title">效果对比</text>
          <text class="metrics-scope">演示指标 · 固定样例</text>
        </view>
        <view class="metric-legend"><text class="before-legend">纠偏前</text><text class="after-legend">纠偏后</text></view>
        <view v-for="metric in report.metrics" :key="metric.label" class="metric-item">
          <text class="metric-title">{{ metric.label }}</text>
          <view class="metric-bar-row" :aria-label="`纠偏前 ${percentage(metric.before)}%`">
            <view class="metric-track"><view class="metric-fill before-fill" :style="{ width: `${percentage(metric.before)}%` }" /></view>
            <text class="metric-value">{{ percentage(metric.before) }}%</text>
          </view>
          <view class="metric-bar-row" :aria-label="`纠偏后 ${percentage(metric.after)}%`">
            <view class="metric-track"><view class="metric-fill after-fill" :style="{ width: `${percentage(metric.after)}%` }" /></view>
            <text class="metric-value after-value">{{ percentage(metric.after) }}%</text>
          </view>
        </view>
      </view>
    </view>

    <view class="panel-note">
      <QIcon name="info" />
      <text>当前内容为前端演示样例。真实纠偏结果与评估指标将在后端接入后展示。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import QIcon from '@/components/QIcon.vue'
import type { CorrectionReport } from '@/types/consultation'

defineProps<{
  report: CorrectionReport | null
  pending: boolean
}>()

function percentage(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)))
}
</script>

<style scoped>
.correction-panel {
  color: var(--ink, #293653);
  background: var(--surface, #ffffff);
  border: 1px solid var(--line, #dce5f2);
  border-radius: calc(40 * var(--u, 1px));
  box-shadow: 0 12px 42px #2939580b;
  overflow: hidden;
}
.panel-heading { display: flex; align-items: center; gap: 13px; padding: max(20px, calc(30 * var(--u, 1px))); border-bottom: 1px solid var(--line, #dce5f2); }
.heading-icon { display: flex; align-items: center; justify-content: center; width: max(28px, calc(40 * var(--u, 1px))); height: max(28px, calc(40 * var(--u, 1px))); flex-shrink: 0; background: var(--surface-tint, #e1edff); border-radius: 10px; }
.heading-icon .q-icon { width: max(18px, calc(23 * var(--u, 1px))); height: max(18px, calc(23 * var(--u, 1px))); }
.heading-copy { flex: 1; min-width: 0; }
.heading-title-row { display: flex; align-items: center; gap: 10px; }
.panel-title { font-size: clamp(16px, calc(22 * var(--u, 1px)), 28px); font-weight: 600; letter-spacing: -.3px; }
.demo-label { padding: 3px 7px; border: 1px solid var(--line, #dce5f2); border-radius: 5px; color: var(--text-strong, #30466c); font-size: 12px; line-height: 16px; }
.panel-subtitle { display: block; margin-top: 5px; color: var(--muted, #657590); font-size: clamp(12px, calc(16 * var(--u, 1px)), 20px); line-height: 1.6; }
.report-content { padding: max(20px, calc(30 * var(--u, 1px))) max(20px, calc(30 * var(--u, 1px))) 0; }
.report-summary { display: flex; gap: 10px; padding: max(10px, calc(16 * var(--u, 1px))); margin-bottom: max(18px, calc(25 * var(--u, 1px))); background: var(--surface-soft, #edf4ff); border: 1px solid var(--line, #dce5f2); border-radius: 10px; }
.report-summary .q-icon { width: 20px; height: 20px; margin-top: 1px; }
.summary-title { display: block; color: var(--text-strong, #30466c); font-size: clamp(13px, calc(18 * var(--u, 1px)), 22px); font-weight: 600; line-height: 1.5; }
.summary-detail { display: block; margin-top: 3px; color: var(--text-strong, #30466c); font-size: clamp(12px, calc(15 * var(--u, 1px)), 18px); line-height: 1.5; }
.section-title { display: block; font-size: clamp(14px, calc(18 * var(--u, 1px)), 22px); line-height: 1.5; font-weight: 600; }
.risk-section { margin-bottom: 26px; }
.risk-item { display: flex; align-items: flex-start; gap: 9px; margin-top: max(8px, calc(11 * var(--u, 1px))); color: var(--muted, #657590); font-size: clamp(13px, calc(18 * var(--u, 1px)), 22px); line-height: 1.6; }
.risk-dot { width: 5px; height: 5px; margin-top: 9px; border-radius: 50%; background: #60799f; flex-shrink: 0; }
.comparison-card { margin-top: max(10px, calc(14 * var(--u, 1px))); border-radius: 11px; padding: max(12px, calc(20 * var(--u, 1px))); }
.before-card { background: #f3f6fb; border: 1px solid var(--line, #dce5f2); }
.after-card { background: var(--surface, #ffffff); border: 1px solid var(--line, #dce5f2); }
.comparison-label { display: flex; align-items: center; gap: 7px; margin-bottom: 10px; color: var(--text-strong, #30466c); font-size: clamp(12px, calc(15 * var(--u, 1px)), 18px); font-weight: 600; line-height: 1.5; }
.comparison-dot { height: 5px; width: 5px; border-radius: 50%; background: #8297b7; margin-right: 2px; }
.after-card .comparison-label { color: var(--text-strong, #30466c); }
.comparison-label .q-icon { width: 16px; height: 16px; }
.comparison-text { display: block; color: var(--text-strong, #30466c); font-size: clamp(15px, calc(20 * var(--u, 1px)), 24px); line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.after-card .comparison-text { color: var(--ink, #293653); }
.metrics-section { margin-top: 28px; padding-top: 23px; border-top: 1px solid var(--line, #dce5f2); }
.metrics-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.metrics-scope { color: var(--muted, #657590); font-size: 12px; line-height: 20px; }
.metric-legend { display: flex; gap: 17px; margin-top: 12px; font-size: 12px; line-height: 18px; }
.before-legend { color: var(--muted, #657590); }
.after-legend { color: var(--accent-deep, #293958); }
.metric-item { margin-top: 19px; }
.metric-title { display: block; margin-bottom: 7px; color: var(--text-strong, #30466c); font-size: 14px; line-height: 22px; }
.metric-bar-row { display: flex; align-items: center; gap: 12px; height: 22px; }
.metric-track { flex: 1; height: 5px; overflow: hidden; background: var(--surface-soft, #edf4ff); border-radius: 4px; }
.metric-fill { height: 100%; border-radius: 4px; }
.before-fill { background: var(--chart-before, #b0bed5); }
.after-fill { background: var(--chart-after, #497fd4); }
.metric-value { width: 37px; flex-shrink: 0; color: var(--muted, #657590); text-align: right; font-size: 13px; font-variant-numeric: tabular-nums; }
.after-value { color: var(--accent-deep, #293958); }
.panel-note { display: flex; align-items: flex-start; gap: 9px; margin: 26px; padding-top: 19px; border-top: 1px solid var(--line, #dce5f2); color: var(--muted, #657590); font-size: 13px; line-height: 1.7; }
.panel-note .q-icon { width: 17px; height: 17px; margin-top: 3px; opacity: .65; }
.panel-state { display: flex; flex-direction: column; align-items: center; min-height: 340px; box-sizing: border-box; padding: 62px 32px 38px; text-align: center; }
.state-icon { display: flex; align-items: center; justify-content: center; width: 56px; height: 56px; border-radius: 16px; background: var(--surface-soft, #edf4ff); }
.state-icon .q-icon { width: 25px; height: 25px; opacity: .75; }
.state-title { margin-top: 20px; font-size: 18px; font-weight: 600; line-height: 28px; }
.state-description { max-width: 280px; margin-top: 9px; color: var(--muted, #657590); font-size: 15px; line-height: 1.8; }
.pending-lines { display: flex; flex-direction: column; align-items: center; gap: 10px; width: 100%; margin-top: 30px; }
.pending-line { width: 83%; height: 7px; border-radius: 5px; background: var(--surface-tint, #e1edff); animation: pending-pulse 1.4s ease-in-out infinite; }
.short-line { width: 59%; animation-delay: .2s; }
.is-pending { animation: pending-pulse 1.4s ease-in-out infinite; }
@keyframes pending-pulse { 50% { opacity: .45; } }
@media (max-width: 600px) {
  .correction-panel { border-radius: 16px; }
  .panel-heading { padding: 21px 20px; }
  .report-content { padding: 21px 20px 0; }
  .panel-note { margin: 23px 20px; }
  .panel-state { min-height: 300px; padding: 42px 24px 28px; }
  .comparison-card { padding: 15px; }
}
@media (prefers-reduced-motion: reduce) {
  .pending-line, .is-pending { animation: none; }
}
</style>
