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
            {{ store.liveMode ? '实时结果 · 后端数据' : '交互预览 · Mock 数据' }}
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
                <text class="section-eyebrow">POSSIBILITIES</text>
                <text class="section-title">可能相关情况</text>
              </view>
              <text class="section-note">每条均附证据</text>
            </view>

            <article
              v-for="(item, index) in conditions"
              :key="item.title"
              class="condition-card"
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
                <text class="section-eyebrow">BEFORE VISIT</text>
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
              <text class="section-eyebrow">FOLLOW-UP</text>
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
    .join(' · ')
})
const latestPressure = computed(() => {
  const bp = store.archiveOverview?.vitals.latest_bp
  return bp ? `${bp.systolic}/${bp.diastolic}` : '162/98'
})
const latestPulse = computed(() => store.archiveOverview?.vitals.latest_bp?.pulse ?? 88)

const triageTitle = computed(() => {
  const item = store.result
  if (!item) return '门诊 · 数日内'
  return `${item.triage_label} · ${item.urgency_note}`
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
.detail-page {
  min-height: 100vh;
  background: #f2f5f2;
  color: #1e3d32;
}

.detail-shell {
  width: min(1360px, 100%);
  margin: 0 auto;
}

.detail-header {
  display: flex;
  height: 76px;
  padding: 0 34px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e1e9e5;
  background: #ffffff;
  box-sizing: border-box;
}

.brand,
.header-actions,
.patient-head,
.condition-head,
.section-heading,
.risk-item,
.follow-card {
  display: flex;
}

.brand {
  align-items: center;
  gap: 10px;
}

.brand-mark {
  display: flex;
  width: 38px;
  height: 38px;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: #174f40;
  color: #ffffff;
  font-size: 20px;
  font-weight: 800;
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

.brand-name {
  font-size: 17px;
  font-weight: 800;
}

.brand-subtitle {
  margin-top: 2px;
  color: #879790;
  font-size: 10px;
}

.header-actions {
  align-items: center;
  gap: 10px;
}

.preview-badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: #eef5f1;
  color: #527467;
  font-size: 10px;
}

.back-button {
  width: auto;
  margin: 0;
  padding: 0 14px;
  border: 1px solid #d3e1da;
  border-radius: 10px;
  background: #ffffff;
  color: #47695c;
  font-size: 11px;
  line-height: 36px;
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 20px;
  padding: 24px 28px 48px;
}

.main-column {
  min-width: 0;
}

.triage-banner {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 24px;
  padding: 26px 28px;
  border-radius: 20px;
  background:
    radial-gradient(circle at 88% 20%, rgba(115, 202, 171, 0.22), transparent 30%),
    #123f35;
  color: #ffffff;
}

.eyebrow {
  color: #80c8b0;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1.5px;
}

.triage-title {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 800;
}

.triage-subtitle {
  margin-top: 7px;
  color: #c1d9d0;
  font-size: 12px;
}

.triage-side {
  min-width: 180px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 13px;
  background: rgba(255, 255, 255, 0.055);
}

.triage-side-label {
  color: #89b5a6;
  font-size: 9px;
}

.triage-side-value {
  margin-top: 7px;
  font-size: 13px;
  font-weight: 700;
}

.triage-side-note {
  margin-top: 5px;
  color: #a9c6bb;
  font-size: 9px;
}

.content-card,
.side-card {
  margin-top: 16px;
  padding: 22px;
  border: 1px solid #e2e9e5;
  border-radius: 17px;
  background: #ffffff;
}

.section-heading {
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 18px;
}

.section-eyebrow {
  color: #79988c;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 1.4px;
}

.section-title {
  margin-top: 5px;
  font-size: 18px;
  font-weight: 800;
}

.section-note {
  color: #8c9b95;
  font-size: 9px;
}

.condition-card {
  margin-top: 12px;
  padding: 16px;
  border: 1px solid #e5ece8;
  border-radius: 13px;
  background: #fbfcfb;
}

.condition-head {
  align-items: center;
  gap: 9px;
}

.condition-index {
  color: #75a695;
  font-size: 9px;
  font-weight: 800;
}

.condition-title {
  font-size: 13px;
  font-weight: 800;
}

.condition-desc {
  margin-top: 8px;
  color: #61756d;
  font-size: 11px;
  line-height: 1.65;
}

.evidence {
  margin-top: 11px;
  padding: 12px 13px;
  border-radius: 10px;
  background: #eef5f1;
}

.evidence-label {
  color: #3f7561;
  font-size: 9px;
  font-weight: 800;
}

.evidence-text {
  margin-top: 5px;
  color: #5c7168;
  font-size: 10px;
  line-height: 1.6;
}

.evidence-source {
  margin-top: 4px;
  color: #8ea098;
  font-size: 8px;
}

.prep-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.prep-item {
  display: flex;
  min-height: 54px;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 11px;
  background: #f5f8f6;
  color: #53685f;
  font-size: 10px;
  line-height: 1.55;
}

.prep-index {
  display: flex;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #dcece5;
  color: #2c6e58;
  font-size: 9px;
  font-weight: 800;
}

.follow-card {
  align-items: center;
  justify-content: space-between;
  background: #fffdf6;
  border-color: #eee5c8;
}

.follow-title {
  margin-top: 5px;
  font-size: 14px;
  font-weight: 800;
}

.follow-text {
  margin-top: 5px;
  color: #7d765d;
  font-size: 10px;
  line-height: 1.55;
}

.follow-button {
  width: auto;
  margin: 0;
  padding: 0 16px;
  border-radius: 10px;
  background: #f1e4b8;
  color: #705d20;
  font-size: 10px;
  line-height: 38px;
}

.side-column {
  min-width: 0;
}

.patient-head {
  align-items: center;
  gap: 10px;
}

.patient-avatar {
  display: flex;
  width: 42px;
  height: 42px;
  align-items: center;
  justify-content: center;
  border-radius: 13px;
  background: #dfeee7;
  color: #24634f;
  font-size: 15px;
  font-weight: 800;
}

.patient-name {
  font-size: 13px;
  font-weight: 800;
}

.patient-meta {
  margin-top: 3px;
  color: #8b9a94;
  font-size: 9px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #edf1ef;
}

.metric-label {
  color: #8b9a94;
  font-size: 9px;
}

.metric-value {
  margin-top: 5px;
  color: #1c5f4b;
  font-size: 20px;
  font-weight: 800;
}

.metric-value.warning {
  color: #b87457;
}

.metric-unit {
  color: #9aa6a1;
  font-size: 8px;
}

.side-title {
  color: #6c8279;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1px;
}

.risk-item {
  align-items: flex-start;
  gap: 9px;
  margin-top: 14px;
}

.risk-mark {
  display: flex;
  width: 25px;
  height: 25px;
  flex: 0 0 25px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #fff0ea;
  color: #b15f48;
  font-size: 11px;
  font-weight: 800;
}

.risk-mark.neutral {
  background: #edf4f1;
  color: #39705d;
}

.risk-name {
  font-size: 10px;
  font-weight: 700;
}

.risk-desc {
  margin-top: 3px;
  color: #8a9993;
  font-size: 9px;
  line-height: 1.55;
}

.disclaimer-card {
  background: #f8faf8;
}

.disclaimer-text {
  margin-top: 8px;
  color: #71847c;
  font-size: 10px;
  line-height: 1.65;
}

.save-button {
  width: 100%;
  margin-top: 16px;
  border-radius: 12px;
  background: #175c49;
  color: #ffffff;
  font-size: 12px;
}

.save-note {
  margin-top: 8px;
  color: #96a39e;
  font-size: 8px;
  text-align: center;
}

@media (max-width: 900px) {
  .detail-header {
    height: auto;
    padding: 16px 18px;
  }

  .preview-badge {
    display: none;
  }

  .layout {
    display: block;
    padding: 16px;
  }

  .triage-banner {
    grid-template-columns: 1fr;
    padding: 22px;
  }

  .triage-title {
    font-size: 25px;
  }

  .side-column {
    margin-top: 16px;
  }

  .prep-grid {
    grid-template-columns: 1fr;
  }

  .follow-card {
    align-items: flex-start;
    gap: 16px;
    flex-direction: column;
  }
}
</style>

<style scoped>
/* Mint theme overrides for the result detail page. */
.detail-page {
  background: #eff9f5;
  color: #23473c;
}

.detail-header {
  border-color: #e0eee8;
  background: #fbfefc;
}

.brand-mark {
  background: #4ba58d;
  color: #ffffff;
}

.preview-badge {
  background: #e2f5ed;
  color: #397b67;
}

.back-button {
  border-color: #cde6dc;
  background: #ffffff;
  color: #3d7462;
}

.triage-banner {
  background:
    radial-gradient(circle at 88% 18%, rgba(255, 255, 255, 0.48), transparent 32%),
    linear-gradient(135deg, #d8f3e9, #bce8da);
  color: #214b3f;
}

.eyebrow {
  color: #347d68;
}

.triage-subtitle {
  color: #557a6d;
}

.triage-side {
  border-color: rgba(57, 121, 102, 0.15);
  background: rgba(255, 255, 255, 0.5);
}

.triage-side-label {
  color: #538678;
}

.triage-side-value {
  color: #285b4c;
}

.triage-side-note {
  color: #67877b;
}

.content-card,
.side-card {
  border-color: #e0eee8;
  background: #ffffff;
}

.condition-card {
  border-color: #e4f0eb;
  background: #fbfefc;
}

.evidence {
  background: #eef9f5;
}

.prep-item {
  background: #f3faf7;
}

.prep-index,
.patient-avatar {
  background: #dcefe7;
  color: #317762;
}

.save-button {
  background: #4ba58d;
  color: #ffffff;
}

.follow-card {
  background: #fffdf7;
  border-color: #eee7d2;
}
</style>
