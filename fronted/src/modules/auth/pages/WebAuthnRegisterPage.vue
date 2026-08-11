<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getErrorMessage } from '@/core/http/error-normalizer'
import SiteFooter from '@/shared/components/SiteFooter.vue'
import {
  beginWebAuthnRegistration,
  fetchCsrfToken,
  verifyWebAuthnRegistration,
} from '../api/auth.api'
import { registerWithWebAuthn } from '../services/webauthn'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const form = reactive({
  deviceName: '',
})

const ticket = computed(() => (typeof route.query.ticket === 'string' ? route.query.ticket : ''))
const canSubmit = computed(() => ticket.value.trim().length > 0 && !loading.value)

async function submitRegistration(): Promise<void> {
  if (!ticket.value) {
    ElMessage.warning('绑定链接无效')
    return
  }

  loading.value = true
  try {
    await fetchCsrfToken()
    const challenge = await beginWebAuthnRegistration({
      ticket: ticket.value,
      device_name: form.deviceName,
    })
    const credential = await registerWithWebAuthn(challenge.options)
    await verifyWebAuthnRegistration({
      ticket: ticket.value,
      challenge_token: challenge.challenge_token,
      credential,
    })
    ElMessage.success('本人验证设备已绑定')
    await router.replace('/login')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="public-page-shell">
    <main class="login-page">
      <section class="login-page__panel" aria-labelledby="webauthn-register-title">
      <div class="login-page__brand">
        <span class="login-page__brand-mark" aria-hidden="true">W</span>
        <div>
          <h1 id="webauthn-register-title">绑定本人验证设备</h1>
        </div>
      </div>

      <el-alert
        v-if="!ticket"
        :closable="false"
        title="绑定链接缺少有效票据"
        type="error"
      />

      <el-form class="login-page__form" :model="form" @submit.prevent="submitRegistration">
        <el-form-item label="设备名称">
          <el-input
            v-model="form.deviceName"
            maxlength="120"
            placeholder="例如：本人工作用手机"
            size="large"
          />
        </el-form-item>

        <el-button
          class="login-page__submit"
          :disabled="!canSubmit"
          :loading="loading"
          native-type="submit"
          size="large"
          type="primary"
        >
          绑定设备
        </el-button>
      </el-form>
      </section>
    </main>
    <SiteFooter />
  </div>
</template>
