<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type { DocumentUploadPayload, FolderTreeNode } from '../documents.types'
import { flattenDocumentTargetFolderOptions } from '../utils/folders'

const props = defineProps<{
  modelValue: boolean
  folders: FolderTreeNode[]
  initialFolderId?: number
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: DocumentUploadPayload]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const folderOptions = computed(() => flattenDocumentTargetFolderOptions(props.folders))
const fileInputRef = ref<HTMLInputElement>()
const files = ref<File[]>([])
const lastUploadedFileNames = ref<string[]>([])
const form = reactive({
  folder: resolveInitialFolderId(),
  title: '',
  description: '',
})
const isMultiFile = computed(() => files.value.length > 1)
const selectedFileText = computed(() =>
  files.value.length > 0 ? files.value.map((item) => item.name).join('、') : '点击选择或拖入文件',
)
const lastUploadedFileText = computed(() => lastUploadedFileNames.value.join('、'))

watch(
  () => props.modelValue,
  (opened) => {
    if (opened) {
      form.folder = resolveInitialFolderId()
      files.value = []
      resetFileInput()
    }
  },
)

function resolveInitialFolderId(): number | undefined {
  if (!props.initialFolderId) {
    return undefined
  }
  return folderOptions.value.some((option) => option.id === props.initialFolderId)
    ? props.initialFolderId
    : undefined
}

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
  if (!form.folder || files.value.length === 0) {
    return
  }

  lastUploadedFileNames.value = files.value.map((item) => item.name)
  emit('submit', {
    folder: form.folder,
    files: files.value,
    title: isMultiFile.value ? '' : form.title,
    description: form.description,
  })
}
</script>

<template>
  <el-dialog v-model="visible" title="上传资料" width="520px">
    <el-form class="document-dialog-form" :model="form" label-width="88px">
      <el-form-item label="目录" required>
        <el-select v-model="form.folder" filterable placeholder="选择目录">
          <el-option
            v-for="folder in folderOptions"
            :key="folder.id"
            :label="folder.label"
            :value="folder.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="文件" required>
        <label class="document-upload-dropzone" @dragover.prevent @drop.prevent="handleDrop">
          <input ref="fileInputRef" multiple type="file" @change="handleFileChange" />
          <span>{{ selectedFileText }}</span>
        </label>
      </el-form-item>
      <el-form-item label="标题">
        <el-input
          v-model="form.title"
          :disabled="isMultiFile"
          :placeholder="isMultiFile ? '多文件上传时使用文件名' : '不填则以后端规则处理'"
        />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" :rows="3" type="textarea" />
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="document-upload-footer">
        <span v-if="lastUploadedFileText" class="document-upload-footer__last">
          上次：{{ lastUploadedFileText }}
        </span>
        <div class="document-upload-footer__actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button
            :disabled="!form.folder || files.length === 0"
            :loading="loading"
            type="primary"
            @click="submit"
          >
            上传
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>
