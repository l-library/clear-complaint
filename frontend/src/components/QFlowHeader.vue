<template>
  <view class="flow-header">
    <view class="header-top">
      <view class="brand">
        <text class="brand-mark">清</text>
        <view>
          <text class="brand-name">清诉</text>
          <text class="brand-subtitle">ClearComplaint</text>
        </view>
      </view>
      <text class="mock-badge">MOCK 演示</text>
    </view>

    <view class="step-line">
      <view
        v-for="item in 5"
        :key="item"
        class="step-dot"
        :class="{ active: item <= step, current: item === step }"
      />
    </view>

    <view class="heading-row">
      <view>
        <text class="step-label">STEP {{ step }} / 5</text>
        <text class="page-title">{{ title }}</text>
        <text class="page-subtitle">{{ subtitle }}</text>
      </view>
      <button v-if="showBack" class="back" @click="goBack">返回</button>
    </view>
  </view>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    step: number
    title: string
    subtitle: string
    showBack?: boolean
  }>(),
  {
    showBack: true,
  },
)

function goBack() {
  uni.navigateBack()
}
</script>

<style scoped>
.flow-header {
  padding: 26rpx 28rpx 30rpx;
  border-radius: 0 0 30rpx 30rpx;
  background:
    radial-gradient(circle at 90% 10%, rgba(118, 209, 180, 0.18), transparent 34%),
    #123f35;
  color: #ffffff;
}

.header-top,
.brand,
.heading-row {
  display: flex;
  align-items: center;
}

.header-top,
.heading-row {
  justify-content: space-between;
}

.brand {
  gap: 12rpx;
}

.brand-mark {
  display: flex;
  width: 54rpx;
  height: 54rpx;
  align-items: center;
  justify-content: center;
  border-radius: 16rpx;
  background: #d9f3e8;
  color: #123f35;
  font-size: 30rpx;
  font-weight: 800;
}

.brand-name,
.brand-subtitle {
  display: block;
}

.brand-name {
  font-size: 28rpx;
  font-weight: 700;
}

.brand-subtitle {
  margin-top: 1rpx;
  color: #b9d6cc;
  font-size: 18rpx;
  letter-spacing: 1rpx;
}

.mock-badge {
  padding: 8rpx 14rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.22);
  border-radius: 999rpx;
  color: #cce7dd;
  font-size: 19rpx;
}

.step-line {
  display: flex;
  gap: 10rpx;
  margin-top: 26rpx;
}

.step-dot {
  flex: 1;
  height: 6rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.15);
}

.step-dot.active {
  background: #78c9ad;
}

.step-dot.current {
  box-shadow: 0 0 14rpx rgba(120, 201, 173, 0.65);
}

.heading-row {
  align-items: flex-end;
  gap: 20rpx;
  margin-top: 28rpx;
}

.step-label {
  display: block;
  color: #89cbb5;
  font-size: 20rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
}

.page-title {
  display: block;
  margin-top: 7rpx;
  font-size: 42rpx;
  font-weight: 700;
  line-height: 1.3;
}

.page-subtitle {
  display: block;
  max-width: 500rpx;
  margin-top: 8rpx;
  color: #bdd8cf;
  font-size: 23rpx;
  line-height: 1.55;
}

.back {
  flex: 0 0 auto;
  width: auto;
  margin: 0;
  padding: 0 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.08);
  color: #e8f5f0;
  font-size: 23rpx;
  line-height: 58rpx;
}
</style>
