<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { TemporaryAccessGrantPayload } from '../access.types'

const props = defineProps<{
  modelValue: boolean
  documentVersionId: number
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: TemporaryAccessGrantPayload]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive<TemporaryAccessGrantPayload>({
  document_version: props.documentVersionId,
  max_downloads: 1,
  expires_at: undefined,
})

watch(
  () => [props.modelValue, props.documentVersionId] as const,
  () => {
    if (!props.modelValue) {
      return
    }
    form.document_version = props.documentVersionId
    form.max_downloads = 1
    form.expires_at = undefined
  },
  { immediate: true },
)

function submit(): void {
  const payload: TemporaryAccessGrantPayload = {
    document_version: form.document_version,
    max_downloads: form.max_downloads,
  }
  if (form.expires_at) {
    payload.expires_at = form.expires_at
  }
  emit('submit', payload)
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="生成临时链接" width="480px">
    <el-form class="access-dialog-form" label-width="110px">
      <el-form-item label="下载次数" required>
        <el-input-number
          v-model="form.max_downloads"
          :min="1"
          :step="1"
          controls-position="right"
        />
      </el-form-item>

      <el-form-item label="过期时间">
        <el-date-picker
          v-model="form.expires_at"
          clearable
          placeholder="不设置则使用后端默认时长"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ssZ"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button :loading="loading" type="primary" @click="submit">生成</el-button>
    </template>
  </el-dialog>
</template>
