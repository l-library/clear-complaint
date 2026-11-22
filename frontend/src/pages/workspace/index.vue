<template>
  <view class="workspace">
    <view class="app-layout">
      <aside class="sidebar">
        <view class="brand">
          <text class="brand-mark">清</text>
          <view>
            <text class="brand-name">清诉</text>
            <text class="brand-en">ClearComplaint</text>
          </view>
        </view>

        <button class="new-chat" @click="startNewChat">
          <text>＋</text>
          <text>新的健康咨询</text>
        </button>

        <view class="nav-list">
          <button
            class="nav-item"
            :class="{ active: store.activeTab === 'consult' }"
            @click="store.switchTab('consult')"
          >
            <text class="nav-icon">诉</text>
            <text>问诊对话</text>
          </button>
          <button
            class="nav-item"
            :class="{ active: store.activeTab === 'archive' }"
            @click="store.switchTab('archive')"
          >
            <text class="nav-icon">档</text>
            <text>健康档案</text>
          </button>
          <button
            class="nav-item"
            :class="{ active: store.activeTab === 'reminders' }"
            @click="store.switchTab('reminders')"
          >
            <text class="nav-icon">醒</text>
            <text>提醒随访</text>
          </button>
        </view>

        <view class="recent">
          <text class="recent-label">最近咨询</text>
          <view class="recent-item active">
            <text class="recent-title">头晕与降压药</text>
            <text class="recent-meta">刚刚 · 信息收集中</text>
          </view>
          <view class="recent-item">
            <text class="recent-title">咳嗽与鼻塞</text>
            <text class="recent-meta">11月9日 · 门诊</text>
          </view>
          <view class="recent-item">
            <text class="recent-title">睡眠不佳</text>
            <text class="recent-meta">10月28日 · 自我观察</text>
          </view>
        </view>

        <view class="account">
          <view class="account-avatar">王</view>
          <view class="account-copy">
            <text class="account-name">{{ patientName }}</text>
            <text class="account-type">{{ store.liveMode ? '已登录账户' : '演示账户' }}</text>
          </view>
          <button v-if="store.liveMode" class="logout" @click="openAccount">数据</button>
          <button class="logout" @click="backHome">退出</button>
        </view>
      </aside>

      <main class="main">
        <header class="topbar">
          <view>
            <text class="page-eyebrow">HEALTH CONSULTATION</text>
            <text class="page-title">
              {{ tabTitle }}
            </text>
          </view>
          <view class="mobile-brand">
            <text class="brand-mark small">清</text>
            <text>清诉</text>
          </view>
          <view class="top-actions">
            <text class="preview-badge">{{ store.liveMode ? '实时后端' : '交互预览' }}</text>
            <view class="top-avatar">王</view>
          </view>
        </header>

        <view v-if="store.activeTab === 'consult'" class="consult-view">
          <view class="conversation">
            <view class="conversation-head">
              <view>
                <text class="conversation-title">今天的健康咨询</text>
                <text class="conversation-subtitle">
                  {{ store.liveMode ? '已连接清诉业务 API' : '本地交互预览' }} · 不构成诊断
                </text>
              </view>
              <text class="status-dot">进行中</text>
            </view>

            <view v-if="store.errorText" class="error-banner">
              <text>{{ store.errorText }}</text>
              <button
                v-if="store.episodeId && !store.typing"
                class="retry-button"
                @click="store.retry"
              >
                重试本轮
              </button>
            </view>

            <view class="messages">
              <view
                v-for="message in store.messages"
                :key="message.id"
                class="message-row"
                :class="message.role"
              >
                <view v-if="message.role === 'assistant'" class="assistant-avatar">清</view>
                <view class="message-body">
                  <view v-if="message.kind === 'stage'" class="stage-message">
                    <text class="stage-mark">✓</text>
                    <text>{{ message.text }}</text>
                  </view>
                  <view v-else-if="message.kind === 'question'" class="question-card">
                    <text class="question-title">{{ message.title }}</text>
                    <text class="question-text">{{ message.text }}</text>
                    <view class="question-list">
                      <view
                        v-for="(item, index) in message.items"
                        :key="item"
                        class="question-item"
                      >
                        <text class="question-index">{{ index + 1 }}</text>
                        <text>{{ item }}</text>
                      </view>
                    </view>
                  </view>
                  <view v-else class="bubble">
                    <text>{{ message.text }}</text>
                  </view>
                </view>
                <view v-if="message.role === 'user'" class="user-avatar">王</view>
              </view>

              <view v-if="store.typing" class="message-row assistant">
                <view class="assistant-avatar">清</view>
                <view class="typing-bubble">
                  <text class="typing-dot" />
                  <text class="typing-dot" />
                  <text class="typing-dot" />
                </view>
              </view>

              <view v-if="store.resultReady" class="result-card">
                <view class="result-head">
                  <view>
                    <text class="result-eyebrow">分诊草稿</text>
                    <text class="result-title">{{ resultTitle }}</text>
                  </view>
                  <text class="result-dept">{{ resultDepartment }}</text>
                </view>
                <text class="result-summary">
                  {{ resultSummary }}
                </text>
                <view class="result-actions">
                  <button class="result-secondary" @click="store.switchTab('archive')">
                    查看健康档案
                  </button>
                  <button class="result-primary" @click="openDetail">查看完整结果</button>
                </view>
              </view>
            </view>

            <view
              v-if="store.liveMode && store.pendingQuestions.length"
              class="live-question-form"
            >
              <text class="live-form-title">补充关键信息</text>
              <view
                v-for="question in store.pendingQuestions"
                :key="question.field"
                class="live-field"
              >
                <text class="live-label">{{ question.text }}</text>
                <view v-if="question.options?.length" class="option-list">
                  <button
                    v-for="option in question.options"
                    :key="option"
                    class="option-chip"
                    :class="{ selected: store.answerDraft[question.field] === option }"
                    @click="store.answerDraft[question.field] = option"
                  >
                    {{ option }}
                  </button>
                </view>
                <input
                  v-model="store.answerDraft[question.field]"
                  class="live-input"
                  :placeholder="question.options?.join(' / ') || '请输入'"
                />
              </view>
              <view class="live-actions">
                <button class="result-secondary" @click="store.skipClarify">跳过追问</button>
                <button class="result-primary" @click="store.submitAnswers">提交补充信息</button>
              </view>
            </view>

            <view v-if="!store.liveMode && !store.resultReady" class="quick-wrap">
              <text class="quick-label">快速补充</text>
              <view class="quick-list">
                <button
                  v-for="item in store.remainingReplies"
                  :key="item"
                  class="quick-chip"
                  @click="store.answerQuick(item)"
                >
                  {{ item }}
                </button>
              </view>
            </view>

            <view class="composer">
              <textarea
                v-model="inputText"
                class="composer-input"
                auto-height
                maxlength="500"
                placeholder="继续补充您的不适或想确认的信息…"
                @confirm="send"
              />
              <button class="send" :disabled="store.typing || !inputText.trim()" @click="send">
                ↑
              </button>
            </view>
            <text class="composer-note">AI 建议仅供参考，不替代医生诊断。信息不足时会继续追问。</text>
          </view>
        </view>

        <view v-else-if="store.activeTab === 'archive'" class="dashboard-view">
          <view class="summary-grid">
            <view class="summary-card">
              <text class="summary-label">最近血压</text>
              <text class="summary-value">{{ latestPressure }}</text>
              <text class="summary-unit">mmHg · 今天 08:30</text>
            </view>
            <view class="summary-card">
              <text class="summary-label">历史问诊</text>
              <text class="summary-value">{{ episodeCount }}</text>
              <text class="summary-unit">次 · 最近 30 天</text>
            </view>
            <view class="summary-card accent">
              <text class="summary-label">下次随访</text>
              <text class="summary-value">{{ pendingCount }}</text>
              <text class="summary-unit">项待处理</text>
            </view>
          </view>

          <view class="dashboard-grid">
            <view class="panel chart-panel">
              <view class="panel-head">
                <text class="panel-title">家庭血压趋势</text>
                <view class="panel-head-actions">
                  <text class="panel-meta">最近 7 天</text>
                  <button class="mini-action" @click="openVitals">录入血压</button>
                </view>
              </view>
              <view class="chart">
                <view v-for="(item, index) in pressureTrend" :key="item.day" class="chart-col">
                  <text class="chart-value">{{ item.value }}</text>
                  <view class="chart-track">
                    <view class="chart-bar" :style="{ height: `${item.height}px` }" />
                  </view>
                  <text class="chart-day">{{ item.day }}</text>
                </view>
              </view>
            </view>

            <view class="panel">
              <view class="panel-head">
                <text class="panel-title">健康档案</text>
                <view class="panel-head-actions">
                  <text class="panel-action">健康信息</text>
                  <button class="mini-action" @click="openMedications">用药管理</button>
                </view>
              </view>
              <view class="profile-row"><text>慢性病</text><strong>高血压</strong></view>
              <view class="profile-row"><text>长期用药</text><strong>氨氯地平</strong></view>
              <view class="profile-row"><text>过敏史</text><strong>未记录</strong></view>
              <view class="profile-row"><text>常住城市</text><strong>上海市</strong></view>
            </view>
          </view>

          <view class="panel history-panel">
            <view class="panel-head">
              <text class="panel-title">历史问诊</text>
              <text class="panel-meta">全部记录</text>
            </view>
            <view
              v-for="item in history"
              :key="`${item.date}-${item.title}`"
              class="history-row"
              @click="openHistory(item.id)"
            >
              <view class="history-date">{{ item.date }}</view>
              <view class="history-main">
                <text class="history-title">{{ item.title }}</text>
                <text class="history-meta">{{ item.summary }}</text>
              </view>
              <text class="history-tag">{{ item.tag }}</text>
            </view>
          </view>
        </view>

        <view v-else class="dashboard-view">
          <view class="reminder-hero">
            <text class="reminder-eyebrow">NEXT FOLLOW-UP</text>
            <text class="reminder-title">48 小时后，记得回来看看</text>
            <text class="reminder-text">重新记录血压、头晕变化和用药情况。</text>
            <button class="reminder-action" @click="store.switchTab('consult')">开始复查</button>
          </view>

          <view class="reminder-list">
            <view v-for="item in reminders" :key="item.title" class="reminder-item">
              <view class="reminder-icon">{{ item.short }}</view>
              <view class="reminder-copy">
                <text class="reminder-item-title">{{ item.title }}</text>
                <text class="reminder-item-text">{{ item.text }}</text>
              </view>
              <text class="reminder-time">{{ item.time }}</text>
              <view v-if="store.liveMode && item.id" class="reminder-actions">
                <button
                  v-if="item.kind === 'medication'"
                  class="reminder-action-button"
                  @click="respondReminder(item, { action: 'taken' })"
                >
                  已服用
                </button>
                <button
                  v-if="item.kind === 'medication'"
                  class="reminder-action-button ghost"
                  @click="respondReminder(item, { action: 'snooze' })"
                >
                  稍后提醒
                </button>
                <button
                  v-if="item.kind === 'recheck'"
                  class="reminder-action-button"
                  @click="respondReminder(item, { action: 'visited' })"
                >
                  已就诊
                </button>
                <button
                  v-if="item.kind === 'recheck'"
                  class="reminder-action-button ghost"
                  @click="respondReminder(item, { action: 'improved' })"
                >
                  已好转
                </button>
                <template v-if="item.kind === 'followup'">
                  <button
                    class="reminder-action-button"
                    @click="respondFollowup(item.id, 'yes', 'no')"
                  >
                    已缓解
                  </button>
                  <button
                    class="reminder-action-button ghost"
                    @click="respondFollowup(item.id, 'no', 'no')"
                  >
                    仍未缓解
                  </button>
                  <button
                    class="reminder-action-button danger"
                    @click="respondFollowup(item.id, 'no', 'yes')"
                  >
                    出现新症状
                  </button>
                </template>
              </view>
            </view>
          </view>
        </view>
      </main>

      <aside class="patient-panel">
        <view class="patient-card">
          <view class="patient-head">
            <view class="patient-avatar">王</view>
            <view>
              <text class="patient-name">{{ patientName }}</text>
              <text class="patient-meta">{{ patientMeta }}</text>
            </view>
          </view>
          <view class="patient-divider" />
          <view class="metric-row">
            <view class="metric">
              <text class="metric-label">家庭血压</text>
              <text class="metric-value high">{{ latestPressure }}</text>
              <text class="metric-unit">mmHg</text>
            </view>
            <view class="metric">
              <text class="metric-label">心率</text>
              <text class="metric-value">{{ latestPulse }}</text>
              <text class="metric-unit">bpm</text>
            </view>
          </view>
          <view class="patient-note">
            <text class="note-label">用药</text>
            <text class="note-text">氨氯地平 · 每日一次</text>
          </view>
        </view>

        <view class="safety-card">
          <text class="side-title">本次关注</text>
          <view class="risk-row">
            <text class="risk-mark">!</text>
            <view>
              <text class="risk-title">自行停药风险</text>
              <text class="risk-text">长期处方药应先咨询医生</text>
            </view>
          </view>
          <view class="risk-row">
            <text class="risk-mark neutral">i</text>
            <view>
              <text class="risk-title">信息仍需补充</text>
              <text class="risk-text">血压、伴随症状与持续时间</text>
            </view>
          </view>
        </view>

        <view class="side-note">
          <text class="side-title">安全边界</text>
          <text class="side-note-text">不诊断疾病 · 不推荐处方 · 不替代医生</text>
        </view>
      </aside>
    </view>

    <view class="mobile-nav">
      <button
        v-for="item in mobileNav"
        :key="item.value"
        class="mobile-nav-item"
        :class="{ active: store.activeTab === item.value }"
        @click="store.switchTab(item.value)"
      >
        <text>{{ item.short }}</text>
        <text>{{ item.label }}</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'
