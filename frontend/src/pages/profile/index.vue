<template>
  <view class="profile-page">
    <view class="profile-shell">
      <header class="profile-header">
        <view class="brand">
          <text class="brand-mark">清</text>
          <view>
            <text class="brand-name">清诉</text>
            <text class="brand-subtitle">基础健康档案</text>
          </view>
        </view>
        <text class="step-badge">开始问诊前</text>
      </header>

      <view class="profile-intro">
        <text class="eyebrow">HEALTH PROFILE</text>
        <text class="headline">补全基础信息</text>
        <text class="description">
          出生日期、性别等基础条件会影响就医建议。档案只用于本次健康管理，不构成诊断。
        </text>
        <view v-if="missingText" class="missing-note">
          <text class="missing-title">还需要确认</text>
          <text class="missing-text">{{ missingText }}</text>
        </view>
      </view>

      <view class="form-card">
        <view class="form-grid">
          <view class="field full">
            <text class="label">姓名或称呼</text>
            <input v-model="form.name" class="input" placeholder="例如：王阿姨" />
          </view>

          <view class="field">
            <text class="label">出生日期</text>
            <picker mode="date" start="1900-01-01" :end="today" :value="form.birth_date" @change="changeBirthDate">
              <view class="picker-value">
                {{ form.birth_date || '请选择出生日期' }}
              </view>
            </picker>
          </view>

          <view class="field">
            <text class="label">性别</text>
            <picker :range="sexOptions" :value="sexIndex" @change="changeSex">
              <view class="picker-value">{{ sexOptions[sexIndex] }}</view>
            </picker>
          </view>

          <view class="field">
            <text class="label">常住城市</text>
            <picker :range="cityOptions" :value="cityIndex" @change="changeCity">
              <view class="picker-value">{{ form.city_name || '请选择常住城市' }}</view>
            </picker>
          </view>

          <view class="field full">
            <text class="label">既往病史</text>
            <input
              v-model="conditionsText"
              class="input"
              placeholder="多个疾病用逗号分隔，例如：高血压, 糖尿病"
            />
          </view>

          <view class="field full">
            <text class="label">过敏史</text>
            <input
              v-model="allergiesText"
              class="input"
              placeholder="多个过敏项用逗号分隔；没有可填写“无”"
            />
          </view>

          <view class="field full">
            <text class="label">病史补充</text>
            <textarea
              v-model="form.condition_note"
              class="textarea"
              maxlength="200"
              placeholder="例如：高血压 2020 年确诊，按原方案服药"
            />
          </view>
        </view>

        <text v-if="errorText" class="error-text">{{ errorText }}</text>

        <view class="actions">
          <button class="secondary" :disabled="loading" @click="loadProfile">重新读取</button>
          <button class="primary" :loading="loading" @click="save">保存并进入工作台</button>
        </view>
      </view>

      <text class="footer-note">
        当前页面已连接档案 API 代码；后端启动后可真实读取和保存。不会上传真实密钥。
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { getProfile, updateProfile, type Profile, type Sex } from '@/api/profile'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const errorText = ref('')
const today = new Date().toISOString().slice(0, 10)
const profile = ref<Profile | null>(null)
const conditionsText = ref('')
const allergiesText = ref('')

const form = reactive({
  name: '',
  birth_date: '',
  sex: 'undisclosed' as Sex,
  city_code: '310100',
  city_name: '上海市',
  condition_note: '',
})

const sexOptions = ['请选择', '男', '女', '不愿透露']
const sexValues: Array<Sex | null> = [null, 'male', 'female', 'undisclosed']
const sexIndex = ref(0)
const cities = [
  { name: '上海市', code: '310100' },
  { name: '北京市', code: '110100' },
  { name: '广州市', code: '440100' },
  { name: '深圳市', code: '440300' },
  { name: '杭州市', code: '330100' },
  { name: '南京市', code: '320100' },
  { name: '成都市', code: '510100' },
  { name: '武汉市', code: '420100' },
]
const cityOptions = cities.map((item) => item.name)
const cityIndex = ref(0)
const missingMap: Record<string, string> = {
  birth_date: '出生日期',
  sex: '性别',
}
const missingText = computed(() =>
  (profile.value?.required_missing ?? ['birth_date', 'sex'])
    .map((item) => missingMap[item] ?? item)
    .join('、'),
)

onMounted(loadProfile)

async function loadProfile() {
  loading.value = true
  errorText.value = ''
  try {
    const response = await getProfile()
    profile.value = response.profile
    if (response.profile) {
      form.name = response.profile.name ?? ''
      form.birth_date = response.profile.birth_date ?? ''
      form.sex = response.profile.sex ?? 'undisclosed'
      sexIndex.value = Math.max(0, sexValues.indexOf(response.profile.sex))
      form.city_code = response.profile.city_code ?? '310100'
      form.city_name = response.profile.city_name ?? '上海市'
      const matchedCity = cities.findIndex((item) => item.code === form.city_code)
      cityIndex.value = Math.max(0, matchedCity)
      form.condition_note = response.profile.condition_note ?? ''
      conditionsText.value = response.profile.conditions.join(', ')
      allergiesText.value = response.profile.allergies.join(', ')
    }
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '读取档案失败'
  } finally {
    loading.value = false
  }
}

