<template>
  <view class="privacy-page live-ui">
    <button role="button" tabindex="0" @keydown="activateButton" class="live-link" @click="back">返回</button>
    <text class="live-title">{{ sensitive ? '敏感个人信息处理说明' : '清诉隐私说明' }}</text>
    <text class="live-muted">本页说明当前清诉服务中的信息处理与管理方式。</text>
    <view class="live-card">
      <template v-if="sensitive">
        <text class="policy-heading">处理哪些敏感信息</text><text class="policy-copy">你主动提供的症状、既往情况、过敏信息、用药、体征和问诊记录可能包含医疗健康等敏感个人信息。请只填写本次服务需要的信息。</text>
        <text class="policy-heading">处理用途</text><text class="policy-copy">这些信息用于整理描述、补充问诊信息、提供就医参考以及管理你保存的健康记录和提醒。智能处理可能使用第三方工作流服务；提交前请核对你愿意提供的内容。</text>
        <text class="policy-heading">你的选择</text><text class="policy-copy">注册时单独征求敏感信息处理同意。选填信息可以不提供，不知道的情况可以明确填写“不确定”。你可以在账户信息中导出或清空健康数据、注销账户；也可删除单条记录。</text>
      </template>
      <template v-else>
        <text class="policy-heading">我们处理的信息</text><text class="policy-copy">注册和登录使用手机号与密码；账户档案可包含称呼、出生日期、性别、城市、既往情况和过敏信息。你使用健康服务时，还会提交症状描述、问诊回答、体征、用药记录及提醒设置。</text>
        <text class="policy-heading">信息用于什么</text><text class="policy-copy">用于账户识别、保存和展示你的记录、整理问诊信息、提供就医参考、安排你选择的健康提醒。问诊智能处理使用第三方工作流服务，相关处理不能代替医生诊断。</text>
        <text class="policy-heading">保存与管理</text><text class="policy-copy">账户和健康记录保存在清诉服务中；登录状态保存在你使用的设备上。未保存的问诊有有效期，到期会按清理规则删除。你可以在账户信息中导出、清空健康数据或注销账户，也可以在健康档案中删除单条记录。退出登录会清除本设备的登录状态。</text>
        <text class="policy-heading">可选信息</text><text class="policy-copy">城市等标注为选填的信息可留空。出生日期和性别用于问诊所需的基本档案。选择“不确定”或“未告知”不会被当成明确没有相关情况。</text>
      </template>
      <text class="policy-heading">服务主体与联系信息</text><text class="policy-copy">本说明当前由清诉项目组维护，尚未对外提供服务。正式启用前，这里会写明运营主体与联系方式；启用之前请勿在服务中填写真实健康信息。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { activateButton } from '@/components/buttonKeyboard'
const sensitive = ref(false)
onLoad((options) => { sensitive.value = options?.section === 'sensitive' })
function back() { if (getCurrentPages().length > 1) uni.navigateBack(); else uni.redirectTo({ url: '/pages/chat/index' }) }
</script>

<style scoped>
.privacy-page { max-width: 780px; margin: 0 auto; padding: 30px 22px 60px; }
.privacy-page .live-title { margin: 20px 0 12px; }
.policy-heading { display: block; margin: 24px 0 9px; font-size: 17px; font-weight: 600; }
.policy-heading:first-child { margin-top: 0; }
.policy-copy { display: block; white-space: pre-wrap; line-height: 1.9; }
</style>