import { useAuthStore } from '@/stores/auth'

const store = useWorkspaceStore()
const auth = useAuthStore()
const inputText = ref('')

const tabTitle = computed(() => {
  if (store.activeTab === 'archive') return '健康档案'
  if (store.activeTab === 'reminders') return '提醒随访'
  return '健康咨询'
})

const mobileNav = [
  { value: 'consult' as const, short: '诉', label: '咨询' },
  { value: 'archive' as const, short: '档', label: '档案' },
  { value: 'reminders' as const, short: '醒', label: '提醒' },
]

const fallbackPressureTrend = [
  { day: '周一', value: '138', height: 48 },
  { day: '周二', value: '142', height: 62 },
  { day: '周三', value: '145', height: 72 },
  { day: '周四', value: '150', height: 88 },
  { day: '周五', value: '146', height: 78 },
  { day: '周六', value: '156', height: 108 },
  { day: '今天', value: '162', height: 126 },
]

const fallbackHistory = [
  { id: 0, date: '11月19日', title: '头晕与自行停药想法', summary: '高血压随访 · 门诊', tag: '复评中' },
  { id: 0, date: '11月09日', title: '睡醒后头晕', summary: '家庭血压 150/92 mmHg', tag: '门诊' },
  { id: 0, date: '10月08日', title: '咳嗽、流涕', summary: '症状已缓解', tag: '自我观察' },
]