function changeSex(event: { detail: { value: string | number } }) {
  const index = Number(event.detail.value)
  const value = sexValues[index]
  sexIndex.value = index
  if (value) form.sex = value
}

function changeBirthDate(event: { detail: { value: string } }) {
  form.birth_date = event.detail.value
}

function changeCity(event: { detail: { value: string | number } }) {
  const index = Number(event.detail.value)
  const city = cities[index]
  cityIndex.value = index
  if (city) {
    form.city_name = city.name
    form.city_code = city.code
  }
}

function splitList(value: string) {
  return value
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

async function save() {
  errorText.value = ''
  if (!form.birth_date || !form.sex) {
    errorText.value = '出生日期和性别是开始问诊前必须确认的信息。'
    return
  }
  if (!form.city_code !== !form.city_name) {
    errorText.value = '常住城市和行政区划码需要同时填写。'
    return
  }

  loading.value = true
  try {
    profile.value = await updateProfile({
      name: form.name,
      birth_date: form.birth_date,
      sex: form.sex,
      city_code: form.city_code,
      city_name: form.city_name,
      condition_note: form.condition_note,
      conditions: splitList(conditionsText.value),
      allergies: splitList(allergiesText.value),
    })
    auth.updateProfileComplete(true)
    uni.reLaunch({ url: '/pages/workspace/index' })
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '保存档案失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  padding: 36px 24px 60px;
  background:
    radial-gradient(circle at 90% 8%, rgba(166, 226, 207, 0.28), transparent 30%),
    #eff9f5;
  box-sizing: border-box;
}

.profile-shell {
  width: min(920px, 100%);
  margin: 0 auto;
}

.profile-header,
.brand,
.actions {
  display: flex;
}

.profile-header {
  align-items: center;
  justify-content: space-between;
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
  background: #4ba58d;
  color: #ffffff;
  font-size: 20px;
  font-weight: 800;
}

.brand-name,
.brand-subtitle,
.eyebrow,
.headline,
.description,
.missing-title,
.missing-text,
.label,
.error-text,
.footer-note {
  display: block;
}

.brand-name {
  font-size: 17px;
  font-weight: 800;
}

.brand-subtitle {
  margin-top: 2px;
  color: #78958a;
  font-size: 10px;
}

.step-badge {
  padding: 7px 11px;
  border-radius: 999px;
  background: #e1f4ed;
  color: #397b67;
  font-size: 10px;
}

.profile-intro {
  margin-top: 54px;
}

.eyebrow {
  color: #3d8d76;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 2px;
}

.headline {
  margin-top: 10px;
  color: #21483c;
  font-size: 34px;
  font-weight: 800;
}

.description {
  max-width: 690px;
  margin-top: 12px;
  color: #69847a;
  font-size: 13px;
  line-height: 1.75;
}

.missing-note {
  margin-top: 18px;
  padding: 12px 15px;
  border: 1px solid #eadbab;
  border-radius: 11px;
  background: #fffdf6;
}

.missing-title {
  color: #796524;
  font-size: 10px;
  font-weight: 800;
}

.missing-text {
  margin-top: 4px;
  color: #8b7950;
  font-size: 11px;
}

.form-card {
  margin-top: 24px;
  padding: 24px;
  border: 1px solid #dfeee8;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 15px 40px rgba(67, 139, 119, 0.06);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.field.full {
  grid-column: 1 / -1;
}

.label {
  margin-bottom: 7px;
  color: #426056;
  font-size: 11px;
  font-weight: 700;
}

.input,
.picker-value,
.textarea {
  width: 100%;
  border: 1px solid #d4e8df;
  border-radius: 11px;
  background: #fbfefc;
  color: #28493e;
  font-size: 12px;
  box-sizing: border-box;
}

.input,
.picker-value {
  height: 44px;
  padding: 0 13px;
  line-height: 44px;
}

.picker-value {
  color: #527166;
}

.textarea {
  height: 100px;
  padding: 12px 13px;
  line-height: 1.6;
}

.error-text {
  margin-top: 16px;
  padding: 10px 12px;
  border-radius: 9px;
  background: #fff6f2;
  color: #a35d49;
  font-size: 11px;
}

.actions {
  gap: 12px;
  margin-top: 22px;
}

.actions button {
  flex: 1;
  margin: 0;
  border-radius: 11px;
  font-size: 12px;
}

.primary {
  background: #4ba58d;
  color: #ffffff;
}

.secondary {
  border: 1px solid #cce5db;
  background: #ffffff;
  color: #3d7462;
}

.footer-note {
  margin-top: 16px;
  color: #8ca099;
  font-size: 9px;
  text-align: center;
}

@media (max-width: 700px) {
  .profile-page {
    padding: 22px 14px 40px;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .field.full {
    grid-column: auto;
  }

  .headline {
    font-size: 28px;
  }
}
</style>
