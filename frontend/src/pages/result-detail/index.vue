<template>
  <view class="detail-page">
    <view class="detail-shell">
      <header class="detail-header">
        <view class="brand">
          <text class="brand-mark">清</text>
          <view>
            <text class="brand-name">清诉</text>
            <text class="brand-subtitle">分诊详情</text>
          </view>
        </view>
        <view class="header-actions">
          <text class="preview-badge">
            {{ store.liveMode ? '实时结果，后端数据' : '交互预览，演示数据' }}
          </text>
          <button class="back-button" @click="goBack">返回问诊</button>
        </view>
      </header>

      <view class="layout">
        <main class="main-column">
          <section class="triage-banner">
            <view class="triage-copy">
              <text class="eyebrow">本轮分诊草稿</text>
                <text class="triage-title">{{ triageTitle }}</text>
                <text class="triage-subtitle">建议首诊科室：{{ primaryDepartment }}</text>
            </view>
            <view class="triage-side">
              <text class="triage-side-label">信息状态</text>
              <text class="triage-side-value">关键信息已补充</text>
              <text class="triage-side-note">仍需结合近期血压记录评估</text>
            </view>
          </section>

          <section class="content-card">
            <view class="section-heading">
              <view>
                <text class="section-eyebrow">相关情况</text>
                <text class="section-title">可能相关情况</text>
              </view>
              <text class="section-note">每条均附证据</text>
            </view>

            <article
              v-for="(item, index) in conditions"
              :key="item.title"
              class="condition-row"
            >
              <view class="condition-head">
                <text class="condition-index">0{{ index + 1 }}</text>
                <text class="condition-title">{{ item.title }}</text>
              </view>
              <text class="condition-desc">{{ item.description }}</text>
              <view class="evidence">
                <text class="evidence-label">依据</text>
                <text class="evidence-text">“{{ item.evidence }}”</text>
                <text class="evidence-source">来源：{{ item.source }}</text>
              </view>
            </article>
          </section>

          <section class="content-card">
            <view class="section-heading">
              <view>
                <text class="section-eyebrow">就医准备</text>
                <text class="section-title">就医前准备</text>
              </view>
            </view>
            <view class="prep-grid">
              <view
                v-for="(item, index) in preparation"
                :key="item"
                class="prep-item"
              >
                <text class="prep-index">{{ index + 1 }}</text>
                <text>{{ item }}</text>
              </view>
            </view>
          </section>

          <section class="content-card follow-card">
            <view>
              <text class="section-eyebrow">随访安排</text>
              <text class="follow-title">48 小时后建议复评</text>
              <text class="follow-text">重新记录血压、头晕变化和用药情况；症状加重时及时就医。</text>
            </view>
            <button class="follow-button" @click="openWorkspace('reminders')">查看随访</button>
          </section>
        </main>

        <aside class="side-column">
          <section class="side-card patient-card">
            <view class="patient-head">
              <view class="patient-avatar">王</view>
              <view>
                <text class="patient-name">{{ patientName }}</text>
                <text class="patient-meta">{{ patientMeta }}</text>
              </view>
            </view>
            <view class="metric-grid">
              <view>
                <text class="metric-label">家庭血压</text>
                <text class="metric-value warning">{{ latestPressure }}</text>
                <text class="metric-unit">mmHg</text>
              </view>
              <view>
                <text class="metric-label">心率</text>
                <text class="metric-value">{{ latestPulse }}</text>
                <text class="metric-unit">bpm</text>
              </view>
            </view>
          </section>

          <section class="side-card">
            <text class="side-title">风险提示</text>
            <view class="risk-item">
              <text class="risk-mark">!</text>
              <view>
                <text class="risk-name">不要自行停药</text>
                <text class="risk-desc">长期处方药应先咨询医生再调整。</text>
              </view>
            </view>
            <view class="risk-item">
              <text class="risk-mark neutral">i</text>
              <view>
                <text class="risk-name">留意危险症状</text>
                <text class="risk-desc">胸痛、呼吸困难、意识异常需及时就医。</text>
              </view>
            </view>
          </section>

          <section class="side-card disclaimer-card">
            <text class="side-title">安全边界</text>
            <text class="disclaimer-text">
              本结果不构成疾病诊断，不提供处方或剂量建议，不替代医生。
            </text>
          </section>

          <button class="save-button" @click="saveResult">保存到健康档案</button>
          <text class="save-note">
            {{ store.liveMode ? '保存后将写入健康档案并创建提醒' : '预览模式不会写入真实档案' }}
          </text>
        </aside>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'

const store = useWorkspaceStore()