const fallbackReminders = [
  { id: 0, kind: 'followup' as const, short: '随', title: '血压与头晕随访', text: '记录血压并确认症状是否缓解', time: '48 小时后' },
  { id: 0, kind: 'medication' as const, short: '药', title: '晚间用药提醒', text: '按医生原方案服用氨氯地平', time: '20:00' },
  { id: 0, kind: 'recheck' as const, short: '复', title: '门诊复查准备', text: '携带近七天血压记录与用药清单', time: '本周六' },
]

onMounted(async () => {
  const result = await store.initialize()
  if (result.needsLogin) {
    uni.reLaunch({ url: '/pages/auth/index' })
    return
  }
  if (result.needsProfile) {
    uni.reLaunch({ url: '/pages/profile/index' })
  }
})

const patientName = computed(() => store.profile?.name || '王阿姨')
const patientMeta = computed(() => {
  const age = store.profile?.age_years
  const condition = store.profile?.conditions?.[0]
  return [age ? `${age}岁` : '', condition ? `${condition}随访` : '演示账户']
    .filter(Boolean)
    .join(' · ')
})
const latestPressure = computed(() => {
  const bp = store.archiveOverview?.vitals.latest_bp
  return bp ? `${bp.systolic}/${bp.diastolic}` : '162/98'
})
const latestPulse = computed(() => store.archiveOverview?.vitals.latest_bp?.pulse ?? 88)
const episodeCount = computed(
  () => store.archiveOverview?.trend_summary.episodes_90d ?? 7,
)
const pendingCount = computed(() => store.archiveOverview?.pending.total ?? 1)
const latestTriage = computed(
  () => store.archiveOverview?.trend_summary.latest_triage ?? 'clinic',
)
const resultTitle = computed(() =>
  store.result ? `${store.result.triage_label} · 按建议就诊` : '门诊 · 数日内',
)
const resultDepartment = computed(() => store.result?.department_primary || '心血管内科')
const resultSummary = computed(
  () =>
    store.result?.urgency_note ||
    '当前信息提示需要结合近期血压记录进一步评估。不建议自行停用长期处方药；如出现胸痛、呼吸困难或意识异常，请及时就医。',
)
const pressureTrend = computed(() => {
  const points = store.archiveTrend?.bp_points ?? []
  if (!points.length) return fallbackPressureTrend
  const recent = points.slice(-7)
  return recent.map((item, index) => ({
    day: item.at.slice(5, 10),
    value: String(item.systolic),
    height: 48 + index * 12,
  }))
})
const history = computed(() => {
  if (!store.historyEpisodes.length) return fallbackHistory
  return store.historyEpisodes.map((item) => ({
    id: item.id,
    date: item.created_at.slice(5, 10),
    title: item.complaint_excerpt,
    summary: item.department_primary,
    tag: item.triage_label,
  }))
})
const reminders = computed(() => {
  if (!store.flattenedReminders.length) return fallbackReminders
  return store.flattenedReminders.map((item) => ({
    id: item.id,
    kind: item.kind,
    short: item.kind === 'medication' ? '药' : item.kind === 'followup' ? '随' : '复',
    title: item.title,
    text: item.body,
    time: item.due_at.slice(5, 16),
  }))
})

