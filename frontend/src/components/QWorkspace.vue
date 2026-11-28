<template>
  <view class="app-shell" :class="{ 'workspace-shell': screen === 'workspace', 'is-transitioning': transferring }">
    <template v-if="screen === 'landing'">
      <view class="landing-header">
        <view class="wordmark">
          <image src="/static/brand.svg" class="brand-mark" />
          <text>清诉</text>
        </view>
        <view class="header-actions">
          <button role="button" tabindex="0" @keydown="activateButton" class="text-button archive-link" @click="navigate('archive')">健康档案</button>
          <button role="button" tabindex="0" @keydown="activateButton" class="small-primary" @click="navigate('chat')">开始交流</button>
          <button role="button" tabindex="0" @keydown="activateButton" class="icon-button" :aria-label="menuOpen ? '关闭导航菜单' : '打开导航菜单'" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen"><QIcon :name="menuOpen ? 'close' : 'menu'" /></button>
        </view>
        <view v-if="menuOpen" class="header-menu">
          <button role="button" tabindex="0" @keydown="activateButton" @click="navigate('chat'); menuOpen = false">AI 对话</button>
          <button role="button" tabindex="0" @keydown="activateButton" @click="navigate('archive'); menuOpen = false">健康档案</button>
          <button role="button" tabindex="0" @keydown="activateButton" @click="navigate('plans'); menuOpen = false">健康计划</button>
          <button role="button" tabindex="0" @keydown="activateButton" @click="navigate('daily'); menuOpen = false">每日小结</button>
        </view>
      </view>
      <view class="landing-main">
        <view class="landing-intro">
          <QBrandMark class="hero-mark" animated />
          <view class="landing-title">你好，我是<text class="name-accent">清诉</text>。</view>
          <text class="intro-copy">描述你的不适，<text class="strong">一起把情况说清楚。</text></text>
          <text class="intro-detail">记录症状、管理健康档案，及时回顾每一次变化。</text>
        </view>
        <view class="landing-composer">
          <QComposer v-model="draft" label="今天有什么想告诉我？" placeholder="描述你的不适，或写下想了解的健康问题…" :error="error" :pending="pending" @send="handleSend" @attach="navigate('archive')" />
          <view class="composer-footnote">
            <text>登录后可保存咨询记录</text>
            <view><QIcon name="shield" /><text>仅供健康信息整理</text></view>
          </view>
          <button role="button" tabindex="0" @keydown="activateButton" class="landing-daily-card" @click="navigate('daily')">
            <view class="landing-daily-copy">
              <text class="landing-daily-title">每日小结</text>
              <text class="landing-daily-detail">回看今天值得肯定的事，以及明天可以做的小事。</text>
            </view>
            <view class="landing-daily-action"><text>查看每日小结</text><QIcon name="arrow-right" /></view>
          </button>
        </view>
      </view>
      <view class="landing-footer"><text>清诉</text><text>仅供健康信息整理</text></view>
    </template>

    <template v-else>
      <view class="sidebar" :class="{ 'sidebar-expanded': sidebarExpanded }">
        <button role="button" tabindex="0" @keydown="activateButton" v-if="sidebarExpanded" class="sidebar-logo" aria-label="返回首页" @click="goHome">
          <image src="/static/brand.svg" class="brand-mark" /><text v-if="sidebarExpanded" class="sidebar-brand">清诉</text>
        </button>
        <button role="button" tabindex="0" @keydown="activateButton" class="sidebar-collapse icon-button" :aria-label="sidebarExpanded ? '收起导航' : '展开导航'" :aria-expanded="sidebarExpanded" @click="sidebarExpanded = !sidebarExpanded"><QIcon name="collapse" /></button>
        <view class="sidebar-nav">
          <button role="button" tabindex="0" @keydown="activateButton" class="nav-item" :class="{ 'nav-item-active': activeTab === 'chat' }" :aria-pressed="activeTab === 'chat'" aria-label="AI 对话" @click="navigate('chat')">
            <QIcon name="chat" /><text v-if="sidebarExpanded">AI 对话</text><text v-else class="nav-tooltip">AI 对话</text>
          </button>
          <button role="button" tabindex="0" @keydown="activateButton" class="nav-item" :class="{ 'nav-item-active': activeTab === 'archive' }" :aria-pressed="activeTab === 'archive'" aria-label="健康档案" @click="navigate('archive')">
            <QIcon name="file" /><text v-if="sidebarExpanded">健康档案</text><text v-else class="nav-tooltip">健康档案</text>
          </button>
          <button role="button" tabindex="0" @keydown="activateButton" class="nav-item" :class="{ 'nav-item-active': activeTab === 'plans' }" :aria-pressed="activeTab === 'plans'" aria-label="健康计划" @click="navigate('plans')">
            <QIcon name="calendar" /><text v-if="sidebarExpanded">健康计划</text><text v-else class="nav-tooltip">健康计划</text>
          </button>
          <button role="button" tabindex="0" @keydown="activateButton" class="nav-item" :class="{ 'nav-item-active': activeTab === 'daily' }" :aria-pressed="activeTab === 'daily'" aria-label="每日小结" @click="navigate('daily')">
            <QIcon name="clock" /><text v-if="sidebarExpanded">每日小结</text><text v-else class="nav-tooltip">每日小结</text>
          </button>
        </view>
        <view v-if="sidebarExpanded" class="recent-conversations">
          <text class="recent-heading">最近对话</text>
          <text v-if="!recentConversations.length" class="recent-empty">从一次新的问诊开始</text>
          <button role="button" tabindex="0" @keydown="activateButton" v-for="item in recentConversations.slice(0, 8)" :key="item.id" class="recent-conversation" :class="{ 'recent-current': item.id === activeConversation?.id }" :aria-label="`问诊：${item.title}`" @click="openConversation(item.id)">
            <QIcon name="chat" /><view><text class="recent-title">{{ item.title }}</text><text class="recent-kind">症状问诊</text></view>
          </button>
        </view>
        <view class="sidebar-bottom">
          <button role="button" tabindex="0" @keydown="activateButton" class="nav-item" aria-label="新建问诊" @click="requestNewConversation"><QIcon name="plus" /><text v-if="sidebarExpanded">新建问诊</text><text v-else class="nav-tooltip">新建问诊</text></button>
          <button role="button" tabindex="0" @keydown="activateButton" class="sidebar-person" aria-label="账户信息" @click="showProfile"><view class="patient-avatar"><QIcon name="user" /></view><view v-if="sidebarExpanded"><text class="patient-name">{{ store.profile.name }}</text><text class="patient-description">账户信息</text></view></button>
        </view>
      </view>
      <view class="workspace-main">
        <view v-if="activeTab === 'chat'" class="chat-mobile-toolbar"><button role="button" tabindex="0" @keydown="activateButton" class="mobile-home" aria-label="返回首页" @click="goHome"><image src="/static/brand.svg" /><text>清诉</text></button><view><button role="button" tabindex="0" @keydown="activateButton" class="icon-button" aria-label="新建问诊" @click="requestNewConversation"><QIcon name="plus" /></button><button role="button" tabindex="0" @keydown="activateButton" class="icon-button" aria-label="最近对话" :aria-expanded="historyOpen" @click="historyOpen = !historyOpen"><QIcon name="clock" /></button></view></view>
        <view v-if="activeTab !== 'chat'" class="workspace-header">
          <view class="breadcrumb"><text class="breadcrumb-brand">清诉</text><text class="slash">/</text><text>{{ pageTitle }}</text></view>
          <view class="workspace-actions"><button role="button" tabindex="0" @keydown="activateButton" class="icon-button mobile-history-button" aria-label="最近对话" :aria-expanded="historyOpen" @click="historyOpen = !historyOpen"><QIcon name="clock" /></button><button role="button" tabindex="0" @keydown="activateButton" class="icon-button" aria-label="返回首页" @click="goHome"><QIcon name="home" /></button></view>
        </view>
        <view v-if="historyOpen" class="history-menu"><text class="recent-heading">最近对话</text><button role="button" tabindex="0" @keydown="activateButton" v-for="item in recentConversations" :key="item.id" class="recent-conversation" @click="openConversation(item.id); historyOpen = false"><QIcon name="chat" /><view><text class="recent-title">{{ item.title }}</text><text class="recent-kind">问诊</text></view></button><button role="button" tabindex="0" @keydown="activateButton" class="history-new" @click="requestNewConversation(); historyOpen = false">＋ 新建问诊</button></view>
        <view class="workspace-content">
          <view v-show="activeTab === 'archive'" class="workspace-pane"><QHealthArchive @open-conversation="openConversation" /></view>
          <view v-show="activeTab === 'plans'" class="workspace-pane"><QHealthPlans @open-followup="openFollowUp" @open-archive="navigate('archive')" /></view>
          <view v-show="activeTab === 'daily'" class="workspace-pane"><QDailyReport /></view>
          <view v-if="activeTab === 'chat' && !messages.length" class="empty-chat">
            <view class="chat-welcome">
              <QBrandMark class="welcome-mark" animated />
              <view class="welcome-title">今天，有什么想告诉我？</view>
            </view>
            <view class="chat-entry-composer">
              <button role="button" tabindex="0" @keydown="activateButton" class="record-connector" @click="navigate('archive')"><text>查看我的健康档案</text><QIcon name="arrow-right" /></button>
              <QComposer ref="entryComposer" v-model="draft" compact placeholder="描述你的不适，或写下想了解的健康问题…" :error="error" :pending="pending" @send="handleSend" @attach="navigate('archive')" />
              <text class="medical-note">健康信息整理，不能替代医生诊断。</text>
            </view>
            <view class="quick-start"><view class="prompt-list"><button role="button" tabindex="0" @keydown="activateButton" v-for="prompt in prompts" :key="prompt.title" class="prompt-chip" @click="choosePrompt(prompt.content)"><text>{{ prompt.title }}</text></button></view></view>
          </view>
          <view v-else-if="activeTab === 'chat'" class="conversation-layout">
            <view class="conversation-column">
              <view v-if="isFollowUp" class="follow-up-context"><QIcon name="calendar" /><view><text class="context-title">{{ store.followUpReminder?.title }}</text><button role="button" tabindex="0" @keydown="activateButton" class="context-link" @click="navigate('plans')">查看健康计划</button></view></view>
              <view v-else class="emergency-note"><QIcon name="info" /><text>如有紧急情况，请立即联系当地急救服务。</text></view>
              <scroll-view class="messages-scroll" scroll-y :scroll-top="messageScrollTop" :scroll-with-animation="false">
                <view class="messages-list">
                  <view v-for="message in messages" :id="`message-${message.id}`" :key="message.id" class="message" :class="`message-${message.role}`">
                    <view v-if="message.role === 'assistant'" class="assistant-identity"><image src="/static/brand.svg" /><text>清诉</text></view>
                    <view :id="`bubble-${message.id}`" class="message-bubble" :class="{ 'bubble-in-flight': message.id === flyingMessageId }"><text>{{ message.content }}</text></view>
                  </view>
                  <view v-if="pending" id="message-pending" class="pending-message" role="status"><view class="loading-dots"><text /><text /><text /></view><text>{{ store.stage || '正在整理你的描述…' }}</text></view>
                  <QConsultationFlow />
                  <view id="message-end" class="message-end" />
                </view>
              </scroll-view>
              <view class="conversation-composer">
                <view class="conversation-tools">
                  <text>{{ savedLine }}</text>
                  <button v-if="saved && !isFollowUp" role="button" tabindex="0" @keydown="activateButton" class="conversation-daily-link" @click="navigate('daily')">查看今日小结</button>
                </view>
                <view v-if="isCompletedFollowUp" class="completed-conversation"><QIcon name="check" /><text>本次随访已完成，记录已归档。出现新的不适可以新建问诊。</text><button role="button" tabindex="0" @keydown="activateButton" @click="requestNewConversation">新建问诊</button></view>
                <QComposer v-else ref="replyComposer" v-model="draft" compact :context-label="isFollowUp ? '随访回复' : '问诊交流'" :placeholder="composerPlaceholder" :pending="pending" :error="error" @send="handleSend" @attach="navigate('archive')" />
                <text class="medical-note">健康信息整理，不构成诊断。</text>
              </view>
            </view>
            <view v-if="!store.accountOpen" class="context-column">
              <view class="context-heading"><text>纠偏与评估</text></view>
              <QEpisodeReview :detail="store.detail" :pending="pending" />
            </view>
          </view>
        </view>
      </view>
      <view class="mobile-nav" aria-label="主要导航">
        <button role="button" tabindex="0" @keydown="activateButton" aria-label="账户信息" @click="showProfile"><QIcon name="user" /><text>账户</text></button>
        <button role="button" tabindex="0" @keydown="activateButton" v-for="tab in navigationTabs" :key="tab.id" :class="{ 'mobile-tab-active': activeTab === tab.id }" :aria-pressed="activeTab === tab.id" @click="navigate(tab.id)"><QIcon :name="tab.icon" /><text>{{ tab.title }}</text></button>
      </view>
    </template>
    <view v-if="store.accountOpen" class="account-overlay" @click="store.accountOpen = false"><view class="context-column account-dialog" role="dialog" aria-modal="true" aria-label="账户信息" @click.stop @keydown="handleDialogKey"><button role="button" tabindex="0" @keydown="activateButton" class="icon-button account-close" aria-label="关闭账户信息" @click="store.accountOpen = false"><QIcon name="close" /></button><QAccountPanel /></view></view>
    <QMessageTransition ref="messageTransition" @complete="finishTransfer" />
  </view>
