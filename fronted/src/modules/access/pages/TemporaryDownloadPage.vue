<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { downloadTemporaryAccess } from '../api/temporary-access.api'

const route = useRoute()
const loading = ref(false)
const token = computed(() => String(route.params.token || ''))
const isInvalidToken = computed(() => token.value.trim().length === 0)

async function download(): Promise<void> {
  if (isInvalidToken.value) {
    ElMessage.error('临时访问链接无效')
    return
  }

  loading.value = true
  try {
    await downloadTemporaryAccess(token.value)
    ElMessage.success('下载已开始')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="temporary-download-page">
    <div class="temporary-download-page__panel">
      <div class="temporary-download-page__brand">
        <span class="temporary-download-page__brand-mark">风</span>
        <div>
          <h1>临时文件下载</h1>
          <p>此链接受有效期和下载次数限制。</p>
        </div>
      </div>

      <el-alert
        v-if="isInvalidToken"
        show-icon
        title="临时访问链接无效"
        type="error"
        :closable="false"
      />

      <el-button
        :disabled="isInvalidToken"
        :loading="loading"
        size="large"
        type="primary"
        @click="download"
      >
        下载文件
      </el-button>
    </div>
  </section>
</template>
