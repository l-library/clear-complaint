<template>
  <view class="expression-review">
    <view class="review-heading"><view class="review-symbol"><QIcon name="spark" /></view><view><text class="review-title">把描述说清楚</text><text class="review-status">{{ pending ? '正在整理…' : '待本人核对' }}</text></view></view>
    <view class="review-section"><text class="section-label">你的原话</text><view v-for="message in userMessages" :key="message.id" class="original-quote"><text>{{ message.content }}</text></view></view>
    <view class="review-section"><view class="section-heading"><text class="section-label">整理草稿</text><text class="small-tag">原话摘录</text></view><view class="draft-card"><text class="draft-label">本人描述</text><text class="draft-copy">{{ description }}</text></view><text class="review-hint">尚未判断症状原因，原始表达保持不变。</text></view>
    <view class="review-section"><text class="section-label">可以继续补充</text><view class="detail-list"><button role="button" tabindex="0" @keydown="activateButton" v-for="(item, index) in details" :key="item.title" @click="$emit('request-detail', item.prompt)"><text class="detail-index">0{{ index + 1 }}</text><view><text class="detail-title">{{ item.title }}</text><text class="detail-subtitle">{{ item.subtitle }}</text></view><QIcon name="arrow-right" /></button></view></view>
    <view class="review-section boundary-section"><QIcon name="shield" /><text>纠偏服务尚未接入。当前仅展示原话与补充入口，不生成诊断或评估分数。</text></view>
  </view>
</template>

<script setup lang="ts">
import { activateButton } from '@/components/buttonKeyboard'
import { computed } from 'vue'
import QIcon from '@/components/QIcon.vue'
import type { ChatMessage } from '@/types/consultation'

const props = defineProps<{ messages: ChatMessage[]; pending: boolean }>()
defineEmits<{ (e: 'request-detail', content: string): void }>()
const userMessages = computed(() => props.messages.filter((message) => message.role === 'user'))
const description = computed(() => userMessages.value.map((message) => message.content).join('\n\n'))
const details = [
  { title: '开始时间与持续时间', subtitle: '什么时候开始，持续了多久？', prompt: '关于开始时间和持续时间：' },
  { title: '伴随表现', subtitle: '还有哪些同时出现的感觉？', prompt: '同时出现的其他不适：' },
  { title: '近期变化与已有资料', subtitle: '记录变化、测量结果或已有医嘱。', prompt: '近期变化，以及已有的测量或就诊资料：' },
]
</script>

<style scoped>
.expression-review { padding: clamp(18px, 1.2vw, 34px); color: #35413a; }
.review-heading { display: flex; align-items: flex-start; gap: 10px; padding: 2px 0 3px; }
.review-symbol { display: flex; justify-content: center; align-items: center; width: 24px; height: 28px; }
.review-symbol .q-icon { width: 19px; height: 19px; opacity: .55; }
.review-title { display: block; font-size: clamp(16px, .8vw, 20px); font-weight: 500; line-height: 1.5; color: #626c65; }
.review-status { display: block; margin-top: 4px; color: #657064; font-size: 11px; }
.review-section { margin-top: 24px; }
.section-label { display: block; font-size: 13px; font-weight: 500; line-height: 1.6; }
.original-quote { margin-top: 11px; padding-left: 14px; border-left: 1px solid #cbd8d0; color: #5f6a62; font-size: 14px; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; }
.section-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.small-tag { padding: 3px 7px; border: 1px solid var(--glass-stroke, #fff); border-radius: 6px; background: var(--glass-surface, #ffffff6b); color: #657064; font-size: 10px; }
.draft-card { margin-top: 12px; padding: 18px; border: 1px solid var(--glass-stroke, #fff); border-radius: 16px; background: var(--glass-surface, #ffffff6b); box-shadow: inset 0 1px 0 rgba(255, 255, 255, .9); }
.draft-label { display: block; margin-bottom: 8px; color: #526b70; font-size: 11px; }
.draft-copy { font-size: 14px; line-height: 1.85; white-space: pre-wrap; overflow-wrap: anywhere; }
.review-hint { display: block; margin-top: 10px; color: #657064; font-size: 11px; line-height: 1.7; }
.detail-list { margin-top: 10px; }
.detail-list button { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 75px; margin: 0; padding: 15px 0; border-bottom: 1px solid var(--glass-rule, #dce3dc); border-radius: 0; background: transparent; text-align: left; line-height: 1.6; transition: background-color .16s, transform .16s; }
.detail-list button:hover { background: rgba(255, 255, 255, .35); }
.detail-list button:active { transform: translateX(2px); }
.detail-list button:last-child { border-bottom: 0; }
.detail-list button > view { flex: 1; min-width: 0; }
.detail-index { color: #a1a19a; font-size: 11px; }
.detail-title { display: block; color: #35413a; font-size: 13px; }
.detail-subtitle { display: block; margin-top: 3px; color: #657064; font-size: 11px; }
.detail-list .q-icon { width: 17px; height: 17px; opacity: .5; }
.boundary-section { display: flex; gap: 8px; padding-top: 18px; border-top: 1px solid var(--glass-rule, #dce3dc); color: #657064; font-size: 11px; line-height: 1.8; }
.boundary-section .q-icon { flex-shrink: 0; width: 15px; height: 15px; margin-top: 2px; opacity: .55; }
</style>
