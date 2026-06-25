<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, watch } from 'vue'

import type { FolderCreatePayload, FolderUpdatePayload, SystemFolder } from '../system.types'

const props = defineProps<{
  modelValue: boolean
  folder?: SystemFolder | null
  parentOptions: SystemFolder[]
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: FolderCreatePayload | FolderUpdatePayload]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const isEdit = computed(() => Boolean(props.folder))
const title = computed(() => (isEdit.value ? '编辑目录' : '创建目录'))

const form = reactive<FolderCreatePayload>({
  project: null,
  parent: null,
  name: '',
  code: '',
  sort_order: 0,
})

const selectableParents = computed(() => props.parentOptions.filter((item) => item.id !== props.folder?.id))

watch(
  () => [props.modelValue, props.folder] as const,
  () => {
    if (!props.modelValue) {
      return
    }

    form.project = props.folder?.project ?? null
    form.parent = props.folder?.parent ?? null
    form.name = props.folder?.name ?? ''
    form.code = props.folder?.code ?? ''
    form.sort_order = props.folder?.sort_order ?? 0
  },
  { immediate: true },
)

function submit(): void {
  if (!form.name.trim()) {
    ElMessage.warning('请填写目录名称')
    return
  }

  if (isEdit.value) {
    emit('submit', {
      name: form.name.trim(),
      code: form.code.trim(),
      sort_order: form.sort_order,
    })
    return
  }

  emit('submit', {
    project: form.project,
    parent: form.parent,
    name: form.name.trim(),
    code: form.code.trim(),
    sort_order: form.sort_order,
  })
}
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="title" width="540px">
    <el-form class="system-dialog-form" label-width="96px">
      <el-form-item v-if="!isEdit" label="所属项目">
        <el-input-number
          v-model="form.project"
          :min="1"
          clearable
          controls-position="right"
          placeholder="留空表示公共目录"
        />
      </el-form-item>

      <el-form-item v-if="!isEdit" label="父级目录">
        <el-select v-model="form.parent" clearable filterable placeholder="公共目录必须选择系统根分类">
          <el-option
            v-for="item in selectableParents"
            :key="item.id"
            :label="`${item.name}${item.project_name ? ` / ${item.project_name}` : ' / 公共目录'}`"
            :value="item.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="目录名称" required>
        <el-input v-model="form.name" maxlength="120" />
      </el-form-item>

      <el-form-item label="目录编码">
        <el-input v-model="form.code" maxlength="50" />
      </el-form-item>

      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" controls-position="right" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button :loading="loading" type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
