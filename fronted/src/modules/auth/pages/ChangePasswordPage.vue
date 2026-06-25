<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { useAuthStore } from '../stores/auth.store'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

async function submitChangePassword(): Promise<void> {
  if (!form.old_password || !form.new_password) {
    ElMessage.warning('请输入原密码和新密码')
    return
  }

  if (form.new_password !== form.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  loading.value = true

  try {
    await authStore.changePassword({
      old_password: form.old_password,
      new_password: form.new_password,
    })
    ElMessage.success('密码已修改')
    await router.replace('/dashboard')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="change-password-page">
    <header class="change-password-page__header">
      <h1>修改密码</h1>
      <p>首次登录或重置密码后，需要先更新密码。</p>
    </header>

    <el-form class="change-password-page__form" :model="form" @submit.prevent="submitChangePassword">
      <el-form-item label="原密码">
        <el-input
          v-model="form.old_password"
          autocomplete="current-password"
          show-password
          type="password"
        />
      </el-form-item>

      <el-form-item label="新密码">
        <el-input
          v-model="form.new_password"
          autocomplete="new-password"
          show-password
          type="password"
        />
      </el-form-item>

      <el-form-item label="确认新密码">
        <el-input
          v-model="form.confirm_password"
          autocomplete="new-password"
          show-password
          type="password"
          @keyup.enter="submitChangePassword"
        />
      </el-form-item>

      <el-button :loading="loading" native-type="submit" type="primary">保存密码</el-button>
    </el-form>
  </section>
</template>