function send() {
  if (!inputText.value.trim()) return
  store.sendMessage(inputText.value)
  inputText.value = ''
}

function startNewChat() {
  store.resetConversation()
}

function openDetail() {
  uni.navigateTo({ url: '/pages/result-detail/index' })
}

async function openHistory(id: number) {
  if (!id) return
  try {
    await store.openHistoryEpisode(id)
    uni.navigateTo({ url: '/pages/result-detail/index' })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : '读取问诊详情失败',
      icon: 'none',
    })
  }
}

function openVitals() {
  if (!store.liveMode) {
    uni.showToast({ title: '预览模式不会写入真实档案', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/vitals/create' })
}

function openMedications() {
  if (!store.liveMode) {
    uni.showToast({ title: '预览模式不会修改真实用药', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/medications/index' })
}

function openAccount() {
  uni.navigateTo({ url: '/pages/account/index' })
}

async function respondReminder(
  item: { id: number; title: string },
  payload: Record<string, unknown>,
) {
  try {
    await store.respondToReminder(item.id, payload)
    uni.showToast({ title: `${item.title}已更新`, icon: 'success' })
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : '提醒处理失败',
      icon: 'none',
    })
  }
}

async function respondFollowup(id: number, relieved: string, newSymptom: string) {
  await respondReminder(
    { id, title: '随访' },
    {
      action: 'answer',
      answers: { relieved, visited: 'no', new_symptom: newSymptom },
    },
  )
}

async function backHome() {
  try {
    await auth.logout()
  } finally {
    uni.reLaunch({ url: '/pages/auth/index' })
  }
}
</script>

<style scoped>
.workspace {
  min-height: 100vh;
  background: #f1f4f1;
  color: #203b32;
}

.app-layout {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 230px minmax(0, 1fr) 280px;
  background: #f1f4f1;
}

.sidebar {
  display: flex;
  min-height: 100vh;
  padding: 24px 16px 18px;
  border-right: 1px solid #e3eae6;
  background: #f8faf8;
  flex-direction: column;
  box-sizing: border-box;
}

.brand,
.patient-head,
.topbar,
.mobile-brand,
.top-actions,
.conversation-head,
.message-row,
.result-head,
.result-actions,
.account,
.panel-head,
.history-row,
.reminder-item,
.metric-row,
.risk-row {
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

.brand-mark.small {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  font-size: 16px;
}

.brand-name,
.brand-en,
.page-eyebrow,
.page-title,
.conversation-title,
.conversation-subtitle,
.result-eyebrow,
.result-title,
.result-summary,
.summary-label,
.summary-value,
.summary-unit,
.panel-title,
.panel-meta,
.chart-value,
.chart-day,
.history-title,
.history-meta,
.reminder-eyebrow,
.reminder-title,
.reminder-text,
.reminder-item-title,
.reminder-item-text,
.patient-name,
.patient-meta,
.metric-label,
.metric-value,
.metric-unit,
.note-label,
.note-text,
.side-title,
.risk-title,
.risk-text,
.side-note-text {
  display: block;
}

.brand-name {
  font-size: 18px;
  font-weight: 800;
}

.brand-en {
  margin-top: 1px;
  color: #91a49d;
  font-size: 9px;
  letter-spacing: 1px;
}

.new-chat {
  display: flex;
  width: 100%;
  height: 44px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 28px;
  border-radius: 12px;
  background: #175c49;
  color: #ffffff;
  font-size: 13px;
}

.nav-list {
  margin-top: 24px;
}

.nav-item {
  display: flex;
  width: 100%;
  height: 44px;
  align-items: center;
  gap: 11px;
  margin: 0 0 5px;
  padding: 0 12px;
  border-radius: 11px;
  background: transparent;
  color: #60756d;
  font-size: 13px;
  text-align: left;
}

.nav-item::after {
  border: 0;
}

.nav-item.active {
  background: #e3efe9;
  color: #175a47;
  font-weight: 700;
}

.nav-icon {
  display: flex;
  width: 25px;
  height: 25px;
  align-items: center;
  justify-content: center;
  border-radius: 7px;
  background: #edf2ef;
  font-size: 11px;
}

.nav-item.active .nav-icon {
  background: #cae4d9;
}

.recent {
  margin-top: 28px;
}

.recent-label {
  color: #96a39e;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
}

.recent-item {
  margin-top: 8px;
  padding: 10px 11px;
  border-radius: 10px;
}

.recent-item.active {
  background: #eef3f0;
}

.recent-title {
  display: block;
  color: #40594f;
  font-size: 12px;
  font-weight: 600;
}

.recent-meta {
  display: block;
  margin-top: 4px;
  color: #9aa6a1;
  font-size: 9px;
}

.account {
  align-items: center;
  gap: 9px;
  margin-top: auto;
  padding-top: 18px;
  border-top: 1px solid #e6ece9;
}

.account-avatar,
.top-avatar,
.patient-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #dcece5;
  color: #24634f;
  font-weight: 700;
}

.account-avatar {
  width: 34px;
  height: 34px;
  font-size: 13px;
}

.account-copy {
  min-width: 0;
  flex: 1;
}

.account-name {
  display: block;
  font-size: 12px;
  font-weight: 700;
}

.account-type {
  display: block;
  margin-top: 2px;
  color: #94a19c;
  font-size: 9px;
}

.logout {
  width: auto;
  margin: 0;
  padding: 0;
  background: transparent;
  color: #8a9993;
  font-size: 10px;
}

.logout::after {
  border: 0;
}

.main {
  min-width: 0;
  background: #ffffff;
}

.topbar {
  height: 78px;
  padding: 0 28px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #edf1ef;
  box-sizing: border-box;
}

.page-eyebrow {
  color: #7e9b8f;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1.4px;
}

.page-title {
  margin-top: 4px;
  font-size: 21px;
  font-weight: 800;
}

.top-actions {
  align-items: center;
  gap: 10px;
}

.preview-badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: #eff5f2;
  color: #567269;
  font-size: 10px;
}

.top-avatar {
  width: 34px;
  height: 34px;
  font-size: 12px;
}

.mobile-brand {
  display: none;
  align-items: center;
  gap: 7px;
  font-size: 14px;
  font-weight: 800;
}

.conversation {
  max-width: 820px;
  min-height: calc(100vh - 78px);
  margin: 0 auto;
  padding: 24px 26px 18px;
  box-sizing: border-box;
}

.conversation-head {
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 18px;
  border-bottom: 1px solid #eef2f0;
}

.conversation-title {
  font-size: 17px;
  font-weight: 800;
}

.conversation-subtitle {
  margin-top: 4px;
  color: #8b9a94;
  font-size: 10px;
}

.status-dot {
  padding: 5px 9px;
  border-radius: 999px;
  background: #e9f5ef;
  color: #2b7b5f;
  font-size: 9px;
}

.messages {
  padding: 22px 0 10px;
}

.message-row {
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 18px;
}

.message-row.user {
  justify-content: flex-end;
}

.assistant-avatar,
.user-avatar {
  display: flex;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  align-items: center;
  justify-content: center;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 700;
}

.assistant-avatar {
  background: #175c49;
  color: #ffffff;
}

.user-avatar {
  background: #dcece5;
  color: #24634f;
}

.message-body {
  max-width: min(76%, 620px);
}

.bubble {
  padding: 13px 15px;
  border-radius: 5px 14px 14px 14px;
  background: #f3f7f5;
  color: #425a51;
  font-size: 13px;
  line-height: 1.7;
}

.user .bubble {
  border-radius: 14px 5px 14px 14px;
  background: #175c49;
  color: #ffffff;
}

.stage-message {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 13px;
  border-radius: 10px;
  background: #f8faf9;
  color: #778a82;
  font-size: 11px;
  line-height: 1.55;
}

.stage-mark {
  color: #2e936e;
  font-weight: 800;
}

.question-card {
  padding: 16px;
  border: 1px solid #dce8e2;
  border-radius: 15px;
  background: #ffffff;
  box-shadow: 0 9px 26px rgba(26, 65, 51, 0.055);
}

.question-title {
  display: block;
  font-size: 14px;
  font-weight: 800;
}

.question-text {
  display: block;
  margin-top: 5px;
  color: #84948e;
  font-size: 11px;
}

.question-list {
  margin-top: 13px;
}

.question-item {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-top: 8px;
  color: #536a61;
  font-size: 12px;
  line-height: 1.5;
}

.question-index {
  display: flex;
  width: 20px;
  height: 20px;
  flex: 0 0 20px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e7f2ed;
  color: #2c725c;
  font-size: 9px;
  font-weight: 700;
}

.typing-bubble {
  display: flex;
  gap: 5px;
  padding: 13px 16px;
  border-radius: 5px 14px 14px 14px;
  background: #f3f7f5;
}

.typing-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #8fa49b;
}

.result-card {
  margin: 6px 0 18px 40px;
  padding: 18px;
  border-radius: 16px;
  background:
    linear-gradient(145deg, rgba(94, 166, 139, 0.1), transparent 50%),
    #f7faf8;
  border: 1px solid #d9e8e1;
}

.result-head {
  align-items: flex-start;
  justify-content: space-between;
}

.result-eyebrow {
  color: #679184;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1px;
}

.result-title {
  margin-top: 5px;
  font-size: 20px;
  font-weight: 800;
}

.result-dept {
  padding: 6px 9px;
  border-radius: 8px;
  background: #e4f1eb;
  color: #276d56;
  font-size: 10px;
}

.result-summary {
  margin-top: 13px;
  color: #60766d;
  font-size: 12px;
  line-height: 1.7;
}

.result-actions {
  gap: 8px;
  margin-top: 15px;
}

.result-actions button {
  flex: 1;
  margin: 0;
  border-radius: 10px;
  font-size: 11px;
}

.result-secondary {
  border: 1px solid #cdded6;
  background: #ffffff;
  color: #4c7365;
}

.result-primary {
  background: #175c49;
  color: #ffffff;
}

.quick-wrap {
  margin-top: 2px;
}

.quick-label {
  display: block;
  color: #96a39e;
  font-size: 9px;
  font-weight: 700;
}

.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 8px;
}

.quick-chip {
  width: auto;
  margin: 0;
  padding: 0 12px;
  border: 1px solid #d6e4de;
  border-radius: 999px;
  background: #ffffff;
  color: #4d7466;
  font-size: 10px;
  line-height: 34px;
}

.composer {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  margin-top: 18px;
  padding: 10px 10px 10px 15px;
  border: 1px solid #dbe7e2;
  border-radius: 15px;
  background: #ffffff;
  box-shadow: 0 8px 28px rgba(29, 67, 53, 0.06);
}

.composer-input {
  min-height: 26px;
  max-height: 100px;
  flex: 1;
  padding: 3px 0;
  color: #29453b;
  font-size: 13px;
  line-height: 1.55;
}

.send {
  display: flex;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
  border-radius: 11px;
  background: #175c49;
  color: #ffffff;
  font-size: 18px;
}

.send[disabled] {
  background: #d6e1dc;
  color: #93a39c;
}

.composer-note {
  display: block;
  margin-top: 8px;
  color: #a0aaa6;
  font-size: 9px;
  text-align: center;
}

.patient-panel {
  min-height: 100vh;
  padding: 22px 18px;
  border-left: 1px solid #e2e9e5;
  background: #f7f9f7;
  box-sizing: border-box;
}

.patient-card,
.safety-card,
.side-note {
  padding: 16px;
  border: 1px solid #e5ebe8;
  border-radius: 15px;
  background: #ffffff;
}

.safety-card,
.side-note {
  margin-top: 14px;
}

.patient-head {
  align-items: center;
  gap: 10px;
}

.patient-avatar {
  width: 40px;
  height: 40px;
  font-size: 14px;
}

.patient-name {
  font-size: 13px;
  font-weight: 800;
}

.patient-meta {
  margin-top: 3px;
  color: #8d9b95;
  font-size: 9px;
}

.patient-divider {
  height: 1px;
  margin: 14px 0;
  background: #edf1ef;
}

.metric-row {
  justify-content: space-between;
}

.metric-label {
  color: #8b9a94;
  font-size: 9px;
}

.metric-value {
  margin-top: 4px;
  color: #1e5e4b;
  font-size: 18px;
  font-weight: 800;
}

.metric-value.high {
  color: #b7795a;
}

.metric-unit {
  color: #98a49f;
  font-size: 8px;
}

.patient-note {
  margin-top: 14px;
  padding: 10px;
  border-radius: 9px;
  background: #f4f8f6;
}

.note-label {
  color: #8a9a94;
  font-size: 8px;
  font-weight: 700;
}

.note-text {
  margin-top: 4px;
  color: #4d665d;
  font-size: 10px;
}

.side-title {
  color: #6b8178;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1px;
}

.risk-row {
  align-items: flex-start;
  gap: 9px;
  margin-top: 13px;
}

.risk-mark {
  display: flex;
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #fff0ea;
  color: #b46249;
  font-size: 11px;
  font-weight: 800;
}

.risk-mark.neutral {
  background: #edf4f1;
  color: #4b7b6b;
}

.risk-title {
  font-size: 10px;
  font-weight: 700;
}

.risk-text {
  margin-top: 3px;
  color: #8d9a95;
  font-size: 9px;
  line-height: 1.5;
}

.side-note-text {
  margin-top: 7px;
  color: #85968f;
  font-size: 9px;
  line-height: 1.6;
}

.dashboard-view {
  padding: 26px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  padding: 18px;
  border: 1px solid #e4ebe7;
  border-radius: 15px;
  background: #ffffff;
}

.summary-card.accent {
  border-color: #d8e8e1;
  background: #edf6f2;
}

.summary-label {
  color: #8b9a94;
  font-size: 9px;
}

.summary-value {
  margin-top: 8px;
  color: #245c4b;
  font-size: 26px;
  font-weight: 800;
}

.summary-unit {
  margin-top: 4px;
  color: #8d9c96;
  font-size: 9px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr;
  gap: 14px;
  margin-top: 14px;
}

.panel {
  padding: 18px;
  border: 1px solid #e4ebe7;
  border-radius: 15px;
  background: #ffffff;
}

.panel-head {
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 13px;
  font-weight: 800;
}

.panel-meta,
.panel-action {
  color: #8e9c97;
  font-size: 9px;
}

.panel-action {
  color: #34745f;
}

.chart {
  display: flex;
  height: 180px;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10px;
  margin-top: 20px;
  padding-top: 10px;
  border-bottom: 1px solid #edf1ef;
}

.chart-col {
  display: flex;
  flex: 1;
  align-items: center;
  flex-direction: column;
}

.chart-value {
  color: #70847b;
  font-size: 8px;
}

.chart-track {
  display: flex;
  height: 132px;
  align-items: flex-end;
  margin-top: 4px;
}

.chart-bar {
  width: 18px;
  border-radius: 5px 5px 2px 2px;
  background: #87bda9;
}

.chart-col:last-child .chart-bar {
  background: #d09976;
}

.panel-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mini-action {
  width: auto;
  margin: 0;
  padding: 0 10px;
  border: 1px solid #cde5db;
  border-radius: 8px;
  background: #f3faf7;
  color: #397862;
  font-size: 8px;
  line-height: 28px;
}

.chart-day {
  margin-top: 5px;
  color: #94a19c;
  font-size: 8px;
}

.profile-row {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
  color: #84948e;
  font-size: 10px;
}

.profile-row strong {
  color: #425b52;
  font-weight: 600;
}

.history-panel {
  margin-top: 14px;
}

.history-row {
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid #edf1ef;
}

.history-row:last-child {
  border-bottom: 0;
}

.history-date {
  width: 70px;
  flex: 0 0 70px;
  color: #8d9b96;
  font-size: 9px;
}

.history-main {
  min-width: 0;
  flex: 1;
}

.history-title {
  font-size: 11px;
  font-weight: 700;
}

.history-meta {
  margin-top: 3px;
  color: #8e9b96;
  font-size: 9px;
}

.history-tag {
  padding: 4px 8px;
  border-radius: 999px;
  background: #eef5f2;
  color: #528170;
  font-size: 8px;
}

.reminder-hero {
  padding: 28px;
  border-radius: 18px;
  background:
    radial-gradient(circle at 90% 20%, rgba(124, 198, 170, 0.22), transparent 34%),
    #143f35;
  color: #ffffff;
}

.reminder-eyebrow {
  color: #85cdb5;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 1.5px;
}

.reminder-title {
  margin-top: 10px;
  font-size: 23px;
  font-weight: 800;
}

.reminder-text {
  margin-top: 8px;
  color: #bdd7ce;
  font-size: 11px;
}

.reminder-action {
  width: fit-content;
  margin: 18px 0 0;
  padding: 0 16px;
  border-radius: 10px;
  background: #e6f2ed;
  color: #194f40;
  font-size: 10px;
  line-height: 38px;
}

.reminder-list {
  margin-top: 16px;
}

.reminder-item {
  align-items: center;
  gap: 12px;
  margin-top: 10px;
  padding: 16px;
  border: 1px solid #e4ebe7;
  border-radius: 14px;
  background: #ffffff;
}

.reminder-icon {
  display: flex;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  align-items: center;
  justify-content: center;
  border-radius: 11px;
  background: #edf5f1;
  color: #2a6c56;
  font-size: 12px;
  font-weight: 800;
}

.reminder-copy {
  min-width: 0;
  flex: 1;
}

.reminder-item-title {
  font-size: 11px;
  font-weight: 700;
}

.reminder-item-text {
  margin-top: 3px;
  color: #8b9994;
  font-size: 9px;
}

.reminder-time {
  color: #5c7c70;
  font-size: 9px;
}

.reminder-item {
  flex-wrap: wrap;
}

.reminder-actions {
  display: flex;
  width: 100%;
  gap: 7px;
  padding-left: 48px;
  box-sizing: border-box;
}

.reminder-action-button {
  width: auto;
  margin: 0;
  padding: 0 11px;
  border-radius: 8px;
  background: #4ba58d;
  color: #ffffff;
  font-size: 8px;
  line-height: 28px;
}

.reminder-action-button.ghost {
  border: 1px solid #cde5db;
  background: #ffffff;
  color: #3c7663;
}

.reminder-action-button.danger {
  background: #d69372;
}

.mobile-nav {
  display: none;
}

@media (max-width: 1050px) {
  .app-layout {
    grid-template-columns: 200px minmax(0, 1fr);
  }

  .patient-panel {
    display: none;
  }
}

@media (max-width: 720px) {
  .app-layout {
    display: block;
    min-height: 100vh;
    padding-bottom: 62px;
  }

  .sidebar,
  .patient-panel {
    display: none;
  }

  .main {
    min-height: calc(100vh - 62px);
  }

  .topbar {
    position: sticky;
    top: 0;
    z-index: 10;
    height: 62px;
    padding: 0 16px;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(10px);
  }

  .page-eyebrow,
  .page-title,
  .top-actions {
    display: none;
  }

  .mobile-brand {
    display: flex;
  }

  .conversation {
    min-height: calc(100vh - 124px);
    padding: 18px 14px 6px;
  }

  .message-body {
    max-width: 82%;
  }

  .result-card {
    margin-left: 0;
  }

  .dashboard-view {
    padding: 16px;
  }

  .summary-grid,
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    gap: 9px;
  }

  .summary-card {
    padding: 14px;
  }

  .mobile-nav {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 20;
    display: flex;
    height: 62px;
    padding: 6px 18px calc(6px + env(safe-area-inset-bottom));
    border-top: 1px solid #e2e9e5;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(10px);
    box-sizing: border-box;
  }

  .mobile-nav-item {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: 3px;
    margin: 0;
    padding: 0;
    background: transparent;
    color: #8a9993;
    font-size: 9px;
    flex-direction: column;
  }

  .mobile-nav-item > text:first-child {
    font-size: 14px;
    font-weight: 800;
  }

  .mobile-nav-item.active {
    color: #1d6a53;
  }
}
</style>

