<template>
  <view class="episode-review live-ui">
    <view class="review-heading"><QIcon name="shield" /><text class="live-subtitle">描述与核验</text></view>
    <template v-if="detail">
      <view class="review-section"><text class="live-label">你的原话</text><text class="original-words">{{ detail.episode.complaint_text }}</text></view>
      <view class="review-section">
        <text class="live-label">整理信息</text>
        <view v-if="fields.length" class="normalized-fields"><view v-for="field in fields" :key="field.key" class="normalized-field"><text class="live-muted">{{ field.label }}</text><text class="live-preserve">{{ field.value }}</text></view></view>
        <text v-else class="live-muted">暂无已整理的信息。</text>
      </view>
      <view class="review-section"><text class="live-label">你对原因的推测</text><text class="live-preserve">{{ detail.self_attribution || '未记录原因推测' }}</text><text v-if="detail.self_attribution" class="live-muted attribution-note">此内容单独记录，不作为已确认的症状原因。</text></view>
      <view class="review-section">
        <text class="live-label">校验记录</text>
        <template v-if="hasGate">
          <view class="verification-row"><text>引用已核验</text><text>{{ gate?.citations_verified ?? '—' }}</text></view>
          <view class="verification-row"><text>引用已剔除</text><text>{{ gate?.citations_dropped ?? '—' }}</text></view>
          <view class="red-flag-list"><text class="live-muted">{{ gate?.red_flags?.length ? '命中的红旗规则' : '本次校验未记录红旗命中' }}</text><text v-for="flag in gate?.red_flags || []" :key="flag.rule_id" class="red-flag">{{ flag.name }}</text></view>
          <text v-if="gate?.fallback || gate?.degraded" class="live-notice">本次采用了保守降级处理。</text>
          <text v-else-if="gate?.out_of_coverage" class="live-notice">资料库暂不覆盖此类表现，建议仅按紧急程度与科室参考。</text>
        </template>
        <text v-else class="live-muted">暂无校验记录。</text>
      </view>
    </template>
    <text v-else class="live-muted">{{ pending ? '正在等待本次问诊的整理结果…' : '问诊整理信息将在这里显示。' }}</text>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import QIcon from '@/components/QIcon.vue'
import type { EpisodeDetail } from '@/api/episodes'

const props = defineProps<{ detail: EpisodeDetail | null; pending: boolean }>()
const labels: Record<string, string> = { symptom: '症状描述', onset_at: '开始时间', duration_text: '持续时间', site: '部位', nature: '感受与性质', associated: '伴随表现', medications_text: '用药情况' }
const fields = computed(() => Object.entries(labels).flatMap(([key, label]) => {
  const raw = props.detail?.normalized?.[key]
  const value = Array.isArray(raw) ? raw.filter((item) => typeof item === 'string').join('；') : raw
  return typeof value === 'string' && value.trim() ? [{ key, label, value: value === 'unknown' ? '本人暂不确定' : value }] : []
}))
const gate = computed(() => props.detail?.gate)
const hasGate = computed(() => Boolean(gate.value && Object.keys(gate.value).length))
</script>

<style scoped>
.episode-review { padding: clamp(22px, 1.3vw, 36px); }
.review-heading { display: flex; align-items: center; gap: 10px; }
.review-heading .q-icon { width: 22px; height: 22px; }
.review-section { margin-top: 26px; }
.original-words { display: block; padding-left: 15px; border-left: 2px solid var(--glass-rule, #deded7); white-space: pre-wrap; overflow-wrap: anywhere; }
.normalized-fields { padding: 17px; border: 1px solid rgba(255,255,255,.9); border-radius: 18px; background: rgba(255,255,255,.48); }
.normalized-field + .normalized-field { margin-top: 14px; }
.attribution-note { margin-top: 9px; }
.verification-row { display: flex; justify-content: space-between; gap: 15px; padding: 10px 0; border-bottom: 1px solid var(--glass-rule, #deded7); }
.red-flag-list { margin-top: 15px; }
.red-flag { display: block; margin-top: 8px; color: #a14136; }
</style>
