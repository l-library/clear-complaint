<template>
  <view class="app-shell" :class="{ 'workspace-shell': screen === 'workspace', 'is-transitioning': transferring }">
    <template v-if="screen === 'landing'">
      <view class="landing-header">
        <view class="wordmark">
          <image src="/static/brand.svg" class="brand-mark" />
          <text>清诉</text><text class="brand-en">ClearComplaint</text>
        </view>
        <view class="header-actions">
          <button class="text-button archive-link" @click="navigate('archive')">健康档案</button>
          <button class="small-primary" @click="navigate('chat')">开始体验</button>
          <button class="icon-button" aria-label="打开导航菜单" @click="menuOpen = !menuOpen"><QIcon :name="menuOpen ? 'close' : 'menu'" /></button>
        </view>
        <view v-if="menuOpen" class="header-menu">
          <button @click="navigate('chat'); menuOpen = false">AI 对话</button>
          <button @click="navigate('archive'); menuOpen = false">健康档案</button>
          <button @click="navigate('plans'); menuOpen = false">健康计划</button>
        </view>
      </view>
      <view class="landing-main">
        <view class="landing-intro">
          <view class="landing-title">
            <text v-for="(character, index) in landingLead" :key="index" class="reveal-character" :style="{ animationDelay: `${index * 45}ms` }">{{ character }}</text>
            <text class="name-accent">
              <text v-for="(character, index) in brandCharacters" :key="index" class="reveal-character" :style="{ animationDelay: `${(index + landingLead.length) * 45}ms` }">{{ character }}</text>
            </text>
            <text class="reveal-character" style="animation-delay: 315ms">。</text>
          </view>
          <text class="intro-copy">描述你的不适，清诉会帮你整理症状与关键线索，<text class="strong">让下一次就医沟通更清晰。</text></text>
          <text class="intro-detail">聊聊当下的感受，留住每一次变化。对话、健康档案和未来的安排，在这里连在一起。</text>
        </view>
        <view class="landing-composer">
          <QComposer v-model="draft" label="今天有什么想告诉我？" :error="error" :pending="pending" @send="handleSend" />
          <view class="composer-footnote">
            <text>无需注册 · 匿名体验</text>
            <view><QIcon name="shield" /><text>仅供健康信息整理</text></view>
          </view>
        </view>
      </view>
      <view class="landing-footer"><text>预设演示资料 · {{ store.profile.name }} · {{ store.profile.age }} 岁</text><text>交互演示 · 数据均为模拟</text></view>
    </template>

    <template v-else>
      <view class="sidebar" :class="{ 'sidebar-expanded': sidebarExpanded }">
        <button class="sidebar-logo" aria-label="返回首页" @click="goHome">
          <image src="/static/brand.svg" class="brand-mark" /><text v-if="sidebarExpanded" class="sidebar-brand">清诉</text>
        </button>
        <button class="sidebar-collapse icon-button" :aria-label="sidebarExpanded ? '收起导航' : '展开导航'" :aria-expanded="sidebarExpanded" @click="sidebarExpanded = !sidebarExpanded"><QIcon name="collapse" /></button>
        <view class="sidebar-nav">
          <button class="nav-item" :class="{ 'nav-item-active': activeTab === 'chat' }" :aria-pressed="activeTab === 'chat'" aria-label="AI 对话" @click="navigate('chat')">
            <QIcon name="chat" /><text v-if="sidebarExpanded">AI 对话</text><text v-else class="nav-tooltip">AI 对话</text>
          </button>
          <button class="nav-item" :class="{ 'nav-item-active': activeTab === 'archive' }" :aria-pressed="activeTab === 'archive'" aria-label="健康档案" @click="navigate('archive')">
            <QIcon name="file" /><text v-if="sidebarExpanded">健康档案</text><text v-else class="nav-tooltip">健康档案</text>
          </button>
          <button class="nav-item" :class="{ 'nav-item-active': activeTab === 'plans' }" :aria-pressed="activeTab === 'plans'" aria-label="健康计划" @click="navigate('plans')">
            <QIcon name="calendar" /><text v-if="sidebarExpanded">健康计划</text><text v-else class="nav-tooltip">健康计划</text>
          </button>
        </view>
        <view v-if="sidebarExpanded" class="recent-conversations">
          <text class="recent-heading">最近对话</text>
          <text v-if="!recentConversations.length" class="recent-empty">从一次新的问诊开始</text>
          <button v-for="item in recentConversations.slice(0, 8)" :key="item.id" class="recent-conversation" :class="{ 'recent-current': item.id === activeConversation?.id }" :aria-label="`${item.type === 'follow_up' ? '随访' : '问诊'}：${item.title}`" @click="openConversation(item.id)">
            <QIcon :name="item.type === 'follow_up' ? 'calendar' : 'chat'" /><view><text class="recent-title">{{ item.title }}</text><text class="recent-kind">{{ item.type === 'follow_up' ? '随访对话' : '症状问诊' }}</text></view>
          </button>
        </view>
        <view class="sidebar-bottom">
          <button class="nav-item" aria-label="新建问诊" @click="requestNewConversation"><QIcon name="plus" /><text v-if="sidebarExpanded">新建问诊</text><text v-else class="nav-tooltip">新建问诊</text></button>
          <button class="sidebar-person" aria-label="个人中心与演示资料" @click="showProfile"><view class="patient-avatar"><QIcon name="user" /></view><view v-if="sidebarExpanded"><text class="patient-name">{{ store.profile.name }}</text><text class="patient-description">个人中心 · 演示资料</text></view></button>
        </view>
      </view>
      <view class="workspace-main">
        <view class="workspace-header">
          <view class="breadcrumb"><text class="breadcrumb-brand">清诉</text><text class="slash">/</text><text>{{ pageTitle }}</text><text v-if="activeTab === 'chat' && activeConversation" class="mode-tag" :class="{ 'follow-up-mode': isFollowUp }">{{ isFollowUp ? '随访模式' : '问诊模式' }}</text></view>
          <view class="workspace-actions"><text class="demo-tag">本地交互演示</text><button class="icon-button mobile-history-button" aria-label="最近对话" :aria-expanded="historyOpen" @click="historyOpen = !historyOpen"><QIcon name="clock" /></button><button class="icon-button" aria-label="返回首页" @click="goHome"><QIcon name="home" /></button></view>
        </view>
        <view v-if="activeTab === 'chat' && error.startsWith('本地保存失败')" class="storage-notice" role="alert"><text>{{ error }} 当前内容仍在本次页面中。</text><button @click="store.persist()">重试本地保存</button></view>
        <view v-if="historyOpen" class="history-menu"><text class="recent-heading">最近对话</text><button v-for="item in recentConversations" :key="item.id" class="recent-conversation" @click="openConversation(item.id); historyOpen = false"><QIcon :name="item.type === 'follow_up' ? 'calendar' : 'chat'" /><view><text class="recent-title">{{ item.title }}</text><text class="recent-kind">{{ item.type === 'follow_up' ? '随访' : '问诊' }}</text></view></button><button class="history-new" @click="requestNewConversation(); historyOpen = false">＋ 新建问诊</button></view>
        <view class="workspace-content">
          <view v-show="activeTab === 'archive'" class="workspace-pane"><QHealthArchive @open-conversation="openConversation" @open-plans="navigate('plans')" /></view>
          <view v-show="activeTab === 'plans'" class="workspace-pane"><QHealthPlans @open-conversation="openConversation" /></view>
          <view v-if="activeTab === 'chat' && !messages.length" class="empty-chat">
            <view class="chat-welcome">
              <image src="/static/brand.svg" class="welcome-mark" />
              <view class="welcome-title">
                <text v-for="(character, index) in welcomeLead" :key="index" class="reveal-character" :style="{ animationDelay: `${index * 32}ms` }">{{ character }}</text>
                <text class="welcome-title-end">
                  <text v-for="(character, index) in welcomeEnding" :key="index" class="reveal-character" :style="{ animationDelay: `${(index + welcomeLead.length) * 32}ms` }">{{ character }}</text>
                </text>
              </view>
              <text class="welcome-description">哪里不舒服，持续了多久，最近有什么变化？<text class="welcome-break">用自己的话说就好，清诉会陪你一起梳理。</text></text>
            </view>
            <view class="chat-entry-composer">
              <QComposer v-model="draft" compact :error="error" :pending="pending" @send="handleSend" />
              <text class="medical-note">模拟问诊演示，内容仅供信息整理，不构成诊断。</text>
            </view>
            <view class="quick-start"><view class="prompt-list"><button v-for="prompt in prompts" :key="prompt.title" class="prompt-chip" @click="choosePrompt(prompt.content)"><text>{{ prompt.title }}</text></button></view></view>
            <view class="entry-assurances"><view><QIcon name="shield" /><text>慢慢说清楚</text></view><view><QIcon name="calendar" /><text>衔接后续随访</text></view><view><QIcon name="file" /><text>留存健康记录</text></view></view>
          </view>
          <view v-else-if="activeTab === 'chat'" class="conversation-layout">
            <view class="conversation-column">
              <view v-if="isFollowUp && followUpContext" class="follow-up-context"><QIcon name="calendar" /><view><text class="context-title">{{ currentEpisode?.title || '健康情况回顾' }}</text><text>{{ followUpContext.goal }}</text><button class="context-link" @click="navigate('plans')">查看关联健康计划</button></view></view>
              <view v-else class="emergency-note"><QIcon name="info" /><text>如有紧急情况，请立即联系当地急救服务。</text></view>
              <scroll-view class="messages-scroll" scroll-y :scroll-top="messageScrollTop" :scroll-with-animation="false">
                <view class="messages-list">
                  <view v-for="message in messages" :id="`message-${message.id}`" :key="message.id" class="message" :class="`message-${message.role}`">
                    <view v-if="message.role === 'assistant'" class="assistant-identity"><image src="/static/brand.svg" /><text>清诉</text></view>
                    <view :id="`bubble-${message.id}`" class="message-bubble" :class="{ 'bubble-in-flight': message.id === flyingMessageId }"><text>{{ message.content }}</text></view>
                  </view>
                  <view v-if="pending" id="message-pending" class="pending-message" role="status"><view class="loading-dots"><text /><text /><text /></view><text>{{ isFollowUp ? '正在整理这次随访…' : '正在整理你的描述…' }}</text></view>
                  <view id="message-end" class="message-end" />
                </view>
              </scroll-view>
              <view class="conversation-composer">
                <view class="conversation-tools"><text>{{ isFollowUp ? '核对后归档，更新本次随访任务' : '对话自动留存，核对后可归档为健康记录' }}</text><button class="save-button" :disabled="pending || saved || !hasUserMessage" @click="saveCurrentConversation"><QIcon :name="saved ? 'check' : 'save'" /><text>{{ saved ? '已归档' : isFollowUp ? '归档并完成随访' : '核对并归档' }}</text></button></view>
                <view v-if="isCompletedFollowUp" class="completed-conversation"><QIcon name="check" /><text>本次随访已完成，记录已归档。出现新的不适可以新建问诊。</text><button @click="requestNewConversation">新建问诊</button></view>
                <QComposer v-else v-model="draft" compact :context-label="isFollowUp ? '随访回复' : '问诊交流'" :placeholder="isFollowUp ? '这段时间有什么变化？' : '继续补充你的情况…'" :pending="pending" :error="error" @send="handleSend" />
                <text class="medical-note">演示回复不调用真实 AI。记录保存在当前设备，不作为诊断或用药依据。</text>
              </view>
            </view>
            <view class="context-column"><QConversationContext @open-record="openArchivedRecord" @open-plans="navigate('plans')" /></view>
          </view>
        </view>
      </view>
      <view class="mobile-nav" aria-label="主要导航">
        <button v-for="tab in navigationTabs" :key="tab.id" :class="{ 'mobile-tab-active': activeTab === tab.id }" :aria-pressed="activeTab === tab.id" @click="navigate(tab.id)"><QIcon :name="tab.icon" /><text>{{ tab.title }}</text></button>
      </view>
    </template>
    <QMessageTransition ref="messageTransition" @complete="finishTransfer" />
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import QIcon from '@/components/QIcon.vue'
import QComposer from '@/components/QComposer.vue'
import QHealthArchive from '@/components/QHealthArchive.vue'
import QHealthPlans from '@/components/QHealthPlans.vue'
import QConversationContext from '@/components/QConversationContext.vue'
import QMessageTransition from '@/components/QMessageTransition.vue'
import { useConsultationStore } from '@/stores/consultation'
import type { FollowUpPlan, WorkspaceTab } from '@/types/consultation'