</template>

<script setup lang="ts">
import { activateButton } from '@/components/buttonKeyboard'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import QIcon from '@/components/QIcon.vue'
import QBrandMark from '@/components/QBrandMark.vue'
import QComposer from '@/components/QComposer.vue'
import QHealthArchive from '@/components/QLiveArchive.vue'
import QHealthPlans from '@/components/QLivePlans.vue'
import QDailyReport from '@/components/QDailyReport.vue'
import QAccountPanel from '@/components/QAccountPanel.vue'
import QEpisodeReview from '@/components/QEpisodeReview.vue'
import QConsultationFlow from '@/components/QConsultationFlow.vue'
import QMessageTransition from '@/components/QMessageTransition.vue'
import { useLiveWorkspaceStore, type WorkspaceTab } from '@/stores/liveWorkspace'
import type { ReminderItem } from '@/api/archive'

const store = useLiveWorkspaceStore()
const { screen, activeTab, draft, messages, pending, error, saved, activeConversation, recentConversations } = storeToRefs(store)
const menuOpen = ref(false)
const sidebarExpanded = ref(false)
const entryComposer = ref<InstanceType<typeof QComposer> | null>(null)
const replyComposer = ref<InstanceType<typeof QComposer> | null>(null)
const historyOpen = ref(false)
const messageScrollTop = ref(0)
const messageCount = computed(() => messages.value.length)
const isFollowUp = computed(() => Boolean(store.followUpReminder))
const isCompletedFollowUp = computed(() => Boolean(store.followUpReminder && store.followUpReminder.status !== 'pending'))
// 占位文案必须与 sendMessage 的真实行为一致：无结论已存档时输入会开新问诊，
// 「正在整理…」只在等待流式响应时出现
const composerPlaceholder = computed(() => {
  if (isFollowUp.value) return '随访补充说明…'
  if (store.result) return '补充新情况，会更新这份建议…'
  if (store.pendingQuestion) return '回答上方的问题…'
  if (pending.value) return '正在整理…'
  if (store.noConclusionText) return '本次问诊已结束，输入新的描述将开始新的问诊。'
  return '描述你的不适，或写下想了解的健康问题…'
})
// 保存行只在后端确实建了提醒时才提提醒（api.md 5.7 的 reminder_created）
const savedLine = computed(() => {
  if (isFollowUp.value) return '提交后保存本次随访'
  if (!saved.value) return '问诊完成后自动保存至健康档案。'
  return store.reminderCreated ? '问诊完成，已保存至健康档案，并按建议安排了提醒。' : '问诊完成，已保存至健康档案。'
})
const pageTitles: Record<WorkspaceTab, string> = { chat: 'AI 对话', archive: '健康档案', plans: '健康计划', daily: '每日小结' }
const pageTitle = computed(() => activeTab.value === 'chat' ? activeConversation.value?.title || 'AI 对话' : pageTitles[activeTab.value])
const navigationTabs: { id: WorkspaceTab; title: string; icon: string }[] = [
  { id: 'chat', title: 'AI 对话', icon: 'chat' },
  { id: 'archive', title: '健康档案', icon: 'file' },
  { id: 'plans', title: '健康计划', icon: 'calendar' },
  { id: 'daily', title: '每日小结', icon: 'clock' },
]
const workspacePaths: Record<WorkspaceTab, string> = {
  chat: 'pages/chat/index',
  archive: 'pages/health-records/index',
  plans: 'pages/health-plans/index',
  daily: 'pages/daily/index',
}
interface ElementRect { left: number; top: number; width: number; height: number }
const messageTransition = ref<InstanceType<typeof QMessageTransition> | null>(null)
const transferring = ref(false)
const flyingMessageId = ref('')
const prompts = [
  { title: '描述我的症状', content: '我想记录最近不适的变化。' },
  { title: '整理就医问题', content: '我想整理一下最近的症状。' },
  { title: '记录不适变化', content: '我想补充目前不适的情况。' },
]

