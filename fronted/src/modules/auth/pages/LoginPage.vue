<script setup lang="ts">
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
const loginStep = ref<'idle' | 'password' | 'webauthn'>('idle')
const form = reactive({
  username: '',
  password: '',
})

async function submitLogin(): Promise<void> {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  loginStep.value = 'password'

  try {
    window.setTimeout(() => {
      if (loading.value) {
        loginStep.value = 'webauthn'
      }
    }, 300)
    const user = await authStore.login({
      username: form.username,
      password: form.password,
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
  <main class="login-page">
    <section class="login-page__panel" aria-labelledby="login-title">
      <div class="login-page__brand">
        <img
          class="login-page__brand-mark"
          :src="appConfig.logoUrl"
          alt=""
          aria-hidden="true"
        />
        <div>
          <!-- <p>Wind Document System</p> -->
          <h1 id="login-title">绿能信盾资料管理系统</h1>
        </div>
      </div>

      <el-form class="login-page__form" :model="form" @submit.prevent="submitLogin">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            autocomplete="username"
            placeholder="请输入用户名/手机号"
            size="large"
          />
        </el-form-item>

        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            autocomplete="current-password"
            placeholder="请输入您的密码"
            show-password
            size="large"
            type="password"
            @keyup.enter="submitLogin"
          />
        </el-form-item>

        <el-button
          class="login-page__submit"
          :loading="loading"
          native-type="submit"
          size="large"
          type="primary"
        >
          {{ loginStep === 'webauthn' ? '等待本人验证' : '登录' }}
        </el-button>
      </el-form>
    </section>
  </main>
</template>
