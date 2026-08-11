<script setup lang="ts">
import { ElMessageBox } from 'element-plus'
import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import {
  consumePendingSessionReplacement,
  SESSION_REPLACED_EVENT,
} from '@/core/http/session-events'
import { fetchCurrentUser } from '@/modules/auth/api/auth.api'
import { useAuthStore } from '@/modules/auth/stores/auth.store'

const SESSION_CHECK_INTERVAL_MS = 10_000
const authStore = useAuthStore()
const router = useRouter()
let sessionCheckTimer: number | null = null
let sessionCheckRunning = false
let replacementDialogOpen = false

async function checkCurrentSession(): Promise<void> {
  if (!authStore.isAuthenticated || sessionCheckRunning) {
    return
  }

  sessionCheckRunning = true
  try {
    await fetchCurrentUser()
  } catch {
    // The global response interceptor handles a replaced session. Transient
    // network failures must not force an otherwise valid user to log out.
  } finally {
    sessionCheckRunning = false
  }
}

async function handleSessionReplaced(): Promise<void> {
  if (replacementDialogOpen) {
    return
  }

  replacementDialogOpen = true
  authStore.clearLocalSession()
  try {
    await ElMessageBox.alert(
      '您的账号已在其他设备或浏览器重新登录，当前登录已下线。',
      '账号已下线',
      {
        confirmButtonText: '重新登录',
        type: 'warning',
        showClose: false,
        closeOnClickModal: false,
        closeOnPressEscape: false,
      },
    )
  } finally {
    await router.replace({
      name: 'login',
      query: { reason: 'session_replaced' },
    })
    replacementDialogOpen = false
  }
}

function onSessionReplaced(): void {
  consumePendingSessionReplacement()
  void handleSessionReplaced()
}

function onVisibilityChange(): void {
  if (document.visibilityState === 'visible') {
    void checkCurrentSession()
  }
}

onMounted(() => {
  window.addEventListener(SESSION_REPLACED_EVENT, onSessionReplaced)
  window.addEventListener('focus', checkCurrentSession)
  document.addEventListener('visibilitychange', onVisibilityChange)
  sessionCheckTimer = window.setInterval(() => {
    void checkCurrentSession()
  }, SESSION_CHECK_INTERVAL_MS)

  if (consumePendingSessionReplacement()) {
    void handleSessionReplaced()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener(SESSION_REPLACED_EVENT, onSessionReplaced)
  window.removeEventListener('focus', checkCurrentSession)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  if (sessionCheckTimer !== null) {
    window.clearInterval(sessionCheckTimer)
  }
})
</script>

<template>
  <RouterView />
</template>
