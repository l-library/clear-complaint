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
            <text class="recent-meta">刚刚，信息收集中</text>
          </view>
          <view class="recent-item">
            <text class="recent-title">咳嗽与鼻塞</text>
            <text class="recent-meta">11月9日，门诊</text>
          </view>
          <view class="recent-item">
            <text class="recent-title">睡眠不佳</text>
            <text class="recent-meta">10月28日，自我观察</text>
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
            <text class="page-eyebrow">{{ tabEyebrow }}</text>
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
                  {{ store.liveMode ? '已连接清诉业务 API' : '本地交互预览' }}，不构成诊断
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
              <text class="summary-unit">mmHg，今天 08:30</text>
            </view>
            <view class="summary-card">
              <text class="summary-label">历史问诊</text>
              <text class="summary-value">{{ episodeCount }}</text>
              <text class="summary-unit">次，最近 30 天</text>
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
            <text class="reminder-eyebrow">下一次随访</text>
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
            <text class="note-text">氨氯地平，每日一次</text>
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
          <text class="side-note-text">不诊断疾病，不推荐处方，也不替代医生。</text>
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

const tabEyebrow = computed(() => {
  if (store.activeTab === 'archive') return '健康数据'
  if (store.activeTab === 'reminders') return '随访任务'
  return '问诊工作台'
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
  { id: 0, date: '11月19日', title: '头晕与自行停药想法', summary: '高血压随访，门诊', tag: '复评中' },
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
    .join('，')
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
  store.result ? `${store.result.triage_label}，按建议就诊` : '门诊，数日内',
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
/* Mint theme overrides for the desktop workspace. */
.workspace {
  background: var(--palette-eff9f5);
  color: var(--palette-23473c);
}

.app-layout {
  background: var(--palette-eff9f5);
}

.sidebar {
  border-color: var(--palette-deeee7);
  background: var(--palette-f8fdfb);
}

.brand-mark,
.assistant-avatar {
  background: var(--palette-4ba58d);
  color: var(--palette-ffffff);
}

.new-chat {
  background: var(--palette-4ba58d);
  box-shadow: var(--shadow-new-chat);
}

.nav-item {
  color: var(--palette-6a8379);
}

.nav-item.active {
  background: var(--palette-e0f5ed);
  color: var(--palette-2c7964);
}

.nav-icon {
  background: var(--palette-edf6f2);
}

.nav-item.active .nav-icon {
  background: var(--palette-c9eadf);
}

.recent-item.active,
.patient-note {
  background: var(--palette-eef8f4);
}

.account-avatar,
.top-avatar,
.patient-avatar,
.user-avatar {
  background: var(--palette-d9f1e8);
  color: var(--palette-2e745f);
}

.main {
  background: var(--palette-fbfefc);
}

.topbar {
  border-color: var(--palette-e4f0eb);
  background: var(--wash-light-94);
}

.preview-badge,
.status-dot,
.question-index,
.result-dept {
  background: var(--palette-e1f5ed);
  color: var(--palette-357c67);
}

.bubble {
  background: var(--palette-eef8f4);
  color: var(--palette-476159);
}

.user .bubble {
  background: var(--palette-55aa92);
  color: var(--palette-ffffff);
}

.stage-message,
.typing-bubble {
  background: var(--palette-f2faf7);
}

.question-card {
  border-color: var(--palette-d7ebe3);
  box-shadow: var(--shadow-question);
}

.result-card {
  border-color: var(--palette-d1e9df);
  background:
    linear-gradient(145deg, var(--wash-result-16), transparent 52%),
    var(--palette-f3fbf8);
}

.result-primary,
.send {
  background: var(--palette-4ba58d);
  color: var(--palette-ffffff);
}

.patient-panel {
  border-color: var(--palette-deeee7);
  background: var(--palette-f8fdfb);
}

.patient-card,
.safety-card,
.side-note,
.summary-card,
.panel,
.reminder-item {
  border-color: var(--palette-e0eee8);
  background: var(--palette-ffffff);
}

.summary-card.accent,
.reminder-hero {
  border-color: var(--palette-cae9dd);
  background:
    radial-gradient(circle at 90% 15%, var(--wash-light-40), transparent 35%),
    linear-gradient(135deg, var(--palette-d4f1e7), var(--palette-bde8da));
  color: var(--palette-234d40);
}

.reminder-eyebrow {
  color: var(--palette-337d68);
}

.reminder-text {
  color: var(--palette-55786b);
}

.reminder-action {
  background: var(--palette-ffffff);
  color: var(--palette-2f765f);
}

.chart-bar {
  background: var(--palette-8ed5bf);
}

.chart-col:last-child .chart-bar {
  background: var(--palette-d9a17e);
}

.metric-value,
.summary-value {
  color: var(--palette-2e735f);
}

.history-tag,
.reminder-icon {
  background: var(--palette-e8f7f1);
  color: var(--palette-367c67);
}

.mobile-nav {
  border-color: var(--palette-deeee7);
  background: var(--wash-light-97);
}

.mobile-nav-item.active {
  color: var(--palette-398a72);
}

.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: var(--space-md);
  padding: var(--space-xs) var(--space-sm);
  border: 1px solid var(--palette-efd6cd);
  border-radius: 10px;
  background: var(--palette-fff7f4);
  color: var(--palette-9d5b49);
  font-size: 10px;
  line-height: 1.55;
}

.retry-button {
  width: auto;
  flex: 0 0 auto;
  margin: 0;
  padding: 0 12px;
  border-radius: 8px;
  background: var(--palette-ffffff);
  color: var(--palette-9d5b49);
  font-size: 9px;
  line-height: 32px;
}

.live-question-form {
  margin-top: var(--space-md);
  padding: var(--space-md);
  border: 1px solid var(--palette-d6e9e1);
  border-radius: 14px;
  background: var(--palette-f3faf7);
}

.live-form-title {
  display: block;
  color: var(--palette-315f50);
  font-size: 12px;
  font-weight: 800;
}

.live-field {
  margin-top: 12px;
}

.live-label {
  display: block;
  margin-bottom: var(--space-xs);
  color: var(--palette-587266);
  font-size: 10px;
}

.live-input {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--palette-d4e8df);
  border-radius: 10px;
  background: var(--palette-ffffff);
  color: var(--palette-29493d);
  font-size: 11px;
  box-sizing: border-box;
}

