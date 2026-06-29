<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { DocumentItem, DocumentMovePayload, FolderTreeNode } from '../documents.types'
import { flattenDocumentTargetFolderOptions } from '../utils/folders'

const props = defineProps<{
  modelValue: boolean
  document: DocumentItem | null
  folders: FolderTreeNode[]
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: DocumentMovePayload]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const folderOptions = computed(() => flattenDocumentTargetFolderOptions(props.folders))
const folder = ref<number>()

watch(
  () => [props.modelValue, props.document] as const,
  ([opened, document]) => {
    if (opened) {
      folder.value =
        document && folderOptions.value.some((option) => option.id === document.folder)
          ? document.folder
          : undefined
    }
  },
)

function submit(): void {
  if (!props.document || !folder.value) {
    return
  }

  emit('submit', {
    folder: folder.value,
    expected_updated_at: props.document.updated_at,
  })
}
</script>

<template>
  <el-dialog v-model="visible" title="移动资料" width="480px">
    <el-form label-width="88px">
      <el-form-item label="目标目录" required>
        <el-select v-model="folder" filterable placeholder="选择目标目录">
          <el-option
            v-for="item in folderOptions"
            :key="item.id"
            :label="item.label"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :disabled="!folder" :loading="loading" type="primary" @click="submit">
        移动
      </el-button>
    </template>
  </el-dialog>
</template>
