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
const file = ref<File | null>(null)
const form = reactive({
  folder: resolveInitialFolderId(),
  title: '',
  description: '',
})

watch(
  () => props.modelValue,
  (opened) => {
    if (opened) {
      form.folder = resolveInitialFolderId()
      file.value = null
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
  file.value = input.files?.[0] ?? null
}

function submit(): void {
  if (!form.folder || !file.value) {
    return
  }

  emit('submit', {
    folder: form.folder,
    file: file.value,
    title: form.title,
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
        <input type="file" @change="handleFileChange" />
      </el-form-item>
      <el-form-item label="标题">
        <el-input v-model="form.title" placeholder="不填则以后端规则处理" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" :rows="3" type="textarea" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :disabled="!form.folder || !file" :loading="loading" type="primary" @click="submit">
        上传
      </el-button>
    </template>
  </el-dialog>
</template>
