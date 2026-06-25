<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { FolderMovePayload, SystemFolder } from '../system.types'

const props = defineProps<{
  modelValue: boolean
  folder?: SystemFolder | null
  parentOptions: SystemFolder[]
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: FolderMovePayload]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive<FolderMovePayload>({
  parent: null,
  sort_order: 0,
})

const selectableParents = computed(() =>
  props.parentOptions.filter((item) => {
    if (!props.folder) {
      return true
    }
    return item.id !== props.folder.id && item.project === props.folder.project
  }),
)

watch(
  () => [props.modelValue, props.folder] as const,
  () => {
    if (!props.modelValue) {
      return
    }
    form.parent = props.folder?.parent ?? null
    form.sort_order = props.folder?.sort_order ?? 0
  },
  { immediate: true },
)

function submit(): void {
  emit('submit', {
    parent: form.parent,
    sort_order: form.sort_order,
  })
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="移动目录" width="500px">
    <el-form class="system-dialog-form" label-width="96px">
      <el-form-item label="目录">
        <span>{{ folder?.name || '-' }}</span>
      </el-form-item>

      <el-form-item label="父级目录">
        <el-select v-model="form.parent" clearable filterable placeholder="选择新的父级目录">
          <el-option
            v-for="item in selectableParents"
            :key="item.id"
            :label="`${item.name}${item.project_name ? ` / ${item.project_name}` : ' / 公共目录'}`"
            :value="item.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" controls-position="right" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button :loading="loading" type="primary" @click="submit">移动</el-button>
    </template>
  </el-dialog>
</template>