<style scoped>
/* Mint theme overrides for the desktop workspace. */
.workspace {
  background: #eff9f5;
  color: #23473c;
}

.app-layout {
  background: #eff9f5;
}

.sidebar {
  border-color: #deeee7;
  background: #f8fdfb;
}

.brand-mark,
.assistant-avatar {
  background: #4ba58d;
  color: #ffffff;
}

.new-chat {
  background: #4ba58d;
  box-shadow: 0 8px 22px rgba(67, 148, 124, 0.16);
}

.nav-item {
  color: #6a8379;
}

.nav-item.active {
  background: #e0f5ed;
  color: #2c7964;
}

.nav-icon {
  background: #edf6f2;
}

.nav-item.active .nav-icon {
  background: #c9eadf;
}

.recent-item.active,
.patient-note {
  background: #eef8f4;
}

.account-avatar,
.top-avatar,
.patient-avatar,
.user-avatar {
  background: #d9f1e8;
  color: #2e745f;
}

.main {
  background: #fbfefc;
}

.topbar {
  border-color: #e4f0eb;
  background: rgba(251, 254, 252, 0.94);
}

.preview-badge,
.status-dot,
.question-index,
.result-dept {
  background: #e1f5ed;
  color: #357c67;
}

.bubble {
  background: #eef8f4;
  color: #476159;
}