.option-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin-bottom: var(--space-xs);
}

.option-chip {
  width: auto;
  margin: 0;
  padding: 0 var(--space-xs);
  border: 1px solid var(--palette-cfe5dc);
  border-radius: 999px;
  background: var(--palette-ffffff);
  color: var(--palette-547266);
  font-size: 9px;
  line-height: 30px;
}

.option-chip.selected {
  border-color: var(--palette-57aa93);
  background: var(--palette-dff4ed);
  color: var(--palette-2d735e);
}

.live-actions {
  display: flex;
  gap: 8px;
  margin-top: var(--space-sm);
}

.live-actions button {
  flex: 1;
  margin: 0;
  border-radius: 9px;
  font-size: 10px;
}

/* Hallmark Dose redesign: consultation as the primary work surface. */
.workspace {
  min-height: 100vh;
  background: var(--color-paper);
  color: var(--color-ink);
}

.brand,
.patient-head,
.topbar,
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
.risk-row,
.quick-list,
.live-actions {
  display: flex;
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
.side-note-text,
.live-form-title,
.live-label {
  display: block;
}

.mobile-brand,
.mobile-nav {
  display: none;
}

.app-layout {
  display: grid;
  min-height: 100vh;
  grid-template-areas:
    "sidebar sidebar"
    "main patient";
  grid-template-columns: minmax(0, 1fr) 320px;
  grid-template-rows: 72px minmax(0, 1fr);
  width: min(1680px, 100%);
  margin: 0 auto;
  background: var(--color-paper);
}

.sidebar {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky-nav);
  display: flex;
  grid-area: sidebar;
  width: 100%;
  height: 72px;
  min-height: 0;
  padding: 0 var(--space-lg);
  align-items: center;
  border-right: 0;
  border-bottom: var(--rule-hair) solid var(--color-rule);
  background: var(--palette-fffdf6);
  flex-direction: row;
  box-sizing: border-box;
}

