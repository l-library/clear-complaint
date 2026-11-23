<template>
  <view class="context-panel">
    <button role="button" tabindex="0" @keydown="activateButton" class="panel-heading" :aria-expanded="expanded" @click="expanded = !expanded">
      <view class="heading-icon"><QIcon :name="isFollowUp ? 'calendar' : 'file'" /></view>
      <view><text class="panel-title">{{ isFollowUp ? '本次随访' : '问诊记录' }}</text></view>
      <QIcon :name="expanded ? 'collapse' : 'chevron'" />
    </button>
    <view v-show="expanded" class="panel-body">
      <view class="event-card"><text class="eyebrow">关联健康事件</text><text class="event-title">{{ currentEpisode?.title || '尚未关联健康事件' }}</text><text class="muted">{{ isFollowUp ? '回顾已有记录，记录本次变化' : '整理症状描述，保留原始表达' }}</text></view>
      <view v-if="followUpPlan" class="section"><text class="section-title">本次回顾目标</text><text class="body-copy">{{ followUpPlan.goal }}</text><view v-for="question in followUpPlan.questions" :key="question" class="question-line"><text class="dot">·</text><text>{{ question }}</text></view></view>
      <view class="section"><text class="section-title">已收到的描述 <text class="count">{{ userMessages.length }}</text></text><text v-if="!userMessages.length" class="muted">等待你补充当前的情况</text><view v-for="(message, index) in userMessages" :key="message.id" class="description"><text class="description-number">{{ index + 1 }}</text><text>{{ message.content }}</text></view></view>
      <view v-if="linkedRecords.length" class="section"><text class="section-title">相关健康记录</text><button role="button" tabindex="0" @keydown="activateButton" v-for="record in linkedRecords" :key="record.id" class="record-link" @click="$emit('open-record', record.id)"><QIcon name="file" /><view><text>{{ record.title }}</text><text class="record-meta">{{ sourceLabel(record.source) }} · {{ record.date.slice(0, 10) }}</text></view><QIcon name="chevron" /></button></view>
      <view class="section"><text class="section-title">下一步</text><text class="body-copy">{{ isFollowUp ? '补充这段时间的变化，核对并归档后，本次随访任务会更新为已完成。' : '核对当前对话并归档，再从健康档案安排随访或录入已确认的用药计划。' }}</text><button role="button" tabindex="0" @keydown="activateButton" class="plans-link" @click="$emit('open-plans')"><QIcon name="calendar" /><text>查看健康计划</text><QIcon name="chevron" /></button></view>
      <view class="demo-note"><QIcon name="info" /><text>当前展示本地交互流程。真实 AI 分诊草稿待接口接入；此处的用户原话和演示摘要不作为医生诊断。</text></view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { activateButton } from '@/components/buttonKeyboard'
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import QIcon from '@/components/QIcon.vue'
import { useConsultationStore } from '@/stores/consultation'
import type { FollowUpPlan, RecordSource } from '@/types/consultation'

defineEmits<{ (e: 'open-record', id: string): void; (e: 'open-plans'): void }>()
const store = useConsultationStore()
const { activeConversation, currentEpisode, messages, plans, records } = storeToRefs(store)
const expanded = ref(true)
const isFollowUp = computed(() => activeConversation.value?.type === 'follow_up')
const userMessages = computed(() => messages.value.filter((message) => message.role === 'user'))
const linkedRecords = computed(() => records.value.filter((record) => record.healthEpisodeId === currentEpisode.value?.id))
const followUpPlan = computed(() => plans.value.find((plan): plan is FollowUpPlan => plan.type === 'follow_up' && plan.id === activeConversation.value?.followUpPlanId))
function sourceLabel(source: RecordSource) {
  return source === 'medical_document' ? '医院病历' : source === 'ai_follow_up' ? '随访记录' : '问诊记录'
}
</script>

<style scoped>
.context-panel { overflow: hidden; background: transparent; border: 0; border-radius: 0; color: #35413a; }
.panel-heading { display: flex; align-items: center; gap: 12px; width: 100%; padding: 24px 22px; margin: 0; background: transparent; text-align: left; line-height: 1.5; border-radius: 0; }
.panel-heading > view:nth-child(2) { flex: 1; min-width: 0; }
.heading-icon { display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 12px; background: var(--glass-surface, #ffffff6b); }
.heading-icon .q-icon { width: 23px; height: 23px; }
.panel-title { display: block; font-size: 19px; font-weight: 600; }
.panel-subtitle { display: block; margin-top: 4px; color: var(--muted, #767674); font-size: 12px; }
.panel-body { padding: 0 22px 22px; }
.event-card { padding: 18px; border: 1px solid var(--glass-stroke, #fff); border-radius: 16px; background: var(--glass-surface, #ffffff6b); box-shadow: inset 0 1px 0 #fff; }
.eyebrow { display: block; color: var(--muted, #767674); font-size: 12px; }
.event-title { display: block; margin: 6px 0; font-size: 16px; font-weight: 600; }
.muted { display: block; font-size: 13px; color: var(--muted, #767674); line-height: 1.7; }
.section { padding-top: 24px; }
.section-title { display: block; margin-bottom: 12px; font-size: 15px; font-weight: 600; }
.count { margin-left: 5px; padding: 2px 7px; background: var(--surface-soft, #f5f5f0); border-radius: 6px; color: var(--muted, #767674); font-size: 12px; }
.body-copy, .question-line { display: block; font-size: 14px; line-height: 1.8; color: var(--muted, #767674); }
.question-line { display: flex; gap: 9px; margin-top: 8px; }
.dot { color: #7398ca; }
.description { display: flex; gap: 10px; margin-top: 10px; padding: 12px; background: var(--glass-surface, #ffffff6b); border-radius: 10px; font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.description-number { flex-shrink: 0; font-size: 12px; color: #767674; }
.record-link, .plans-link { display: flex; align-items: center; gap: 10px; width: 100%; min-height: 54px; margin: 0 0 7px; padding: 12px; background: var(--glass-surface, #ffffff6b); border-radius: 10px; color: #35413a; font-size: 14px; line-height: 1.5; text-align: left; }
.record-link > view, .plans-link > text { flex: 1; min-width: 0; }
.record-link text { display: block; }
.record-link .q-icon, .plans-link .q-icon { flex-shrink: 0; width: 18px; height: 18px; }
.record-meta { margin-top: 5px; font-size: 12px; color: var(--muted, #767674); }
.plans-link { margin-top: 14px; color: #526b70; border: 1px solid var(--glass-stroke, #fff); background: var(--glass-surface, #ffffff6b); }
.demo-note { display: flex; gap: 8px; margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--line, #e4e4df); color: var(--muted, #767674); font-size: 12px; line-height: 1.8; }
.demo-note .q-icon { flex-shrink: 0; width: 16px; height: 16px; margin-top: 3px; }
@media (max-width: 600px) { .context-panel { border-radius: 18px; } .panel-heading { min-height: 70px; padding: 18px; } .panel-body { padding: 0 18px 18px; } }
</style>
