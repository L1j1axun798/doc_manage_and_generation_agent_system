<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { DocumentItem } from '../documents.types'

const props = defineProps<{
  modelValue: boolean
  document: DocumentItem | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [file: File]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const file = ref<File | null>(null)

watch(
  () => props.modelValue,
  (opened) => {
    if (opened) {
      file.value = null
    }
  },
)

function handleFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}
</script>

<template>
  <el-dialog v-model="visible" title="上传新版本" width="480px">
    <p class="document-version-upload__title">{{ document?.title }}</p>
    <input type="file" @change="handleFileChange" />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :disabled="!file" :loading="loading" type="primary" @click="file && emit('submit', file)">
        上传新版本
      </el-button>
    </template>
  </el-dialog>
</template>