.user .bubble {
  background: #55aa92;
  color: #ffffff;
}

.stage-message,
.typing-bubble {
  background: #f2faf7;
}

.question-card {
  border-color: #d7ebe3;
  box-shadow: 0 10px 28px rgba(69, 139, 119, 0.06);
}

.result-card {
  border-color: #d1e9df;
  background:
    linear-gradient(145deg, rgba(139, 215, 192, 0.16), transparent 52%),
    #f3fbf8;
}

.result-primary,
.send {
  background: #4ba58d;
  color: #ffffff;
}

.patient-panel {
  border-color: #deeee7;
  background: #f8fdfb;
}

.patient-card,
.safety-card,
.side-note,
.summary-card,
.panel,
.reminder-item {
  border-color: #e0eee8;
  background: #ffffff;
}

.summary-card.accent,
.reminder-hero {
  border-color: #cae9dd;
  background:
    radial-gradient(circle at 90% 15%, rgba(255, 255, 255, 0.4), transparent 35%),
    linear-gradient(135deg, #d4f1e7, #bde8da);
  color: #234d40;
}

.reminder-eyebrow {
  color: #337d68;
}

.reminder-text {
  color: #55786b;
}

.reminder-action {
  background: #ffffff;
  color: #2f765f;
}

.chart-bar {
  background: #8ed5bf;
}

.chart-col:last-child .chart-bar {
  background: #d9a17e;
}

.metric-value,
.summary-value {
  color: #2e735f;
}

.history-tag,
.reminder-icon {
  background: #e8f7f1;
  color: #367c67;
}

.mobile-nav {
  border-color: #deeee7;
  background: rgba(251, 254, 252, 0.97);
}

.mobile-nav-item.active {
  color: #398a72;
}

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  padding: 10px 12px;
  border: 1px solid #efd6cd;
  border-radius: 10px;
  background: #fff7f4;
  color: #9d5b49;
  font-size: 10px;
  line-height: 1.55;
}