const fallbackConditions = [
  {
    title: '血压控制不佳相关不适',
    description: '家庭血压高于平时水平，需要医生结合连续记录进行判断。',
    evidence: '出现不适并伴随血压明显升高时，应记录复测结果并咨询医生。',
    source: '演示用公开健康资料',
  },
  {
    title: '需要核实的药物相关因素',
    description: '不能仅凭一次头晕自行停药，应由医生评估原因后调整。',
    evidence: '长期处方药出现不适时，应先联系医生，不建议自行停药或改量。',
    source: '演示用公开健康资料',
  },
  {
    title: '睡眠不足等暂时性因素',
    description: '睡眠不足可能相关，但不能据此排除血压异常。',
    evidence: '单一主观归因不能替代血压和伴随症状的进一步核实。',
    source: '演示用公开健康资料',
  },
]

const fallbackPreparation = [
  '带上最近一周的家庭血压记录',
  '列出目前正在使用的药物和服用时间',
  '说明头晕持续时间、诱因和伴随症状',
  '出现胸痛、呼吸困难或意识异常时及时就医',
]

const patientName = computed(() => store.profile?.name || '王阿姨')
const patientMeta = computed(() => {
  const age = store.profile?.age_years
  const condition = store.profile?.conditions?.[0]
  return [age ? `${age}岁` : '', condition ? `${condition}随访` : '演示数据']
    .filter(Boolean)
    .join('，')
})
const latestPressure = computed(() => {
  const bp = store.archiveOverview?.vitals.latest_bp
  return bp ? `${bp.systolic}/${bp.diastolic}` : '162/98'
})
const latestPulse = computed(() => store.archiveOverview?.vitals.latest_bp?.pulse ?? 88)

const triageTitle = computed(() => {
  const item = store.result
  if (!item) return '门诊，数日内'
  return `${item.triage_label}，${item.urgency_note}`
})
const primaryDepartment = computed(() => store.result?.department_primary || '心血管内科')
const conditions = computed(() => {
  const live = store.result?.conditions
  if (!live?.length) return fallbackConditions
  return live.map((item) => ({
    title: item.name,
    description: '该情况来自本轮核验后的分诊草稿，请结合医生判断。',
    evidence: item.evidence[0]?.quote ?? '暂无引用',
    source: item.evidence[0]?.doc_title ?? '后端核验证据',
  }))
})
const preparation = computed(() => {
  const prep = store.result?.prep
  if (!prep) return fallbackPreparation
  return [...prep.bring, ...prep.describe, ...prep.go_now]
})

function goBack() {
  uni.navigateBack()
}

function openWorkspace(tab: 'archive' | 'reminders') {
  store.switchTab(tab)
  uni.navigateBack()
}

async function saveResult() {
  try {
    const response = await store.saveCurrentEpisode()
    if (response.demo) {
      uni.showToast({ title: '预览模式：未调用保存接口', icon: 'none' })
      return
    }
    uni.showToast({ title: '已保存到健康档案', icon: 'success' })
    store.switchTab('archive')
    setTimeout(() => uni.navigateBack(), 500)
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : '保存失败',
      icon: 'none',
    })
  }
}
</script>

<style scoped>
/* Mint theme overrides for the result detail page. */
.detail-page {
  background: var(--palette-eff9f5);
  color: var(--palette-23473c);
}

.detail-header {
  border-color: var(--palette-e0eee8);
  background: var(--palette-fbfefc);
}

.brand-mark {
  background: var(--palette-4ba58d);
  color: var(--palette-ffffff);
}

.preview-badge {
  background: var(--palette-e2f5ed);
  color: var(--palette-397b67);
}

.back-button {
  border-color: var(--palette-cde6dc);
  background: var(--palette-ffffff);
  color: var(--palette-3d7462);
}

.triage-banner {
  background:
    radial-gradient(circle at 88% 18%, var(--wash-light-48), transparent 32%),
    linear-gradient(135deg, var(--palette-d8f3e9), var(--palette-bce8da));
  color: var(--palette-214b3f);
}

.eyebrow {
  color: var(--palette-347d68);
}

.triage-subtitle {
  color: var(--palette-557a6d);
}

.triage-side {
  border-color: var(--border-accent-15);
  background: var(--wash-light-50);
}

.triage-side-label {
  color: var(--palette-538678);
}

.triage-side-value {
  color: var(--palette-285b4c);
}

.triage-side-note {
  color: var(--palette-67877b);
}

.content-card,
.side-card {
  border-color: var(--palette-e0eee8);
  background: var(--palette-ffffff);
}

.condition-card {
  border-color: var(--palette-e4f0eb);
  background: var(--palette-fbfefc);
}

.evidence {
  background: var(--palette-eef9f5);
}

.prep-item {
  background: var(--palette-f3faf7);
}

.prep-index,
.patient-avatar {
  background: var(--palette-dcefe7);
  color: var(--palette-317762);
}

.save-button {
  background: var(--palette-4ba58d);
  color: var(--palette-ffffff);
}