function measure(selector: string): Promise<ElementRect | null> {
  return new Promise((resolve) => {
    uni.createSelectorQuery().select(selector).boundingClientRect((result) => {
      const rect = result as ElementRect | null
      resolve(rect && rect.width > 0 ? rect : null)
    }).exec()
  })
}

async function handleSend() {
  if (transferring.value || pending.value) return
  const fromLanding = screen.value === 'landing'
  const shouldAnimate = fromLanding || messages.value.length === 0
  if (!draft.value.trim() || !shouldAnimate) {
    store.sendMessage()
    return
  }
  const text = draft.value.trim()
  const originSelector = fromLanding ? '.landing-composer .composer' : '.chat-entry-composer .composer'
  transferring.value = true
  const origin = await measure(originSelector)
  if (!store.sendMessage()) { finishTransfer(); return }
  flyingMessageId.value = messages.value[messages.value.length - 1]?.id || ''
  await nextTick()
  const target = await measure(`#bubble-${flyingMessageId.value}`)
  if (origin && target && messageTransition.value) {
    messageTransition.value.play(text, origin, target)
  } else {
    finishTransfer()
  }
}

function finishTransfer() {
  transferring.value = false
  flyingMessageId.value = ''
  if (screen.value === 'workspace' && activeTab.value === 'chat') navigate('chat')
}