const store = useConsultationStore()
const { screen, activeTab, draft, messages, pending, error, saved, activeConversation, currentEpisode, recentConversations, plans, selectedRecordId } = storeToRefs(store)
const menuOpen = ref(false)
const sidebarExpanded = ref(true)
const historyOpen = ref(false)
const messageScrollTop = ref(0)
const messageCount = computed(() => messages.value.length)
const isFollowUp = computed(() => activeConversation.value?.type === 'follow_up')
const hasUserMessage = computed(() => messages.value.some((message) => message.role === 'user'))
const isCompletedFollowUp = computed(() => isFollowUp.value && activeConversation.value?.status === 'completed')
const followUpContext = computed(() => plans.value.find((plan): plan is FollowUpPlan => plan.type === 'follow_up' && plan.id === activeConversation.value?.followUpPlanId))
const pageTitle = computed(() => activeTab.value === 'archive' ? '健康档案' : activeTab.value === 'plans' ? '健康计划' : activeConversation.value?.title || 'AI 对话')
const navigationTabs: { id: WorkspaceTab; title: string; icon: string }[] = [
  { id: 'chat', title: 'AI 对话', icon: 'chat' },
  { id: 'archive', title: '健康档案', icon: 'file' },
  { id: 'plans', title: '健康计划', icon: 'calendar' },
]
const landingLead = Array.from('你好，我是')
const brandCharacters = Array.from('清诉')
const welcomeLead = Array.from('从你的感受，')
const welcomeEnding = Array.from('开始聊聊。')
interface ElementRect { left: number; top: number; width: number; height: number }
const messageTransition = ref<InstanceType<typeof QMessageTransition> | null>(null)
const transferring = ref(false)
const flyingMessageId = ref('')
const prompts = [
  { title: '整理我的症状', icon: 'heart', content: '最近三天偶尔头晕，想记录一下发生的时间和伴随的不适。' },
  { title: '记录身体变化', icon: 'heart', content: '我想记录这几天身体的变化，方便下次就医时回顾。' },
  { title: '准备就医沟通', icon: 'file', content: '我想把最近不舒服的情况整理一下，方便去医院时告诉医生。' },
  { title: '了解检验报告', icon: 'file', content: '我想整理检验报告中不太理解的内容，准备下次就医时向医生询问。' },
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
  if (screen.value === 'landing') {
    store.sendMessage()
    if (!error.value) navigate('chat')
    return
  }
  const shouldAnimate = messages.value.length === 0
  if (!draft.value.trim() || !shouldAnimate) {
    store.sendMessage()
    return
  }
  const text = draft.value.trim()
  const originSelector = '.chat-entry-composer .composer'
  transferring.value = true
  const origin = await measure(originSelector)
  store.sendMessage()
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
}