.follow-card {
  background: var(--palette-fffdf7);
  border-color: var(--palette-eee7d2);
}

/* Hallmark Dose redesign: the result reads as an evidence sheet. */
.detail-page {
  min-height: 100vh;
  background: var(--color-paper);
  color: var(--color-ink);
}

.detail-header,
.brand,
.header-actions,
.patient-head,
.section-heading,
.risk-item,
.follow-card {
  display: flex;
}

.brand-name,
.brand-subtitle,
.eyebrow,
.triage-title,
.triage-subtitle,
.triage-side-label,
.triage-side-value,
.triage-side-note,
.section-eyebrow,
.section-title,
.condition-title,
.condition-desc,
.evidence-label,
.evidence-text,
.evidence-source,
.follow-title,
.follow-text,
.patient-name,
.patient-meta,
.metric-label,
.metric-value,
.metric-unit,
.side-title,
.risk-name,
.risk-desc,
.disclaimer-text,
.save-note {
  display: block;
}

.detail-shell {
  width: min(1480px, 100%);
}

.detail-header {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky-nav);
  height: 72px;
  padding: 0 var(--space-xl);
  border-color: var(--color-rule);
  background: var(--palette-fffdf6);
  align-items: center;
  justify-content: space-between;
}

.brand {
  align-items: center;
  gap: var(--space-sm);
}

.brand-mark {
  display: flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
}

.brand-name {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand-subtitle {
  margin-top: 0;
  color: var(--color-muted);
  font-size: 9px;
}

.header-actions {
  align-items: center;
  gap: var(--space-md);
}

.preview-badge {
  padding: var(--space-2xs) var(--space-xs);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 5px;
  background: var(--color-paper-2);
  color: var(--color-muted);
  font-family: var(--font-outlier);
  font-size: 9px;
}

.back-button {
  padding: 0 var(--space-md);
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 7px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 11px;
  line-height: 36px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--space-xl);
  padding: var(--space-xl);
}

.main-column {
  min-width: 0;
}

.triage-banner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.36fr);
  gap: var(--space-xl);
  padding: var(--space-xl);
  overflow: hidden;
  border: var(--rule-hair) solid var(--color-accent);
  border-radius: 12px;
  background:
    radial-gradient(circle at 88% 18%, var(--wash-accent-18), transparent 32%),
    var(--color-paper-2);
  color: var(--color-ink);
}

.eyebrow {
  color: var(--color-accent-deep);
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 650;
}

.triage-title {
  max-width: 18ch;
  margin-top: var(--space-sm);
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: clamp(34px, 4vw, 52px);
  font-weight: 700;
  line-height: 1.04;
  letter-spacing: -0.045em;
}

.triage-subtitle {
  margin-top: var(--space-sm);
  color: var(--color-ink-2);
  font-size: 13px;
}

.triage-side {
  min-width: 0;
  padding: var(--space-md);
  align-self: stretch;
  border: var(--rule-hair) solid var(--border-accent-15);
  border-radius: 8px;
  background: var(--palette-fffdf6);
}

.triage-side-label {
  color: var(--color-muted);
  font-size: 10px;
}

.triage-side-value {
  margin-top: var(--space-xs);
  color: var(--color-accent-deep);
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
}

.triage-side-note {
  margin-top: var(--space-xs);
  color: var(--color-muted);
  font-size: 10px;
  line-height: 1.6;
}

.content-card {
  margin-top: 0;
  padding: var(--space-xl) 0;
  border: 0;
  border-bottom: var(--rule-hair) solid var(--color-rule);
  border-radius: 0;
  background: transparent;
}

.section-heading {
  margin-bottom: var(--space-lg);
  align-items: flex-start;
  justify-content: space-between;
}

.section-eyebrow {
  color: var(--color-muted);
  font-size: 10px;
  font-weight: 550;
}

.section-title {
  margin-top: var(--space-2xs);
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.section-note {
  color: var(--color-muted);
  font-size: 10px;
}

.condition-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: var(--space-md);
  padding: var(--space-lg) 0;
  border-top: var(--rule-hair) solid var(--color-rule);
}

.condition-head {
  display: contents;
}

.condition-index {
  grid-column: 1;
  grid-row: 1 / span 3;
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
  font-size: 11px;
}

.condition-title {
  grid-column: 2;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.condition-desc {
  grid-column: 2;
  margin-top: var(--space-xs);
  color: var(--color-ink-2);
  font-size: 13px;
}

.evidence {
  grid-column: 2;
  margin-top: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 6px;
  background: var(--color-paper-2);
}

.evidence-label {
  color: var(--color-accent-deep);
  font-size: 9px;
  font-weight: 650;
}

.evidence-text {
  margin-top: var(--space-xs);
  color: var(--color-ink-2);
  font-size: 11px;
}

.evidence-source {
  margin-top: var(--space-xs);
  color: var(--color-muted);
  font-family: var(--font-outlier);
  font-size: 9px;
}

.prep-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  border-top: var(--rule-hair) solid var(--color-rule);
}