.sidebar .brand {
  display: flex;
  align-items: center;
  order: 0;
}

.brand-mark {
  width: 36px;
  height: 36px;
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

.brand-en {
  margin-top: 0;
  color: var(--color-muted);
  font-family: var(--font-outlier);
  font-size: 9px;
  letter-spacing: 0;
}

.nav-list {
  display: flex;
  order: 1;
  margin: 0 auto;
  align-items: center;
  gap: 4px;
}

.nav-item {
  display: flex;
  width: auto;
  height: 40px;
  margin: 0;
  padding: 0 var(--space-md);
  gap: var(--space-xs);
  border-radius: 8px;
  background: transparent;
  color: var(--color-muted);
  font-size: 13px;
  font-weight: 550;
  line-height: 1;
  align-items: center;
  justify-content: center;
}

.nav-item.active {
  background: var(--color-paper-3);
  color: var(--color-ink);
  font-weight: 650;
}

.nav-icon {
  display: flex;
  width: 20px;
  height: 20px;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
  background: transparent;
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
  font-size: 10px;
  line-height: 1;
}

.nav-item.active .nav-icon {
  background: var(--color-accent-soft);
}

.new-chat {
  display: flex;
  order: 2;
  width: auto;
  height: 38px;
  margin: 0 0 0 var(--space-md);
  padding: 0 var(--space-md);
  gap: var(--space-xs);
  border-radius: 8px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
  font-size: 12px;
  line-height: 38px;
  align-items: center;
  justify-content: center;
  box-shadow: none;
}

.recent {
  display: none;
}

.account {
  align-items: center;
  order: 3;
  margin: 0 0 0 var(--space-lg);
  padding: 0 0 0 var(--space-md);
  gap: var(--space-xs);
  border-top: 0;
  border-left: var(--rule-hair) solid var(--color-rule);
}

.account-copy {
  min-width: 0;
  flex: 1;
  max-width: 92px;
}

.account-avatar,
.top-avatar,
.patient-avatar,
.assistant-avatar,
.user-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 650;
}

.account-avatar {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
  font-size: 11px;
}

.account-name {
  color: var(--color-ink);
  font-size: 11px;
}

.account-type {
  margin-top: 0;
  color: var(--color-muted);
  font-size: 9px;
}

.logout {
  min-width: 38px;
  padding: 0 var(--space-xs);
  border-radius: 6px;
  background: transparent;
  color: var(--color-muted);
  font-size: 10px;
  line-height: 30px;
}

.main {
  grid-area: main;
  min-width: 0;
  background: var(--color-paper);
}

.topbar {
  display: flex;
  height: auto;
  min-height: 96px;
  padding: var(--space-lg) var(--space-xl) var(--space-md);
  border-bottom: 0;
  background: transparent;
  align-items: center;
  justify-content: space-between;
}

.page-eyebrow {
  color: var(--color-muted);
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 550;
}

.page-title {
  margin-top: 2px;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.035em;
}

.top-actions {
  align-items: center;
  gap: var(--space-md);
}

.preview-badge {
  padding: var(--space-2xs) var(--space-xs);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 6px;
  background: var(--palette-fffdf6);
  color: var(--color-muted);
  font-family: var(--font-outlier);
  font-size: 9px;
}

.top-avatar {
  width: 34px;
  height: 34px;
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
  font-size: 12px;
}

.consult-view {
  min-height: calc(100vh - 168px);
}

.conversation {
  width: min(880px, calc(100% - 64px));
  max-width: none;
  min-height: calc(100vh - 168px);
  margin: 0 auto;
  padding: 0 0 40px;
}