function choosePrompt(content: string) {
  draft.value = content
  error.value = ''
}

let navigating = false
function navigate(tab: WorkspaceTab) {
  store.openWorkspace(tab)
  const path = tab === 'chat' ? 'pages/chat/index' : tab === 'archive' ? 'pages/health-records/index' : 'pages/health-plans/index'
  const query = tab === 'chat' && activeConversation.value
    ? `?conversation_id=${encodeURIComponent(activeConversation.value.id)}`
    : tab === 'archive' && selectedRecordId.value
      ? `?record_id=${encodeURIComponent(selectedRecordId.value)}` : ''
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as unknown as { route?: string; options?: Record<string, string> } | undefined
  const sameContext = tab === 'chat'
    ? (page?.options?.conversation_id || '') === (activeConversation.value?.id || '')
    : tab === 'archive' ? (page?.options?.record_id || '') === selectedRecordId.value : true
  if (!navigating && (page?.route !== path || !sameContext)) {
    navigating = true
    uni.redirectTo({ url: `/${path}${query}`, complete: () => { navigating = false } })
  }
}

function requestNewConversation() {
  store.newConversation()
  navigate('chat')
}

function openConversation(id: string) {
  if (store.openConversation(id)) navigate('chat')
}

function openArchivedRecord(id: string) {
  const record = store.records.find((item) => item.id === id)
  if (record) { store.openRecord(record); navigate('archive') }
}