.retry-button {
  width: auto;
  flex: 0 0 auto;
  margin: 0;
  padding: 0 12px;
  border-radius: 8px;
  background: #ffffff;
  color: #9d5b49;
  font-size: 9px;
  line-height: 32px;
}

.live-question-form {
  margin-top: 14px;
  padding: 15px;
  border: 1px solid #d6e9e1;
  border-radius: 14px;
  background: #f3faf7;
}

.live-form-title {
  display: block;
  color: #315f50;
  font-size: 12px;
  font-weight: 800;
}

.live-field {
  margin-top: 12px;
}

.live-label {
  display: block;
  margin-bottom: 6px;
  color: #587266;
  font-size: 10px;
}

.live-input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid #d4e8df;
  border-radius: 10px;
  background: #ffffff;
  color: #29493d;
  font-size: 11px;
  box-sizing: border-box;
}

.option-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 7px;
}

.option-chip {
  width: auto;
  margin: 0;
  padding: 0 10px;
  border: 1px solid #cfe5dc;
  border-radius: 999px;
  background: #ffffff;
  color: #547266;
  font-size: 9px;
  line-height: 30px;
}

.option-chip.selected {
  border-color: #57aa93;
  background: #dff4ed;
  color: #2d735e;
}

.live-actions {
  display: flex;
  gap: 8px;
  margin-top: 13px;
}

.live-actions button {
  flex: 1;
  margin: 0;
  border-radius: 9px;
  font-size: 10px;
}
</style>
