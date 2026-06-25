<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { Project, ProjectPayload } from '../projects.types'

const props = defineProps<{
  modelValue: boolean
  project?: Project | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: ProjectPayload]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const form = reactive({
  name: '',
  code: '',
  description: '',
  manager: undefined as number | undefined,
})

watch(
  () => [props.modelValue, props.project] as const,
  ([opened, project]) => {
    if (!opened) {
      return
    }
    form.name = project?.name || ''
    form.code = project?.code || ''
    form.description = project?.description || ''
    form.manager = project?.manager || undefined
  },
  { immediate: true },
)

function submit(): void {
  emit('submit', {
    name: form.name,
    code: form.code,
    description: form.description,
    manager: form.manager || null,
  })
}
</script>

<template>
  <el-dialog v-model="visible" :title="project ? '修改项目' : '创建项目'" width="520px">
    <el-form class="document-dialog-form" :model="form" label-width="88px">
      <el-form-item label="项目名称" required>
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="项目编号" required>
        <el-input v-model="form.code" :disabled="Boolean(project)" />
      </el-form-item>
      <el-form-item label="负责人ID">
        <el-input-number v-model="form.manager" :min="1" controls-position="right" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" :rows="3" type="textarea" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :disabled="!form.name || !form.code" :loading="loading" type="primary" @click="submit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