function saveCurrentConversation() {
  uni.showModal({
    title: isFollowUp.value ? '核对并完成本次随访' : '核对并归档咨询记录',
    content: '请确认当前对话记录无误。保存的是本地演示摘要，不会将 AI 推测记为医生确诊。',
    confirmText: '确认归档',
    cancelText: '继续核对',
    success: (result) => { if (result.confirm) store.saveConversation() },
  })
}

function goHome() {
  screen.value = 'landing'
  uni.redirectTo({ url: '/pages/index/index' })
}

function showProfile() {
  uni.showModal({ title: '个人中心', content: `${store.profile.name} · ${store.profile.age} 岁\n${store.profile.description}\n当前为本机演示，无真实账号或云端同步。`, showCancel: false })
}

watch(draft, () => { if (draft.value.trim()) error.value = '' })
watch(activeTab, (tab) => { if (screen.value === 'workspace') navigate(tab) })
watch(selectedRecordId, () => { if (screen.value === 'workspace' && activeTab.value === 'archive') navigate('archive') })
watch([messageCount, pending, activeTab, () => activeConversation.value?.id], async () => {
  await nextTick()
  messageScrollTop.value += 100000
}, { immediate: true })
</script>

<style scoped>
.app-shell {
  --u: clamp(.5px, .03937vw, 1.5px);
  --ink: #293653;
  --muted: #5c6e8b;
  --accent: #347be5;
  --accent-deep: #293958;
  --line: #dce5f2;
  --surface: #ffffff;
  --surface-soft: #edf4ff;
  --surface-tint: #e1edff;
  --surface-hover: #e6efff;
  --text-strong: #30466c;
  --state-muted: #8a99b2;
  --chart-before: #b0bed5;
  --chart-after: #497fd4;
  position: relative;
  min-height: 100vh;
  color: var(--ink);
  background:
    radial-gradient(ellipse 56% 48% at 100% 0%, #d7efff 0%, #eaf5ff75 72%, transparent 100%),
    radial-gradient(ellipse 80% 58% at 12% 0%, #e7f2ff 0%, transparent 100%),
    linear-gradient(180deg, #eff3fb 0%, #f9fbff 40%, #ffffff 70%);
}
.landing-header {
  height: calc(102 * var(--u));
  padding: 0 5.8vw;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;
}
.wordmark { display: flex; align-items: center; gap: calc(9 * var(--u)); font-size: calc(34 * var(--u)); font-weight: 600; letter-spacing: 2px; }
.brand-mark { width: calc(36 * var(--u)); height: calc(36 * var(--u)); flex-shrink: 0; }
.brand-en { font-size: calc(17 * var(--u)); letter-spacing: -.3px; font-weight: 400; margin-left: calc(8 * var(--u)); color: #5c6e8b; }
.header-actions { display: flex; align-items: center; gap: calc(14 * var(--u)); }
.text-button { color: var(--accent); background: transparent; padding: 0; margin: 0; font-size: clamp(13px, calc(18 * var(--u)), 22px); line-height: 44px; }
.small-primary { margin: 0; padding: 0 calc(22 * var(--u)); min-height: 38px; height: calc(52 * var(--u)); line-height: calc(52 * var(--u)); display: flex; align-items: center; border-radius: calc(14 * var(--u)); font-size: clamp(14px, calc(18 * var(--u)), 22px); background: var(--accent-deep); color: #fff; }
.icon-button { display: flex; align-items: center; justify-content: center; width: max(44px, calc(58 * var(--u))); height: max(44px, calc(58 * var(--u))); margin: 0; padding: 0; border-radius: 10px; background: transparent; }
.icon-button .q-icon { width: max(20px, calc(26 * var(--u))); height: max(20px, calc(26 * var(--u))); }
.icon-button:hover { background: #edf4ff; }
.header-menu { position: absolute; right: 5.8vw; top: calc(84 * var(--u)); z-index: 5; min-width: 160px; padding: 8px; border: 1px solid var(--line); border-radius: 12px; background: #fff; box-shadow: 0 10px 30px #2d4c8510; }
.header-menu button { padding: 0 16px; border-radius: 6px; background: transparent; font-size: 15px; text-align: left; }
.header-menu button:hover { background: #edf4ff; }
.landing-main { min-height: calc(100vh - 102 * var(--u)); }
.landing-intro { position: absolute; top: 31.8vh; left: 50%; width: 32.36vw; text-align: center; transform: translateX(-50%); }
.landing-title { font-family: 'Noto Serif SC', 'Songti SC', SimSun, serif; font-size: calc(74 * var(--u)); line-height: 1.2; font-weight: 500; white-space: nowrap; }
.name-accent { color: var(--accent); border-bottom: calc(3 * var(--u)) solid #b9d4ff; padding-bottom: calc(4 * var(--u)); }
.intro-copy, .intro-detail { display: block; width: calc(700 * var(--u)); max-width: 100%; margin: calc(25 * var(--u)) auto 0; font-size: clamp(14px, calc(20 * var(--u)), 26px); color: var(--muted); line-height: 1.5; }
.intro-detail { margin-top: calc(20 * var(--u)); }
.strong { font-weight: 600; color: #405476; }
.landing-composer { position: absolute; top: 54.4vh; left: 50%; width: 32.36vw; transform: translateX(-50%); --composer-height: 15.76vh; }
.composer-footnote { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: calc(20 * var(--u)); color: #5c6e8b; font-size: clamp(11px, calc(14 * var(--u)), 18px); }
.composer-footnote > view { display: flex; align-items: center; gap: 6px; }
.composer-footnote .q-icon { width: max(14px, calc(20 * var(--u))); height: max(14px, calc(20 * var(--u))); opacity: .6; }
.landing-footer { position: absolute; bottom: 3vh; left: 5.8vw; right: 5.8vw; display: flex; justify-content: space-between; font-size: clamp(11px, calc(14 * var(--u)), 18px); color: #657590; }
.workspace-shell { display: flex; height: 100vh; overflow: hidden; }
.sidebar { display: flex; flex-direction: column; align-items: center; width: 4.57vw; flex-shrink: 0; padding: calc(40 * var(--u)) calc(10 * var(--u)) calc(24 * var(--u)); box-sizing: border-box; background: #f5f9ffb8; border-right: 1px solid #e0e8f4; z-index: 4; transition: width 320ms cubic-bezier(.22, 1, .36, 1), background-color 220ms ease; }
.sidebar-expanded { width: max(190px, calc(260 * var(--u))); }
.sidebar-logo { display: none; align-items: center; gap: 12px; padding: 0; background: transparent; margin-bottom: 20px; }
.sidebar-expanded .sidebar-logo { display: flex; }
.sidebar-brand { font-size: 24px; letter-spacing: 2px; font-weight: 600; }
.sidebar-collapse { opacity: .45; }
.sidebar-nav { display: flex; flex-direction: column; gap: calc(12 * var(--u)); width: 100%; padding-top: calc(25 * var(--u)); margin-top: calc(25 * var(--u)); border-top: 1px dashed #dce6f4; }
.nav-item { position: relative; display: flex; align-items: center; justify-content: center; gap: 12px; width: max(44px, calc(60 * var(--u))); height: max(44px, calc(60 * var(--u))); margin: 0 auto; padding: 0; border-radius: 50%; background: transparent; color: var(--ink); font-size: 14px; overflow: visible; line-height: 1.4; }
.nav-item .q-icon { width: max(20px, calc(28 * var(--u))); height: max(20px, calc(28 * var(--u))); }
.nav-item-active { background: #e3edff; }
.nav-item:hover { background: #e9f1ff; }
.sidebar-expanded .nav-item { width: 100%; padding-left: 16px; border-radius: 10px; justify-content: flex-start; box-sizing: border-box; }
.nav-tooltip { display: none; position: absolute; left: 110%; top: 8px; z-index: 5; padding: 8px 12px; border-radius: 6px; background: var(--ink); color: #fff; font-size: 13px; white-space: nowrap; }
.nav-item:hover .nav-tooltip, .nav-item:focus-visible .nav-tooltip { display: block; }
.sidebar-bottom { margin-top: auto; width: 100%; }
.sidebar-person { display: flex; align-items: center; justify-content: center; gap: 10px; padding-top: 20px; margin-top: 20px; border-top: 1px dashed #dce6f4; }
.sidebar-expanded .sidebar-person { justify-content: flex-start; padding-left: 12px; }
.patient-avatar { display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 50%; background: #e3edff; color: #48618f; font-size: 14px; flex-shrink: 0; }
.patient-name, .patient-description { display: block; font-size: 13px; line-height: 1.7; }
.patient-description { color: var(--muted); font-size: 12px; }
.workspace-main { display: flex; flex-direction: column; flex: 1; min-width: 0; overflow: hidden; }
.workspace-content { display: flex; flex-direction: column; flex: 1; min-width: 0; min-height: 0; animation: view-enter 360ms ease both; }
.workspace-pane { height: 100%; min-height: 0; overflow-y: auto; }
.recent-conversations { flex: 1; min-height: 0; width: 100%; overflow-y: auto; padding-top: 26px; }
.recent-heading { display: block; padding: 0 12px 10px; color: #657590; font-size: 12px; text-align: left; }
.recent-empty { display: block; padding: 8px 12px; color: #657590; font-size: 12px; }
.recent-conversation { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 58px; margin: 3px 0; padding: 10px 12px; border-radius: 10px; background: transparent; text-align: left; line-height: 1.5; }
.recent-conversation > view { min-width: 0; flex: 1; }
.recent-conversation .q-icon { width: 19px; height: 19px; flex-shrink: 0; opacity: .7; }
.recent-conversation:hover, .recent-current { background: #eaf1fd; }
.recent-title { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #30466c; font-size: 13px; }
.recent-kind { display: block; color: #657590; font-size: 11px; }
.sidebar-person { width: 100%; background: transparent; border-radius: 0; text-align: left; padding-bottom: 0; line-height: 1.5; }
.mode-tag { flex-shrink: 0; padding: 4px 8px; background: #e7efff; color: #315f9e; border-radius: 6px; font-size: 12px; }
.follow-up-mode { background: #e6f3ee; color: #2b6854; }
.follow-up-context { display: flex; gap: 12px; padding: 15px 18px; background: #edf4ff; border: 1px solid #dbe6f7; border-radius: 14px; color: #52698d; font-size: 13px; line-height: 1.7; }
.follow-up-context > view { min-width: 0; }
.follow-up-context .q-icon { flex-shrink: 0; margin-top: 3px; }
.follow-up-context text { display: block; }
.context-title { color: #30466c; font-weight: 600; font-size: 15px; }
.context-link { min-height: 36px; margin: 4px 0 0; padding: 0; background: transparent; text-align: left; color: #2365c7; font-size: 13px; line-height: 36px; }
.completed-conversation { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 14px; background: #edf6f2; border-radius: 12px; color: #345e50; font-size: 14px; line-height: 1.6; }
.completed-conversation text { flex: 1; }
.completed-conversation button { min-height: 44px; margin: 0; padding: 0 12px; background: #fff; color: #2365c7; font-size: 14px; line-height: 44px; }
.mobile-nav, .mobile-history-button { display: none; }
.history-menu { position: absolute; z-index: 20; top: 66px; right: 12px; width: min(320px, calc(100% - 24px)); max-height: 65vh; padding: 16px; overflow-y: auto; box-sizing: border-box; background: #fff; border: 1px solid #dce5f2; border-radius: 16px; box-shadow: 0 12px 40px #29466d20; }
.history-new { min-height: 44px; margin-top: 10px; background: #edf4ff; color: #2365c7; font-size: 14px; line-height: 44px; }
.storage-notice { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 24px; background: #fff1ee; color: #8c4236; font-size: 13px; line-height: 1.6; }
.storage-notice button { flex-shrink: 0; min-height: 44px; margin: 0; background: #fff; color: #8c4236; font-size: 13px; line-height: 44px; }
.workspace-header { display: flex; align-items: center; justify-content: space-between; height: 74px; min-height: 74px; padding: 0 34px; border-bottom: 1px solid var(--line); box-sizing: border-box; }
.breadcrumb { display: flex; align-items: center; gap: 14px; font-size: 14px; color: var(--muted); }
.breadcrumb-brand { color: var(--ink); font-weight: 600; }
.slash { color: #becbe0; }
.workspace-actions { display: flex; align-items: center; gap: 16px; }
.demo-tag { font-size: 12px; padding: 5px 9px; border: 1px solid #d9e4f5; background: #edf4ff; color: #617493; border-radius: 5px; }
.empty-chat { position: relative; flex: 1; overflow-y: auto; text-align: center; }
.chat-welcome { position: absolute; top: 16.9vh; left: 50%; width: 43vw; transform: translateX(-50%); }
.welcome-mark { display: block; width: calc(96 * var(--u)); height: calc(96 * var(--u)); margin: 0 auto; }
.welcome-title { margin: calc(18 * var(--u)) 0 calc(12 * var(--u)); font-family: 'Noto Serif SC', 'Songti SC', SimSun, serif; font-size: calc(62 * var(--u)); font-weight: 500; line-height: 1.2; }
.welcome-title-end { display: inline-block; white-space: nowrap; }
.welcome-description { display: block; width: calc(960 * var(--u)); max-width: 100%; margin: auto; color: var(--muted); font-size: clamp(14px, calc(24 * var(--u)), 28px); line-height: 1.45; }
.welcome-break { display: block; }
.chat-entry-composer { position: absolute; top: 38.83vh; left: 50%; width: 43vw; margin: 0; text-align: left; transform: translateX(-50%); --composer-height: 14.21vh; }
.medical-note { display: block; margin-top: calc(13 * var(--u)); font-size: clamp(11px, calc(14 * var(--u)), 18px); line-height: 1.6; color: #657590; text-align: center; }
.quick-start { position: absolute; top: max(57.4vh, calc(38.83vh + 150px)); left: 50%; width: calc(800 * var(--u)); transform: translateX(-50%); }
.prompt-list { display: flex; flex-wrap: wrap; justify-content: center; gap: calc(12 * var(--u)); }
.prompt-chip { display: flex; align-items: center; justify-content: center; width: calc(246 * var(--u)); height: max(42px, calc(58 * var(--u))); padding: 0 12px; margin: 0; border-radius: calc(12 * var(--u)); background: #eef4ff; color: #435c84; font-size: clamp(14px, calc(20 * var(--u)), 24px); line-height: 1.4; box-sizing: border-box; }
.prompt-chip:hover { background: #e1ecff; }
.entry-assurances { position: absolute; top: max(69vh, calc(38.83vh + 255px)); left: 50%; display: flex; align-items: center; justify-content: center; gap: calc(40 * var(--u)); width: 38.66vw; padding-top: calc(34 * var(--u)); border-top: 1px dashed #dce6f4; color: #5c6e8b; font-size: clamp(11px, calc(14 * var(--u)), 18px); transform: translateX(-50%); }
.entry-assurances > view { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.entry-assurances .q-icon { width: max(16px, calc(21 * var(--u))); height: max(16px, calc(21 * var(--u))); opacity: .55; }
.conversation-layout { display: grid; grid-template-columns: minmax(0, 1fr) 25vw; align-self: stretch; flex: 1; gap: 4vw; width: 100%; min-height: 0; padding: 5.5vh max(12px, calc(24 * var(--u))) 4vh 0; box-sizing: border-box; }
.conversation-column { display: flex; flex-direction: column; justify-self: center; width: min(50vw, calc(100% - 4vw)); min-width: 0; min-height: 0; padding-top: calc(20 * var(--u)); }
.emergency-note { display: flex; align-items: center; gap: 10px; color: #425577; font-size: clamp(14px, calc(24 * var(--u)), 28px); line-height: 1.4; font-weight: 500; }
.emergency-note .q-icon { width: max(16px, calc(24 * var(--u))); height: max(16px, calc(24 * var(--u))); opacity: .5; }
.messages-scroll { flex: 1; min-height: 0; height: 0; }
.messages-list { display: flex; flex-direction: column; gap: calc(35 * var(--u)); padding: calc(34 * var(--u)) 0 calc(24 * var(--u)); }
.message { display: flex; flex-direction: column; align-items: flex-start; }
.message-user { align-items: flex-end; }
.message-bubble { max-width: 94%; box-sizing: border-box; color: #30466c; font-size: clamp(15px, calc(24 * var(--u)), 28px); line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }
.message-user .message-bubble { padding: calc(24 * var(--u)); border-radius: calc(24 * var(--u)) calc(5 * var(--u)) calc(24 * var(--u)) calc(24 * var(--u)); background: #e7f0ff; }
.bubble-in-flight { visibility: hidden; }
.assistant-identity { display: flex; align-items: center; gap: 9px; margin-bottom: calc(14 * var(--u)); font-size: clamp(14px, calc(20 * var(--u)), 24px); font-weight: 500; }
.assistant-identity image { width: max(25px, calc(32 * var(--u))); height: max(25px, calc(32 * var(--u))); }
.message-assistant .message-bubble { padding-left: calc(41 * var(--u)); }
.pending-message { display: flex; align-items: center; gap: 12px; padding: 8px 0; color: #5c6e8b; font-size: clamp(14px, calc(20 * var(--u)), 24px); }
.loading-dots { display: flex; gap: 4px; }
.loading-dots text { width: 5px; height: 5px; border-radius: 50%; background: #5c91e6; animation: pulse 1s ease-in-out infinite; }
.loading-dots text:nth-child(2) { animation-delay: .15s; }
.loading-dots text:nth-child(3) { animation-delay: .3s; }
.message-end { height: 1px; }
.conversation-composer { margin-top: auto; --composer-height: 12.14vh; }
.conversation-tools { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 0 calc(12 * var(--u)); color: #657590; font-size: clamp(11px, calc(14 * var(--u)), 18px); }
.save-button { display: flex; align-items: center; gap: 7px; padding: 0 3px; margin: 0; background: transparent; color: var(--accent); font-size: clamp(13px, calc(18 * var(--u)), 22px); line-height: 36px; }
.save-button[disabled] { background: transparent; color: #7b90b2; }
.save-button .q-icon { width: max(16px, calc(20 * var(--u))); height: max(16px, calc(20 * var(--u))); opacity: .65; }
.context-column { width: 25vw; min-width: 0; flex-shrink: 0; overflow-y: auto; }
.context-column, .conversation-composer, .message-assistant, .pending-message { transition: opacity .35s ease, transform .35s ease; }
.is-transitioning .context-column { opacity: 0; transform: translateY(12px); }
.is-transitioning .conversation-composer, .is-transitioning .message-assistant, .is-transitioning .pending-message { opacity: 0; }
@keyframes pulse { 50% { opacity: .3; transform: translateY(-3px); } }
.reveal-character { display: inline-block; animation: character-enter 580ms cubic-bezier(.22, 1, .36, 1) both; }
.intro-copy { animation: copy-enter 620ms ease 200ms both; }
.intro-detail { animation: copy-enter 620ms ease 340ms both; }
.welcome-description { animation: copy-enter 620ms ease 220ms both; }
.composer-footnote, .medical-note { animation: copy-enter 500ms ease 300ms both; }
.message-assistant .message-bubble { animation: copy-enter 400ms ease both; }
.sidebar-brand, .sidebar-person .patient-name, .sidebar-person .patient-description { animation: view-enter 240ms ease both; }
.header-menu { animation: menu-enter 180ms ease both; }
.icon-button, .nav-item, .small-primary, .text-button, .prompt-chip, .save-button { transition: background-color 220ms ease, color 220ms ease, box-shadow 220ms ease, transform 160ms ease; }
.icon-button:active, .nav-item:active { transform: scale(.92); }
.small-primary:active, .prompt-chip:active, .save-button:active { transform: scale(.97); }
.nav-item-active { box-shadow: inset 0 0 0 1px #cbdcff; }
.text-button, .save-button { color: #2365c7; }
@keyframes character-enter {
  from { opacity: 0; transform: translateY(.16em); filter: blur(3px); }
  to { opacity: 1; transform: translateY(0); filter: blur(0); }
}
@keyframes copy-enter {
  from { opacity: 0; filter: blur(2px); }
  to { opacity: 1; filter: blur(0); }
}
@keyframes view-enter {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes menu-enter {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
@media (prefers-reduced-motion: reduce) {
  .reveal-character, .intro-copy, .intro-detail, .welcome-description, .composer-footnote, .medical-note,
  .workspace-content, .message-assistant .message-bubble, .sidebar-brand, .sidebar-person .patient-name,
  .sidebar-person .patient-description, .header-menu { animation: none; }
  .sidebar, .icon-button, .nav-item, .small-primary, .text-button, .prompt-chip, .save-button { transition: none; }
}
@media (max-width: 1000px) {
  .app-shell { --u: .65px; }
  .landing-header { height: 76px; padding: 0 28px; }
  .wordmark { font-size: 25px; gap: 9px; }
  .brand-mark { width: 36px; height: 36px; }
  .brand-en { font-size: 13px; }
  .landing-main { min-height: calc(100vh - 136px); padding: 100px 24px 120px; }
  .landing-intro { position: static; width: 100%; max-width: 620px; margin: auto; transform: none; }
  .landing-title { font-size: 48px; }
  .intro-copy, .intro-detail { width: 530px; max-width: 100%; font-size: 16px; }
  .landing-composer { position: static; width: 100%; max-width: 620px; margin: 45px auto 0; transform: none; --composer-height: 190px; }
  .landing-footer { position: absolute; bottom: 24px; left: 28px; right: 28px; }
  .sidebar { width: 68px; padding: 24px 8px 18px; }
  .sidebar-expanded { width: 190px; }
  .chat-welcome { position: static; width: 100%; transform: none; }
  .empty-chat { padding: 85px 30px 40px; }
  .welcome-mark { width: 64px; height: 64px; }
  .welcome-title { margin: 24px 0 16px; font-size: 36px; }
  .welcome-description { width: 600px; font-size: 16px; }
  .chat-entry-composer { position: static; width: 100%; max-width: 650px; margin: 36px auto 0; transform: none; --composer-height: 175px; }
  .quick-start { position: static; width: 100%; max-width: 600px; margin: 34px auto 0; transform: none; }
  .prompt-chip { width: 175px; height: 46px; font-size: 15px; }
  .entry-assurances { position: static; width: 100%; max-width: 650px; margin: 38px auto 0; transform: none; padding-top: 26px; gap: 25px; }
  .conversation-layout { display: block; width: 100%; transform: none; padding: 0; overflow-y: auto; }
  .conversation-column { width: 100%; min-height: calc(100vh - 74px); padding: 28px 30px 24px; box-sizing: border-box; }
  .messages-scroll { flex: none; min-height: 240px; height: 40vh; }
  .emergency-note { font-size: 14px; }
  .conversation-composer { --composer-height: 155px; }
  .context-column { width: auto; max-width: 720px; margin: 10px auto 36px; padding: 0 30px; overflow-y: visible; }
}
@media (max-width: 600px) {
  .landing-header { height: 76px; padding: 0 20px; }
  .brand-en, .archive-link { display: none; }
  .wordmark { font-size: 24px; }
  .header-actions { gap: 8px; }
  .small-primary { height: 40px; padding: 0 14px; border-radius: 10px; }
  .header-menu { top: 65px; right: 20px; }
  .landing-main { padding: 70px 22px 110px; }
  .landing-title { font-size: 36px; }
  .intro-copy, .intro-detail { font-size: 15px; line-height: 1.7; }
  .landing-composer { margin-top: 38px; --composer-height: 190px; }
  .landing-footer { left: 22px; right: 22px; font-size: 11px; gap: 20px; }
  .composer-footnote { font-size: 11px; margin-top: 14px; gap: 6px; }
  .workspace-shell { height: 100vh; height: 100dvh; padding-bottom: calc(66px + env(safe-area-inset-bottom)); box-sizing: border-box; }
  .sidebar { display: none; }
  .sidebar-expanded + .workspace-main { margin-left: 0; }
  .sidebar-nav { margin-top: 22px; padding-top: 22px; gap: 10px; }
  .sidebar-collapse { margin-top: 0; }
  .workspace-header { min-height: 64px; height: 64px; padding: 0 16px; }
  .breadcrumb { min-width: 0; gap: 8px; font-size: 13px; }
  .breadcrumb > text:nth-child(3) { max-width: 135px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .breadcrumb-brand, .slash { display: none; }
  .workspace-actions { gap: 4px; }
  .demo-tag { display: none; }
  .mobile-history-button { display: flex; }
  .mobile-nav { position: fixed; z-index: 30; bottom: 0; left: 0; right: 0; display: flex; height: calc(66px + env(safe-area-inset-bottom)); padding: 5px 12px calc(5px + env(safe-area-inset-bottom)); box-sizing: border-box; border-top: 1px solid #dce5f2; background: #f8fbfffa; }
  .mobile-nav button { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 3px; margin: 0; padding: 4px; background: transparent; color: #5c6e8b; font-size: 12px; line-height: 1.5; }
  .mobile-nav .q-icon { width: 23px; height: 23px; }
  .mobile-nav .mobile-tab-active { background: #e8f0ff; border-radius: 10px; color: #2365c7; font-weight: 600; }
  .empty-chat { padding: 74px 20px 30px; }
  .welcome-mark { width: 56px; height: 56px; }
  .welcome-title { font-size: 28px; line-height: 1.4; }
  .welcome-description { font-size: 14px; line-height: 1.8; }
  .welcome-break { display: inline; }
  .chat-entry-composer { --composer-height: 180px; }
  .prompt-chip { width: 100%; max-width: 230px; font-size: 14px; }
  .entry-assurances { flex-wrap: wrap; gap: 14px; font-size: 11px; }
  .entry-assurances > view { gap: 5px; }
  .medical-note { font-size: 11px; }
  .conversation-column { padding: 22px 18px; min-height: calc(100dvh - 130px); }
  .message-bubble { font-size: 16px; max-width: 98%; }
  .message-assistant .message-bubble { padding-left: 0; }
  .message-user .message-bubble { padding: 12px 16px; border-radius: 16px 3px 16px 16px; }
  .conversation-tools { align-items: flex-start; font-size: 12px; }
  .conversation-tools > text { max-width: 54%; }
  .save-button { flex-shrink: 0; font-size: 13px; }
  .context-column { padding: 0 18px; }
}
</style>
