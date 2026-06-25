<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type { DocumentAccessLevel, DocumentUploadPayload, FolderTreeNode } from '../documents.types'
import { flattenFolderOptions } from '../utils/folders'

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
const folderOptions = computed(() => flattenFolderOptions(props.folders))
const file = ref<File | null>(null)
const form = reactive({
  folder: props.initialFolderId,
  title: '',
  description: '',
  access_level: 'internal' as DocumentAccessLevel,
})

watch(
  () => props.modelValue,
  (opened) => {
    if (opened) {
      form.folder = props.initialFolderId
      file.value = null
    }
  },
)

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
    access_level: form.access_level,
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
      <el-form-item label="访问级别">
        <el-radio-group v-model="form.access_level">
          <el-radio-button value="internal">内部</el-radio-button>
          <el-radio-button value="restricted">受限</el-radio-button>
        </el-radio-group>
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