function choosePrompt(content: string) {
  draft.value = content
  error.value = ''
  nextTick(() => (messages.value.length ? replyComposer.value : entryComposer.value)?.focus())
}

let navigating = false
function navigate(tab: WorkspaceTab) {
  store.openWorkspace(tab)
  const path = workspacePaths[tab]
  const query = tab === 'chat' && store.followUpReminder
    ? `?reminder_id=${store.followUpReminder.id}&date=${store.followUpReminder.due_at.slice(0, 10)}`
    : tab === 'chat' && activeConversation.value
    ? `?conversation_id=${encodeURIComponent(activeConversation.value.id)}`
    : tab === 'plans' ? `?tab=${store.selectedPlanTab}` : ''
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as unknown as { route?: string; options?: Record<string, string> } | undefined
  const sameContext = tab === 'chat'
    ? store.followUpReminder ? page?.options?.reminder_id === String(store.followUpReminder.id) : (page?.options?.conversation_id || '') === (activeConversation.value?.id || '')
    : tab === 'plans' ? (page?.options?.tab || 'all') === store.selectedPlanTab : true
  if (!navigating && (page?.route !== path || !sameContext)) {
    navigating = true
    uni.redirectTo({ url: `/${path}${query}`, complete: () => { navigating = false } })
  }
}

function requestNewConversation() {
  store.newConversation()
  navigate('chat')
}

async function openConversation(id: string) {
  if (await store.openConversation(id)) navigate('chat')
}

function openFollowUp(reminder: ReminderItem) {
  store.startFollowUp(reminder)
  navigate('chat')
}

function goHome() {
  screen.value = 'landing'
  uni.redirectTo({ url: '/pages/index/index' })
}

function showProfile() {
  store.accountOpen = true
}

function handleDialogKey(event: KeyboardEvent) {
  // #ifdef H5
  if (event.key === 'Escape') { store.accountOpen = false; event.preventDefault() }
  if (event.key !== 'Tab') return
  const controls = Array.from(document.querySelectorAll<HTMLElement>('.account-dialog [tabindex="0"], .account-dialog input, .account-dialog textarea, .account-dialog a[href]')).filter((element) => element.offsetParent !== null && !element.hasAttribute('disabled'))
  if (!controls.length) return
  const first = controls[0], last = controls[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) { last.focus(); event.preventDefault() }
  else if (!event.shiftKey && document.activeElement === last) { first.focus(); event.preventDefault() }
  // #endif
}
// #ifdef H5
let previousFocus: HTMLElement | null = null
watch(() => store.accountOpen, async (open) => {
  if (open) { previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null; await nextTick(); document.querySelector<HTMLElement>('.account-dialog input, .account-dialog [tabindex="0"]')?.focus() }
  else if (previousFocus?.isConnected) previousFocus.focus()
})
// #endif
onMounted(() => { void store.initialize() })

watch(draft, () => { if (draft.value.trim()) error.value = '' })
watch(activeTab, (tab) => { if (screen.value === 'workspace' && !transferring.value) navigate(tab) })
watch(() => activeConversation.value?.id, () => { if (screen.value === 'workspace' && activeTab.value === 'chat' && !transferring.value && !store.followUpReminder) navigate('chat') })
watch([messageCount, pending, activeTab, () => activeConversation.value?.id], async () => {
  await nextTick()
  messageScrollTop.value += 100000
}, { immediate: true })
</script>