.prep-item {
  display: flex;
  min-height: 72px;
  padding: var(--space-md) var(--space-md) var(--space-md) 0;
  align-items: flex-start;
  gap: var(--space-sm);
  border-bottom: var(--rule-hair) solid var(--color-rule);
  border-radius: 0;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 12px;
}

.prep-item:nth-child(odd) {
  padding-right: var(--space-lg);
  border-right: var(--rule-hair) solid var(--color-rule);
}

.prep-item:nth-child(even) {
  padding-left: var(--space-lg);
}

.prep-index {
  width: 20px;
  height: 20px;
  flex-basis: 20px;
  border-radius: 4px;
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
}

.follow-card {
  margin-top: var(--space-md);
  padding: var(--space-lg);
  align-items: center;
  justify-content: space-between;
  border: var(--rule-hair) solid var(--palette-eee7d2);
  border-radius: 9px;
  background: var(--palette-fffdf7);
}

.follow-title {
  margin-top: var(--space-xs);
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
}

.follow-text {
  margin-top: var(--space-xs);
  color: var(--color-ink-2);
  font-size: 11px;
}

.follow-button {
  border-radius: 7px;
  border: var(--rule-hair) solid var(--color-accent);
  background: transparent;
  color: var(--color-accent-deep);
  font-size: 10px;
}

.side-column {
  position: sticky;
  top: 96px;
  height: fit-content;
}

.side-card {
  margin-top: 0;
  padding: var(--space-lg);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 10px;
  background: var(--palette-fffdf6);
}

.side-card + .side-card {
  margin-top: var(--space-sm);
}

.patient-head {
  align-items: center;
  gap: var(--space-sm);
}

.patient-avatar {
  display: flex;
  width: 38px;
  height: 38px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
}

.patient-name {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
}

.patient-meta {
  margin-top: 1px;
  color: var(--color-muted);
  font-size: 10px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-md);
  margin-top: var(--space-md);
  padding-top: var(--space-md);
  border-top: var(--rule-hair) solid var(--color-rule);
}

.metric-label {
  color: var(--color-muted);
  font-size: 9px;
}

.metric-value {
  margin-top: var(--space-xs);
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
  font-size: 20px;
  font-weight: 500;
}

.metric-value.warning {
  color: var(--color-error);
}

.metric-unit {
  color: var(--color-muted);
  font-size: 8px;
}

.side-title {
  color: var(--color-accent-deep);
  font-size: 10px;
  font-weight: 650;
}

.risk-item {
  align-items: flex-start;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.risk-mark {
  display: flex;
  width: 22px;
  height: 22px;
  flex-basis: 22px;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
  background: var(--palette-fff0ea);
  color: var(--color-error);
  font-family: var(--font-outlier);
}

.risk-mark.neutral {
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
}

.risk-name {
  color: var(--color-ink);
  font-size: 11px;
}

.risk-desc,
.disclaimer-text {
  margin-top: var(--space-2xs);
  color: var(--color-muted);
  font-size: 10px;
  line-height: 1.6;
}

.disclaimer-card {
  background: var(--color-paper-2);
}

.save-button {
  width: 100%;
  margin-top: var(--space-sm);
  border-radius: 8px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
  font-size: 11px;
}

.save-note {
  margin-top: var(--space-xs);
  color: var(--color-muted);
  font-size: 9px;
  text-align: center;
}

.back-button:focus-visible,
.follow-button:focus-visible,
.save-button:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.back-button:active,
.follow-button:active,
.save-button:active {
  transform: translateY(1px);
}

.back-button[disabled],
.follow-button[disabled],
.save-button[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 1080px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-lg);
  }

  .side-column {
    position: static;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-sm);
  }

  .side-card + .side-card {
    margin-top: 0;
  }
}

@media (max-width: 760px) {
  .detail-header {
    height: 64px;
    padding: 0 16px;
  }

  .brand-subtitle,
  .preview-badge {
    display: none;
  }

  .layout {
    padding: 16px;
  }

  .triage-banner {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-md);
    padding: var(--space-lg);
  }

  .triage-title {
    font-size: 34px;
  }

  .content-card {
    padding: var(--space-lg) 0;
  }

  .prep-grid,
  .side-column {
    grid-template-columns: minmax(0, 1fr);
  }

  .prep-item:nth-child(odd),
  .prep-item:nth-child(even) {
    padding-right: 0;
    padding-left: 0;
    border-right: 0;
  }

  .follow-card {
    align-items: flex-start;
    gap: var(--space-md);
    flex-direction: column;
  }
}
</style>