.conversation-head {
  display: flex;
  padding: var(--space-lg) 0 var(--space-md);
  align-items: center;
  justify-content: space-between;
  border-bottom: var(--rule-hair) solid var(--color-rule);
}

.conversation-title {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.conversation-subtitle {
  margin-top: var(--space-2xs);
  color: var(--color-muted);
  font-size: 11px;
}

.status-dot {
  padding: var(--space-2xs) var(--space-xs);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 5px;
  background: var(--palette-fffdf6);
  color: var(--color-accent-deep);
  font-size: 10px;
}

.error-banner {
  margin-top: var(--space-md);
  padding: var(--space-xs) var(--space-sm);
  border: var(--rule-hair) solid var(--border-accent-15);
  border-radius: 6px;
  background: var(--palette-fff7f4);
  color: var(--color-error);
  font-size: 12px;
}

.messages {
  padding: var(--space-xl) 0 var(--space-md);
}

.message-row {
  align-items: flex-start;
  gap: var(--space-sm);
  margin-bottom: var(--space-lg);
}

.message-row.user {
  justify-content: flex-end;
}

.assistant-avatar,
.user-avatar {
  width: 28px;
  height: 28px;
  flex-basis: 28px;
  border-radius: 7px;
  font-family: var(--font-outlier);
  font-size: 10px;
}

.assistant-avatar {
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
}

.user-avatar {
  background: var(--color-paper-3);
  color: var(--color-ink-2);
}

.message-body {
  max-width: min(78%, 650px);
}

.bubble {
  padding: var(--space-sm);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 4px 12px 12px;
  background: var(--palette-fffdf6);
  color: var(--color-ink-2);
  font-size: 14px;
  line-height: 1.7;
}

.user .bubble {
  border-color: var(--color-accent-deep);
  border-radius: 12px 4px 12px 12px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
}

.stage-message {
  padding: 0;
  gap: var(--space-xs);
  border-radius: 0;
  background: transparent;
  color: var(--color-muted);
  font-size: 12px;
}

.stage-mark {
  color: var(--color-accent);
}

.question-card {
  padding: var(--space-md) var(--space-lg);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 10px;
  background: var(--color-paper-2);
  box-shadow: none;
}

.question-title {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
}

.question-text {
  margin-top: var(--space-xs);
  color: var(--color-ink-2);
  font-size: 12px;
}

.question-list {
  margin-top: var(--space-md);
}

.question-item {
  gap: var(--space-sm);
  margin-top: var(--space-sm);
  color: var(--color-ink-2);
  font-size: 13px;
}

.question-index {
  width: 20px;
  height: 20px;
  flex-basis: 20px;
  border-radius: 4px;
  background: var(--color-accent-soft);
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
}

.typing-bubble {
  gap: var(--space-2xs);
  padding: var(--space-sm);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 4px 12px 12px;
  background: var(--palette-fffdf6);
}

.typing-dot {
  background: var(--color-muted);
}

.result-card {
  margin: var(--space-xs) 0 var(--space-lg) 40px;
  padding: var(--space-lg);
  border: var(--rule-hair) solid var(--color-accent);
  border-radius: 12px;
  background: var(--color-paper-2);
}

.result-head {
  align-items: flex-start;
  justify-content: space-between;
}

.result-eyebrow {
  color: var(--color-accent-deep);
  font-size: 11px;
  font-weight: 650;
}

.result-title {
  margin-top: var(--space-xs);
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 700;
  letter-spacing: -0.025em;
}

.result-dept {
  padding: 4px 8px;
  border: var(--rule-hair) solid var(--color-accent);
  border-radius: 5px;
  background: var(--palette-fffdf6);
  color: var(--color-accent-deep);
  font-size: 10px;
}

.result-summary {
  margin-top: var(--space-md);
  color: var(--color-ink-2);
  font-size: 13px;
}

.result-actions {
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.result-actions button {
  flex: 1;
  border-radius: 7px;
  font-size: 11px;
}

.result-secondary {
  border: var(--rule-hair) solid var(--surface-input-border);
  background: transparent;
  color: var(--color-ink-2);
}

.result-primary,
.send {
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
}

.quick-wrap {
  margin-top: 0;
}

.quick-label {
  color: var(--color-muted);
  font-size: 11px;
  font-weight: 550;
}

.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin-top: var(--space-sm);
}

.quick-chip {
  padding: 0 12px;
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 7px;
  background: var(--palette-fffdf6);
  color: var(--color-ink-2);
  font-size: 11px;
  line-height: 34px;
}

.composer {
  position: relative;
  bottom: auto;
  z-index: var(--z-raised);
  display: flex;
  gap: var(--space-sm);
  margin-top: var(--space-md);
  padding: 8px 8px 8px var(--space-md);
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 11px;
  background: var(--palette-fffdf6);
  box-shadow: none;
  align-items: flex-end;
}

.composer:focus-within {
  border-color: var(--color-focus);
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.composer-input {
  min-width: 0;
  min-height: 32px;
  flex: 1;
  padding: var(--space-2xs) 0;
  color: var(--color-ink);
  font-size: 14px;
}

.send {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  border-radius: 8px;
}

.composer-note {
  margin-top: var(--space-xs);
  color: var(--color-muted);
  font-size: 10px;
}

.patient-panel {
  position: sticky;
  top: 72px;
  grid-area: patient;
  min-width: 0;
  height: calc(100vh - 72px);
  overflow-y: auto;
  padding: var(--space-lg);
  border-left: var(--rule-hair) solid var(--color-rule);
  background: var(--palette-fffdf6);
}

.patient-card,
.safety-card,
.side-note {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.safety-card,
.side-note {
  margin-top: var(--space-lg);
  padding-top: var(--space-lg);
  border-top: var(--rule-hair) solid var(--color-rule);
}

.patient-head {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.patient-avatar {
  width: 38px;
  height: 38px;
  border-radius: 9px;
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

.patient-divider {
  margin: var(--space-md) 0;
  background: var(--color-rule);
}

.metric-row {
  justify-content: space-between;
  gap: var(--space-lg);
}

.metric-label {
  color: var(--color-muted);
  font-size: 10px;
}

.metric-value {
  margin-top: var(--space-xs);
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
  font-size: 20px;
  font-weight: 500;
}

.metric-value.high {
  color: var(--color-error);
}

.metric-unit {
  color: var(--color-muted);
  font-size: 9px;
}

.patient-note {
  margin-top: var(--space-md);
  padding: var(--space-sm);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 6px;
  background: var(--color-paper-2);
}

.note-label,
.side-title {
  color: var(--color-accent-deep);
  font-size: 10px;
  font-weight: 650;
}

.note-text {
  margin-top: var(--space-2xs);
  color: var(--color-ink-2);
  font-size: 11px;
}

.risk-row {
  align-items: flex-start;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.risk-mark {
  width: 22px;
  height: 22px;
  flex-basis: 22px;
  border-radius: 5px;
  background: var(--palette-fff0ea);
  color: var(--color-error);
  font-family: var(--font-outlier);
}

.risk-mark.neutral {
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
}

.risk-title {
  color: var(--color-ink);
  font-size: 11px;
}

.risk-text,
.side-note-text {
  margin-top: var(--space-2xs);
  color: var(--color-muted);
  font-size: 10px;
  line-height: 1.6;
}

.dashboard-view {
  width: min(1100px, calc(100% - 64px));
  margin: 0 auto;
  padding: var(--space-md) 0 var(--space-xl);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 12px;
  background: var(--palette-fffdf6);
}

.summary-card {
  padding: var(--space-lg);
  border: 0;
  border-radius: 0;
  background: transparent;
}

.summary-card + .summary-card {
  border-left: var(--rule-hair) solid var(--color-rule);
}

.summary-card.accent {
  background: var(--color-paper-2);
}

.summary-label {
  color: var(--color-muted);
  font-size: 11px;
}

.summary-value {
  margin-top: var(--space-xs);
  color: var(--color-ink);
  font-family: var(--font-outlier);
  font-size: 28px;
  font-weight: 500;
}

.summary-unit {
  margin-top: var(--space-2xs);
  color: var(--color-muted);
  font-size: 10px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.65fr);
  gap: var(--space-md);
  margin-top: var(--space-md);
}

.panel {
  padding: var(--space-lg);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 12px;
  background: var(--palette-fffdf6);
}

.panel-title {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}

.panel-head-actions {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
}

.panel-meta,
.panel-action,
.chart-value,
.chart-day,
.history-meta,
.history-date {
  color: var(--color-muted);
  font-size: 10px;
}

.mini-action {
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 6px;
  background: transparent;
  color: var(--color-accent-deep);
  font-size: 10px;
}

.chart-bar {
  background: var(--color-accent);
}

.chart-col:last-child .chart-bar {
  background: var(--color-error);
}

.profile-row,
.history-row {
  border-color: var(--color-rule);
}

.profile-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) 0;
  border-bottom: var(--rule-hair) solid var(--color-rule);
}

.chart {
  display: flex;
  height: 176px;
  gap: var(--space-sm);
  padding-top: var(--space-md);
  align-items: flex-end;
}

.chart-col {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  flex-direction: column;
}

.chart-track {
  display: flex;
  width: 22px;
  flex: 1;
  margin: var(--space-xs) 0;
  align-items: flex-end;
  border-radius: 4px 4px 0 0;
  background: var(--color-paper-2);
}

.chart-bar {
  width: 100%;
  border-radius: 4px 4px 0 0;
}

.history-panel {
  margin-top: var(--space-md);
}

.history-row {
  cursor: pointer;
  gap: var(--space-md);
  align-items: center;
  padding: var(--space-sm) 0;
  border-bottom: var(--rule-hair) solid var(--color-rule);
}

.history-main {
  min-width: 0;
  flex: 1;
}

.history-title {
  color: var(--color-ink);
  font-size: 12px;
}

.history-tag {
  padding: var(--space-2xs) var(--space-xs);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 5px;
  background: transparent;
  color: var(--color-accent-deep);
  font-size: 9px;
}

.reminder-hero {
  padding: var(--space-xl);
  border: var(--rule-hair) solid var(--color-accent);
  border-radius: 12px;
  background: var(--color-paper-2);
  color: var(--color-ink);
}

.reminder-eyebrow {
  color: var(--color-accent-deep);
  font-size: 11px;
}

.reminder-title {
  margin-top: var(--space-xs);
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.reminder-text {
  margin-top: var(--space-xs);
  color: var(--color-ink-2);
  font-size: 12px;
}

.reminder-action {
  margin-top: var(--space-md);
  border-radius: 7px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
  font-size: 11px;
}

.reminder-item {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-top: var(--space-sm);
  padding: var(--space-md);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 9px;
  background: var(--palette-fffdf6);
}

.reminder-icon {
  width: 32px;
  height: 32px;
  flex-basis: 32px;
  border-radius: 7px;
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
  font-family: var(--font-outlier);
}

.reminder-copy {
  min-width: 0;
  flex: 1;
}

.reminder-actions {
  display: flex;
  width: 100%;
  flex-wrap: wrap;
  gap: var(--space-xs);
  padding-left: 48px;
}

.reminder-item-title {
  color: var(--color-ink);
  font-size: 12px;
}

.reminder-item-text,
.reminder-time {
  color: var(--color-muted);
  font-size: 10px;
}

.reminder-action-button {
  border-radius: 6px;
  background: var(--color-accent-deep);
  color: var(--color-accent-ink);
  font-size: 9px;
}

.reminder-action-button.ghost {
  border: var(--rule-hair) solid var(--surface-input-border);
  background: transparent;
  color: var(--color-ink-2);
}

.reminder-action-button.danger {
  border: var(--rule-hair) solid var(--color-error);
  background: transparent;
  color: var(--color-error);
}

.live-question-form {
  margin-top: var(--space-md);
  padding: var(--space-md);
  border: var(--rule-hair) solid var(--color-rule);
  border-radius: 10px;
  background: var(--palette-fffdf6);
}

.live-form-title {
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 700;
}

.live-label {
  margin-bottom: var(--space-xs);
  color: var(--color-ink-2);
  font-size: 11px;
}

.live-input {
  height: 40px;
  padding: 0 var(--space-sm);
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 7px;
  background: var(--surface-input);
  color: var(--color-ink);
  font-size: 12px;
}

.option-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  margin-bottom: var(--space-xs);
}

.option-chip {
  padding: 0 var(--space-xs);
  border: var(--rule-hair) solid var(--surface-input-border);
  border-radius: 6px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 10px;
  line-height: 30px;
}

.option-chip.selected {
  border-color: var(--color-accent);
  background: var(--color-paper-3);
  color: var(--color-accent-deep);
}

.nav-item:focus-visible,
.new-chat:focus-visible,
.logout:focus-visible,
.quick-chip:focus-visible,
.result-actions button:focus-visible,
.option-chip:focus-visible,
.live-input:focus-visible,
.mini-action:focus-visible,
.reminder-action:focus-visible,
.reminder-action-button:focus-visible,
.history-row:focus-visible,
.send:focus-visible,
.composer-input:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.nav-item:active,
.new-chat:active,
.quick-chip:active,
.result-actions button:active,
.option-chip:active,
.mini-action:active,
.reminder-action:active,
.reminder-action-button:active,
.send:active {
  transform: translateY(1px);
}

.new-chat[disabled],
.send[disabled],
.result-actions button[disabled],
.reminder-action-button[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 1080px) {
  .app-layout {
    grid-template-areas:
      "sidebar"
      "main";
    grid-template-columns: minmax(0, 1fr);
  }

  .patient-panel {
    display: none;
  }

  .account-copy {
    display: none;
  }
}

@media (max-width: 760px) {
  .app-layout {
    display: block;
    min-height: 100vh;
    padding-bottom: 68px;
  }

  .sidebar,
  .patient-panel {
    display: none;
  }

  .main {
    min-height: calc(100vh - 68px);
  }

  .topbar {
    position: relative;
    justify-content: flex-start;
    min-height: 64px;
    padding: 12px 16px 8px;
    background: var(--color-paper);
  }

  .page-eyebrow,
  .page-title,
  .top-actions {
    display: none;
  }

  .mobile-brand {
    display: flex;
    color: var(--color-ink);
  }

  .consult-view {
    min-height: calc(100vh - 132px);
  }

  .conversation {
    width: 100%;
    min-height: calc(100vh - 132px);
    padding: 0 16px 24px;
  }

  .conversation-head {
    padding-top: 12px;
  }

  .messages {
    padding: var(--space-lg) 0 0;
  }

  .message-body {
    max-width: 84%;
  }

  .message-row {
    gap: var(--space-xs);
    margin-bottom: var(--space-sm);
  }

  .result-card {
    margin-left: 0;
  }

  .composer {
    position: relative;
    bottom: auto;
  }

  .dashboard-view {
    width: 100%;
    padding: 0 16px var(--space-lg);
  }

  .summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .summary-card + .summary-card {
    border-top: var(--rule-hair) solid var(--color-rule);
    border-left: 0;
  }

  .dashboard-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .mobile-nav {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: var(--z-sticky-nav);
    display: flex;
    height: 68px;
    padding: var(--space-xs) var(--space-md) calc(var(--space-xs) + env(safe-area-inset-bottom));
    border-top: var(--rule-hair) solid var(--color-rule);
    background: var(--palette-fffdf6);
    box-sizing: border-box;
  }

  .mobile-nav-item {
    display: flex;
    flex: 1;
    margin: 0;
    padding: 0;
    align-items: center;
    justify-content: center;
    gap: 2px;
    background: transparent;
    color: var(--color-muted);
    font-size: 10px;
    flex-direction: column;
    white-space: nowrap;
  }

  .mobile-nav-item.active {
    color: var(--color-accent-deep);
  }
}
</style>