<style scoped>
.app-shell {
  --u: .039078vw;
  --font-display: 'ClearComplaint Display', 'Noto Serif SC', 'Source Han Serif SC', 'STZhongsong', 'Songti SC', serif;
  --font-ui: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  --ink: #1b1b18;
  --muted: #767674;
  --accent: #2463eb;
  --accent-deep: #1b1b18;
  --line: #e4e4df;
  --surface: #fff;
  --surface-soft: #f5f5f0;
  --surface-tint: #f0f5ff;
  --surface-hover: #f2f2ed;
  --text-strong: #1b1b18;
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
  color: var(--ink);
  font-family: var(--font-ui);
  background: #fdfdf7;
}
.landing-header { height: max(76px, calc(102 * var(--u))); padding: 0 5.8vw; display: flex; align-items: center; justify-content: space-between; box-sizing: border-box; }
.wordmark { display: flex; align-items: center; gap: 10px; font-family: var(--font-display); font-size: clamp(22px, calc(34 * var(--u)), 40px); font-weight: 600; line-height: 1.3; letter-spacing: .04em; }
.brand-mark { width: max(30px, calc(36 * var(--u))); height: max(26px, calc(36 * var(--u))); flex-shrink: 0; }
.header-actions { display: flex; align-items: center; gap: max(9px, calc(14 * var(--u))); }
.text-button { margin: 0; padding: 0 17px; border: 1px solid #d1d1ca; border-radius: 30px; background: transparent; font-size: clamp(13px, calc(18 * var(--u)), 20px); line-height: max(38px, calc(52 * var(--u))); color: var(--ink); }
.small-primary { margin: 0; padding: 0 max(16px, calc(22 * var(--u))); min-height: 38px; border-radius: 32px; font-size: clamp(14px, calc(18 * var(--u)), 20px); line-height: max(38px, calc(52 * var(--u))); background: #0b0b09; color: #fff; }
.icon-button { display: flex; align-items: center; justify-content: center; width: max(38px, calc(58 * var(--u))); height: max(38px, calc(58 * var(--u))); margin: 0; padding: 0; border-radius: 12px; background: transparent; }
.icon-button .q-icon { width: max(20px, calc(26 * var(--u))); height: max(20px, calc(26 * var(--u))); }
.icon-button:hover { background: var(--surface-hover); }
.header-menu { position: absolute; right: 5.8vw; top: max(70px, calc(84 * var(--u))); z-index: 20; min-width: 170px; padding: 7px; border: 1px solid var(--line); border-radius: 14px; background: #fff; box-shadow: 0 12px 36px #1b1b1810; animation: reveal .2s ease both; }
.header-menu button { margin: 0; min-height: 44px; padding: 12px; border-radius: 8px; text-align: left; font-size: 14px; line-height: 1.5; background: transparent; color: var(--ink); }
.header-menu button:hover { background: var(--surface-soft); }
.landing-main { padding-top: max(35px, calc(19.95vh - max(76px, calc(102 * var(--u))))); padding-bottom: 110px; }
.landing-intro { text-align: center; }
.hero-mark { width: calc(115 * var(--u)); height: calc(96 * var(--u)); margin: 0 auto calc(20 * var(--u)); animation: reveal .45s ease both; }
.landing-title { font-family: var(--font-display); font-size: clamp(40px, calc(82 * var(--u)), 92px); font-weight: 600; line-height: 1.15; letter-spacing: .025em; animation: reveal .55s ease both; }
.name-accent { border-bottom: max(2px, calc(5 * var(--u))) dashed #b8dcb9; padding-bottom: 1px; }
.intro-copy, .intro-detail { display: block; width: 29vw; max-width: 800px; min-width: 340px; margin: max(20px, calc(24 * var(--u))) auto 0; font-size: clamp(15px, calc(22 * var(--u)), 25px); font-weight: 500; color: #676762; line-height: 1.65; letter-spacing: .015em; animation: reveal .55s .1s ease both; }
.strong { color: #5d5d59; font-weight: 600; }
.intro-detail { margin-top: max(14px, calc(16 * var(--u))); animation-delay: .18s; }
.landing-composer { --composer-height: calc(222 * var(--u)); width: 32.36vw; min-width: 420px; max-width: 1050px; margin: max(40px, calc(60 * var(--u))) auto 0; animation: reveal .55s .24s ease both; }
.composer-footnote { display: flex; justify-content: space-between; align-items: center; gap: 15px; margin-top: max(13px, calc(20 * var(--u))); font-size: clamp(11px, calc(14 * var(--u)), 16px); color: var(--muted); }
.composer-footnote > view { display: flex; align-items: center; gap: 7px; }
.composer-footnote .q-icon { width: 17px; height: 17px; opacity: .6; }
.landing-daily-card { display: flex; align-items: center; justify-content: space-between; gap: 20px; width: 100%; margin-top: max(14px, calc(20 * var(--u))); padding: max(16px, calc(22 * var(--u))) max(18px, calc(24 * var(--u))); border: 1px solid var(--line); border-radius: 18px; box-sizing: border-box; background: var(--surface); color: var(--ink); text-align: left; }
.landing-daily-card:hover { background: var(--surface-soft); }
.landing-daily-copy, .landing-daily-detail { display: block; }
.landing-daily-title { font-size: clamp(14px, calc(18 * var(--u)), 18px); font-weight: 600; line-height: 1.5; }
.landing-daily-detail { margin-top: 5px; color: var(--muted); font-size: clamp(11px, calc(14 * var(--u)), 14px); line-height: 1.7; }
.landing-daily-action { display: flex; align-items: center; flex-shrink: 0; gap: 6px; color: var(--accent); font-size: clamp(11px, calc(14 * var(--u)), 14px); line-height: 1.5; }
.landing-daily-action .q-icon { width: 16px; height: 16px; }
.landing-footer { position: absolute; right: 5.8vw; bottom: 28px; left: 5.8vw; display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); }
.workspace-shell { display: flex; }
.sidebar { position: fixed; z-index: 30; inset: 0 auto 0 0; width: max(60px, 4.65vw); display: flex; flex-direction: column; align-items: center; border-right: 1px solid var(--line); background: #fdfdf7; box-sizing: border-box; transition: width .22s ease, box-shadow .22s ease; }
.sidebar-expanded { width: 248px; align-items: stretch; box-shadow: 20px 0 45px #1b1b1808; }
.sidebar-collapse { position: absolute; top: 3.1vh; width: max(28px, calc(40 * var(--u))); height: max(28px, calc(40 * var(--u))); margin: 0; opacity: .42; }
.sidebar-collapse:hover { opacity: 1; }
.sidebar-expanded .sidebar-collapse { position: absolute; top: 19px; right: 12px; margin: 0; }
.sidebar-logo { display: flex; align-items: center; gap: 9px; min-height: 64px; margin: 8px 54px 0 17px; padding: 0; background: transparent; }
.sidebar-brand { font-size: 22px; font-weight: 600; }
.sidebar-nav { width: calc(100% - 22px); margin-top: 8.6vh; padding-top: calc(24 * var(--u)); border-top: 1px dashed var(--line); display: flex; flex-direction: column; align-items: center; gap: max(3px, calc(6 * var(--u))); }
.sidebar-expanded .sidebar-nav { width: auto; margin: 15px 12px 0; align-items: stretch; }
.nav-item { position: relative; display: flex; align-items: center; justify-content: center; flex-shrink: 0; gap: 13px; width: max(32px, calc(60 * var(--u))); height: max(32px, calc(60 * var(--u))); margin: 0; padding: 0; border-radius: 50%; background: transparent; color: var(--ink); font-size: 14px; line-height: 1.4; }
.nav-item .q-icon { width: max(21px, calc(27 * var(--u))); height: max(21px, calc(27 * var(--u))); }
.nav-item-active { background: var(--surface-tint); }
.nav-item-active .q-icon { filter: invert(29%) sepia(96%) saturate(3590%) hue-rotate(218deg) brightness(98%) contrast(88%); }
.nav-item:hover { background: var(--surface-hover); }
.nav-item-active:hover { background: #e8efff; }
.sidebar-expanded .nav-item { width: 100%; height: 46px; padding: 0 13px; justify-content: flex-start; border-radius: 12px; box-sizing: border-box; }
.nav-tooltip { position: absolute; z-index: 40; left: calc(100% + 12px); padding: 7px 11px; border: 1px solid var(--line); border-radius: 7px; background: #fff; color: var(--ink); font-size: 12px; white-space: nowrap; opacity: 0; visibility: hidden; transform: translateX(-4px); transition: opacity .15s, transform .15s; pointer-events: none; }
.nav-item:hover .nav-tooltip, .nav-item:focus-visible .nav-tooltip { opacity: 1; visibility: visible; transform: none; }
.recent-conversations { min-height: 0; overflow-y: auto; padding: 26px 13px 12px; }
.recent-heading { display: block; padding: 0 10px 11px; font-size: 11px; color: var(--muted); }
.recent-empty { display: block; padding: 10px; font-size: 12px; color: var(--muted); }
.recent-conversation { display: flex; align-items: center; gap: 9px; width: 100%; padding: 10px; margin: 0 0 3px; border-radius: 9px; background: transparent; color: var(--ink); text-align: left; line-height: 1.5; }
.recent-conversation:hover, .recent-current { background: var(--surface-soft); }
.recent-conversation > view { flex: 1; min-width: 0; }
.recent-conversation .q-icon { width: 17px; height: 17px; opacity: .55; }
.recent-title { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.recent-kind { display: block; font-size: 10px; color: var(--muted); margin-top: 3px; }
.sidebar-bottom { display: flex; flex-direction: column; align-items: center; gap: max(12px, calc(28 * var(--u))); width: calc(100% - 22px); margin-top: auto; padding: 20px 0 max(17px, calc(24 * var(--u))); }
.sidebar-person { display: flex; align-items: center; gap: 11px; min-height: 44px; padding: 0; margin: 0; background: transparent; line-height: 1.5; }
.patient-avatar { display: flex; align-items: center; justify-content: center; width: max(38px, calc(52 * var(--u))); height: max(38px, calc(52 * var(--u))); }
.patient-avatar .q-icon { width: max(22px, calc(28 * var(--u))); height: max(22px, calc(28 * var(--u))); }
.patient-name, .patient-description { display: block; text-align: left; font-size: 14px; }
.patient-description { font-size: 11px; color: var(--muted); margin-top: 3px; }
.sidebar-expanded .sidebar-bottom { align-items: stretch; margin-left: 12px; }
.sidebar-expanded .sidebar-person { padding: 10px 0 0; border-top: 1px dashed var(--line); }
.workspace-main { width: calc(100% - max(60px, 4.65vw)); min-width: 0; margin-left: max(60px, 4.65vw); }
.workspace-header { display: flex; align-items: center; justify-content: space-between; gap: 15px; height: 76px; padding: 0 4vw; border-bottom: 1px solid var(--line); }
.breadcrumb { display: flex; align-items: center; gap: 12px; min-width: 0; font-size: 14px; }
.breadcrumb-brand { font-weight: 600; }
.slash { color: var(--muted); }
.workspace-actions { display: flex; align-items: center; gap: 14px; }
.mobile-history-button, .mobile-nav, .chat-mobile-toolbar { display: none; }
.workspace-pane { animation: reveal .28s ease both; }
.history-menu { position: absolute; right: 20px; top: 65px; z-index: 20; width: 270px; max-height: 55vh; overflow: auto; padding: 13px; border: 1px solid var(--line); border-radius: 16px; background: #fff; box-shadow: 0 12px 32px #1b1b1810; }
.history-new { padding: 10px; font-size: 13px; color: var(--accent); background: var(--surface-tint); }
.empty-chat { box-sizing: border-box; min-height: 100vh; min-height: 100dvh; padding: 19.95vh 24px 80px; text-align: center; }
.chat-welcome { display: flex; flex-direction: column; align-items: center; }
.welcome-mark { display: block; width: calc(115 * var(--u)); height: calc(96 * var(--u)); animation: reveal .45s ease both; }
.welcome-title { margin-top: calc(20 * var(--u)); font-family: var(--font-display); font-size: clamp(30px, calc(64 * var(--u)), 80px); font-weight: 600; line-height: 1.25; letter-spacing: .015em; animation: reveal .5s .07s ease both; }
.chat-entry-composer { --composer-height: calc(187 * var(--u)); width: 38.22vw; max-width: 1220px; min-width: 470px; margin: calc(32 * var(--u)) auto 0; text-align: left; animation: reveal .5s .14s ease both; }
.record-connector { display: flex; align-items: flex-start; justify-content: space-between; width: 100%; height: max(40px, calc(80 * var(--u))); margin: 0 0 calc(-27 * var(--u)); padding: max(10px, calc(17 * var(--u))) max(12px, calc(20 * var(--u))); border: 1px solid var(--line); border-bottom: 0; border-radius: max(16px, calc(24 * var(--u))) max(16px, calc(24 * var(--u))) 0 0; box-sizing: border-box; background: var(--surface-soft); color: var(--ink); text-align: left; font-size: clamp(11px, calc(20 * var(--u)), 24px); line-height: 1.4; }
.record-connector .q-icon { width: max(18px, calc(24 * var(--u))); height: max(18px, calc(24 * var(--u))); }
.record-connector:hover { background: #f0f0eb; }
.chat-entry-composer :deep(.composer-wrap) { position: relative; z-index: 1; }
.medical-note { display: block; margin-top: max(9px, calc(14 * var(--u))); color: var(--muted); font-size: clamp(10px, calc(14 * var(--u)), 16px); line-height: 1.6; text-align: center; }
.quick-start { margin-top: max(18px, calc(36 * var(--u))); animation: reveal .5s .22s ease both; }
.prompt-list { display: flex; justify-content: center; flex-wrap: wrap; gap: max(7px, calc(12 * var(--u))); }
.prompt-chip { margin: 0; padding: max(9px, calc(16 * var(--u))) max(12px, calc(24 * var(--u))); border-radius: max(9px, calc(12 * var(--u))); background: var(--surface-soft); color: var(--ink); font-size: clamp(11px, calc(20 * var(--u)), 24px); line-height: 1.3; }
.prompt-chip:hover { background: #eaeae4; }
.conversation-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(300px, 24.1vw); gap: max(30px, calc(70 * var(--u))); height: 100vh; height: 100dvh; padding: 5.5vh max(20px, calc(32 * var(--u))) 3.8vh max(30px, calc(120 * var(--u))); box-sizing: border-box; }
.conversation-column { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.emergency-note { display: flex; align-items: center; gap: 9px; padding: max(10px, calc(15 * var(--u))) 0 max(25px, calc(35 * var(--u))); font-size: clamp(12px, calc(21 * var(--u)), 23px); line-height: 1.6; font-weight: 500; }
.emergency-note .q-icon { width: 17px; height: 17px; opacity: .55; }
.messages-scroll { flex: 1; height: 0; min-height: 0; }
.messages-list { padding: 0 3px 25px; }
.message { margin-bottom: max(28px, calc(48 * var(--u))); animation: reveal .32s ease both; }
.message-user { display: flex; justify-content: flex-end; }
.message-bubble { color: var(--ink); font-size: clamp(15px, calc(24 * var(--u)), 28px); line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.message-user .message-bubble { max-width: 80%; width: fit-content; padding: max(12px, calc(24 * var(--u))); border-radius: max(18px, calc(24 * var(--u))) 4px max(18px, calc(24 * var(--u))) max(18px, calc(24 * var(--u))); background: var(--surface-tint); }
.assistant-identity { display: flex; align-items: center; gap: 10px; margin-bottom: 15px; font-size: clamp(14px, calc(20 * var(--u)), 23px); font-weight: 500; }
.assistant-identity image { width: max(24px, calc(36 * var(--u))); height: max(21px, calc(30 * var(--u))); }
.message-assistant .message-bubble { padding-left: max(34px, calc(46 * var(--u))); }
.bubble-in-flight { visibility: hidden; }
.pending-message { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: clamp(13px, calc(20 * var(--u)), 22px); padding: 8px 0; }
.loading-dots { display: flex; gap: 3px; }
.loading-dots text { width: 4px; height: 4px; border-radius: 50%; background: var(--accent); animation: pulse 1.1s ease-in-out infinite; }
.loading-dots text:nth-child(2) { animation-delay: .14s; }
.loading-dots text:nth-child(3) { animation-delay: .28s; }
.message-end { height: 1px; }
.conversation-composer { --composer-height: calc(173 * var(--u)); padding-top: 18px; flex-shrink: 0; }
.conversation-tools { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 4px 15px; margin-bottom: max(10px, calc(20 * var(--u))); font-size: clamp(11px, calc(16 * var(--u)), 18px); color: var(--muted); }
.conversation-daily-link { display: inline-flex; align-items: center; flex-shrink: 0; min-height: 32px; margin: 0; padding: 5px 0; background: transparent; color: var(--accent); font-size: inherit; line-height: 1.5; }
.context-column {
  --muted: #657064;
  --glass-surface: rgba(255, 255, 255, .42);
  --glass-stroke: rgba(255, 255, 255, .9);
  --glass-rule: rgba(151, 172, 164, .22);
  align-self: start;
  min-height: 0;
  max-height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #c4cfc9 transparent;
  border: 1px solid rgba(255, 255, 255, .96);
  border-radius: max(26px, calc(42 * var(--u)));
  background:
    radial-gradient(ellipse at 0% 0%, rgba(213, 237, 250, .42), transparent 62%),
    radial-gradient(ellipse at 100% 85%, rgba(236, 245, 216, .3), transparent 68%),
    linear-gradient(135deg, rgba(255, 255, 255, .76), rgba(248, 252, 242, .64));
  -webkit-backdrop-filter: blur(20px) saturate(115%);
  backdrop-filter: blur(20px) saturate(115%);
  box-shadow: 0 12px 32px rgba(80, 108, 146, .13), 0 2px 6px rgba(80, 108, 146, .04), inset 0 1px 0 #fff;
  animation: reveal .4s .1s ease both;
}
.account-overlay { position: fixed; z-index: 100; inset: 0; display: flex; justify-content: flex-end; padding: 24px; box-sizing: border-box; background: rgba(27, 33, 28, .13); }
.context-heading { position: sticky; top: 0; z-index: 2; display: flex; padding: 17px 18px 9px; background: rgba(250,253,248,.85); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); }
.context-heading text { display: block; padding: 9px 13px; min-height: 44px; box-sizing: border-box; border-radius: 24px; background: rgba(255,255,255,.8); color: #293c31; box-shadow: inset 0 1px 0 #fff; font-size: 13px; line-height: 1.5; }
.account-dialog { width: min(430px, 100%); height: 100%; align-self: stretch; }
.account-close { position: sticky; z-index: 5; top: 8px; margin: 8px 8px 0 auto; width: 40px; height: 40px; }
@media (prefers-reduced-transparency: reduce), (prefers-contrast: more) {
  .context-column { --glass-surface: #fff; --glass-stroke: #dce3dc; --glass-rule: #dce3dc; background: #f8fbf5; -webkit-backdrop-filter: none; backdrop-filter: none; }
}
.follow-up-context { display: flex; gap: 12px; padding: 15px; margin-bottom: 25px; border: 1px solid var(--line); border-radius: 14px; background: #fff; font-size: 13px; line-height: 1.7; }
.follow-up-context > view { min-width: 0; }
.follow-up-context text { display: block; }
.context-title { margin-bottom: 5px; font-weight: 600; }
.context-link { padding: 7px 0; margin: 0; color: var(--accent); background: transparent; text-align: left; font-size: 12px; line-height: 1.5; }
.completed-conversation { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; padding: 18px; border: 1px solid var(--line); border-radius: 16px; background: #fff; font-size: 14px; line-height: 1.6; }
.completed-conversation button { min-height: 38px; padding: 8px 14px; margin: 0; border-radius: 22px; color: #fff; background: var(--accent); font-size: 13px; line-height: 1.5; }
button { transition: background-color .16s ease, color .16s ease, transform .16s ease; }
button:active { transform: scale(.97); }
@keyframes reveal { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes pulse { 0%, 70%, 100% { opacity: .3; transform: translateY(0); } 35% { opacity: 1; transform: translateY(-3px); } }
@media (max-width: 1100px) {
  .conversation-layout { grid-template-columns: minmax(0, 1fr) 290px; gap: 24px; padding-left: 28px; padding-right: 18px; }
  .conversation-tools > text { max-width: 50%; }
}
@media (max-width: 820px) {
  .conversation-layout { grid-template-columns: minmax(0, 1fr); height: auto; min-height: 100dvh; gap: 24px; padding: 28px 26px 38px; }
  .conversation-column { min-height: calc(100dvh - 66px); }
  .messages-scroll { min-height: 280px; }
  .context-column { max-height: 480px; border-radius: 20px; }
  .landing-composer { min-width: 0; width: 64vw; --composer-height: 170px; }
  .chat-entry-composer { min-width: 0; width: 70vw; --composer-height: 160px; }
  .landing-title { font-size: 42px; }
  .landing-main { padding-top: 10vh; }
  .intro-copy, .intro-detail { width: 62vw; min-width: 0; }
  .welcome-title { font-size: 36px; }
  .hero-mark, .welcome-mark { width: 84px; height: 70px; }
  .chat-entry-composer { margin-top: 30px; }
  .record-connector { height: 61px; margin-bottom: -20px; }
  .conversation-composer { --composer-height: 160px; }
}
@media (max-width: 600px) {
  .landing-header { height: 80px; padding: 0 22px; }
  .wordmark { font-size: 20px; }
  .wordmark .brand-mark { width: 28px; height: 25px; }
  .header-actions { gap: 5px; }
  .archive-link { display: none; }
  .small-primary { min-height: 36px; padding: 0 14px; font-size: 12px; line-height: 36px; }
  .icon-button { width: 34px; height: 36px; }
  .landing-main { padding-top: 8vh; padding-bottom: 110px; }
  .hero-mark { margin-bottom: 20px; }
  .landing-title { padding: 0 20px; font-size: clamp(30px, 8.6vw, 38px); line-height: 1.3; letter-spacing: .01em; }
  .intro-copy, .intro-detail { width: calc(100% - 64px); font-size: 14px; }
  .intro-detail { margin-top: 16px; }
  .landing-composer { width: calc(100% - 40px); margin-top: 40px; --composer-height: 185px; }
  .composer-footnote { font-size: 10px; }
  .landing-daily-card { gap: 12px; padding: 14px 16px; }
  .landing-daily-action { gap: 3px; }
  .landing-footer { left: 22px; right: 22px; bottom: 22px; font-size: 10px; }
  .sidebar { display: none; }
  .chat-mobile-toolbar { display: flex; height: 60px; align-items: center; justify-content: space-between; gap: 10px; padding: 0 20px; }
  .chat-mobile-toolbar > view { display: flex; gap: 4px; }
  .mobile-home { display: flex; align-items: center; gap: 6px; margin: 0; padding: 0; background: transparent; font-family: var(--font-display); font-size: 19px; font-weight: 600; line-height: 1.5; }
  .mobile-home image { width: 28px; height: 24px; }
  .workspace-main { width: 100%; margin-left: 0; padding-bottom: calc(67px + env(safe-area-inset-bottom)); }
  .workspace-header { height: 68px; padding: 0 20px; }
  .mobile-history-button { display: flex; }
  .empty-chat { min-height: calc(100dvh - 127px); padding: 8vh 20px 55px; }
  .welcome-title { margin-top: 20px; max-width: 100%; font-size: clamp(24px, 7.1vw, 32px); line-height: 1.3; letter-spacing: .01em; }
  .hero-mark, .welcome-mark { width: 78px; height: 65px; }
  .chat-entry-composer { width: 100%; margin-top: 32px; --composer-height: 172px; }
  .record-connector { font-size: 13px; }
  .prompt-list { gap: 7px; }
  .prompt-chip { font-size: 12px; padding: 11px 13px; }
  .medical-note { font-size: 10px; }
  .mobile-nav { position: fixed; z-index: 35; bottom: 0; left: 0; right: 0; display: flex; justify-content: space-around; padding: 8px 12px calc(8px + env(safe-area-inset-bottom)); border-top: 1px solid var(--line); background: #fdfdf7; }
  .mobile-nav button { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; min-height: 45px; padding: 5px 7px; margin: 0; background: transparent; border-radius: 12px; font-size: 10px; line-height: 1.3; color: var(--muted); }
  .mobile-nav .q-icon { width: 21px; height: 21px; opacity: .65; }
  .mobile-nav .mobile-tab-active { color: var(--accent); background: var(--surface-tint); }
  .conversation-layout { padding: 22px 20px 24px; min-height: calc(100dvh - 127px); }
  .conversation-column { min-height: calc(100dvh - 173px); }
  .emergency-note { padding-top: 2px; padding-bottom: 24px; font-size: 12px; }
  .message-bubble { font-size: 15px; }
  .message-assistant .message-bubble { padding-left: 0; }
  .assistant-identity { margin-bottom: 10px; }
  .conversation-tools { font-size: 10px; }
  .conversation-daily-link { min-height: 44px; padding: 0; }
  .save-button { font-size: 12px; }
  .context-column { max-height: none; }
}
</style>
