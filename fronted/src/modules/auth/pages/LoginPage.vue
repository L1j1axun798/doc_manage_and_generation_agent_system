<script setup lang="ts">
import { ArrowRight, InfoFilled, Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { appConfig } from '@/config/app'
import { getErrorMessage } from '@/core/http/error-normalizer'
import { setTheme } from '@/shared/composables/useTheme'
import { useAuthStore } from '../stores/auth.store'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

setTheme('light')

const loading = ref(false)
const loginStep = ref<'idle' | 'password'>('idle')
const form = reactive({
  username: '',
  password: '',
  remember_me: true,
})

async function submitLogin(): Promise<void> {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  loginStep.value = 'password'

  try {
    const user = await authStore.login({
      username: form.username,
      password: form.password,
      remember_me: form.remember_me,
    })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    await router.replace(user.must_change_password ? '/change-password' : redirect)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
    loginStep.value = 'idle'
  }
}
</script>

<template>
  <main class="login-page login-page--split">
    <section class="login-page__visual" aria-labelledby="platform-title">
      <div class="login-page__visual-content">
        <header class="login-page__intro">
          <h1 id="platform-title">绿能信盾企业资料管理与Agent平台</h1>
          <span class="login-page__title-accent" aria-hidden="true"></span>
          <p>高效管理 · 安全合规 · 智能协同</p>
        </header>

        <div class="login-page__features" aria-label="平台核心能力">
          <article class="login-page__feature">
            <span class="login-page__feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M3.75 7.25h6l1.7 2h8.8v8.5a2 2 0 0 1-2 2H5.75a2 2 0 0 1-2-2V7.25Z" />
                <path d="M5.75 4.25h4.7l1.7 2h6.1a2 2 0 0 1 2 2v1" />
              </svg>
            </span>
            <div>
              <h2>全周期资料管理</h2>
              <p>统一归档与快速检索，让企业资料流转清晰有序</p>
            </div>
          </article>

          <article class="login-page__feature">
            <span class="login-page__feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M12 3.25 19 6v5.3c0 4.35-2.9 7.9-7 9.45-4.1-1.55-7-5.1-7-9.45V6l7-2.75Z" />
                <path d="m8.85 12.05 2.05 2.05 4.45-4.45" />
              </svg>
            </span>
            <div>
              <h2>安全合规防护</h2>
              <p>权限分级与全程留痕，守护企业关键资料安全</p>
            </div>
          </article>

          <article class="login-page__feature">
            <span class="login-page__feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M12 3.25 13.45 8l4.8 1.45-4.8 1.45L12 15.75l-1.45-4.85-4.8-1.45L10.55 8 12 3.25Z" />
                <path d="m18.2 14.4.75 2.45 2.3.7-2.3.7-.75 2.5-.75-2.5-2.3-.7 2.3-.7.75-2.45Z" />
              </svg>
            </span>
            <div>
              <h2>Agent 智能协同</h2>
              <p>智能理解业务需求，辅助内容生成与团队协作提效</p>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section class="login-page__panel" aria-labelledby="login-title">
      <div class="login-page__brand">
        <img
          class="login-page__brand-mark"
          :src="appConfig.logoUrl"
          alt="绿能信盾企业 Logo"
        />
        <h1 id="login-title">欢迎使用本系统！</h1>
      </div>

      <el-form class="login-page__form" :model="form" @submit.prevent="submitLogin">
        <el-form-item>
          <label class="login-page__label" for="login-username">账号</label>
          <el-input
            id="login-username"
            v-model="form.username"
            autocomplete="username"
            :prefix-icon="User"
            placeholder="请输入账号"
            size="large"
          />
        </el-form-item>

        <el-form-item>
          <label class="login-page__label" for="login-password">密码</label>
          <el-input
            id="login-password"
            v-model="form.password"
            autocomplete="current-password"
            :prefix-icon="Lock"
            placeholder="请输入您的密码"
            show-password
            size="large"
            type="password"
            @keyup.enter="submitLogin"
          />
        </el-form-item>

        <div class="login-page__assist">
          <el-checkbox
            v-model="form.remember_me"
            class="login-page__remember"
            :disabled="loading"
            title="勾选后，登录状态按系统安全策略保持 8 小时"
          >
            保持登录
          </el-checkbox>
        </div>

        <el-button
          class="login-page__submit"
          :loading="loading"
          native-type="submit"
          size="large"
          type="primary"
        >
          <span>{{ loginStep === 'password' ? '正在登录' : '进入系统' }}</span>
          <span v-if="!loading" class="login-page__submit-icon" aria-hidden="true">
            <el-icon><ArrowRight /></el-icon>
          </span>
        </el-button>

        <p id="account-help" class="login-page__account-help">
          <el-icon aria-hidden="true"><InfoFilled /></el-icon>
          <span>如需开通账号，请联系系统管理员</span>
        </p>
      </el-form>
    </section>
  </main>
</template>
