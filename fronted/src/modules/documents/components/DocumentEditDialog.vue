<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { DocumentAccessLevel, DocumentItem, DocumentUpdatePayload } from '../documents.types'

const props = defineProps<{
  modelValue: boolean
  document: DocumentItem | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: DocumentUpdatePayload]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const form = reactive({
  title: '',
  description: '',
  access_level: 'internal' as DocumentAccessLevel,
})

watch(
  () => [props.modelValue, props.document] as const,
  ([opened, document]) => {
    if (opened && document) {
      form.title = document.title
      form.description = document.description
      form.access_level = document.access_level
    }
  },
  { immediate: true },
)

function submit(): void {
  if (!props.document) {
    return
  }

  emit('submit', {
    title: form.title,
    description: form.description,
    access_level: form.access_level,
    expected_updated_at: props.document.updated_at,
  })
}
</script>

<template>
  <el-dialog v-model="visible" title="修改资料" width="520px">
    <el-form class="document-dialog-form" :model="form" label-width="88px">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" />
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
      <el-button :disabled="!form.title" :loading="loading" type="primary" @click="submit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
