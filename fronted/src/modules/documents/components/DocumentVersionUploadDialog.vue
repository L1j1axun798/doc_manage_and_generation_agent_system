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
  submit: [files: File[]]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const fileInputRef = ref<HTMLInputElement>()
const files = ref<File[]>([])
const lastUploadedFileNames = ref<string[]>([])
const selectedFileText = computed(() =>
  files.value.length > 0 ? files.value.map((item) => item.name).join('、') : '点击选择或拖入文件',
)
const lastUploadedFileText = computed(() => lastUploadedFileNames.value.join('、'))

watch(
  () => props.modelValue,
  (opened) => {
    if (opened) {
      files.value = []
      resetFileInput()
    }
  },
)

function handleFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  setFiles(input.files)
}

function handleDrop(event: DragEvent): void {
  setFiles(event.dataTransfer?.files)
}

function setFiles(fileList: FileList | undefined | null): void {
  files.value = Array.from(fileList ?? [])
}

function resetFileInput(): void {
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

function submit(): void {
  if (files.value.length === 0) {
    return
  }

  lastUploadedFileNames.value = files.value.map((item) => item.name)
  emit('submit', files.value)
}
</script>

<template>
  <el-dialog v-model="visible" title="上传新版本" width="480px">
    <p class="document-version-upload__title">{{ document?.title }}</p>
    <label class="document-upload-dropzone" @dragover.prevent @drop.prevent="handleDrop">
      <input ref="fileInputRef" multiple type="file" @change="handleFileChange" />
      <span>{{ selectedFileText }}</span>
    </label>
    <template #footer>
      <div class="document-upload-footer">
        <span v-if="lastUploadedFileText" class="document-upload-footer__last">
          上次：{{ lastUploadedFileText }}
        </span>
        <div class="document-upload-footer__actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button :disabled="files.length === 0" :loading="loading" type="primary" @click="submit">
            上传新版本
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>
