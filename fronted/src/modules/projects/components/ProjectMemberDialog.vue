<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import type { ProjectMember, ProjectMemberPayload, ProjectMemberRole } from '../projects.types'

const props = defineProps<{
  modelValue: boolean
  member?: ProjectMember | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: ProjectMemberPayload]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const form = reactive({
  user: undefined as number | undefined,
  role: 'viewer' as ProjectMemberRole,
  can_upload: false,
  can_download_restricted: false,
  can_manage_folder: false,
  can_delete: false,
  can_restore: false,
  can_manage_permission: false,
})

watch(
  () => [props.modelValue, props.member] as const,
  ([opened, member]) => {
    if (!opened) {
      return
    }
    form.user = member?.user
    form.role = member?.role || 'viewer'
    form.can_upload = member?.can_upload || false
    form.can_download_restricted = member?.can_download_restricted || false
    form.can_manage_folder = member?.can_manage_folder || false
    form.can_delete = member?.can_delete || false
    form.can_restore = member?.can_restore || false
    form.can_manage_permission = member?.can_manage_permission || false
  },
  { immediate: true },
)

function submit(): void {
  emit('submit', {
    user: form.user,
    role: form.role,
    can_upload: form.can_upload,
    can_download_restricted: form.can_download_restricted,
    can_manage_folder: form.can_manage_folder,
    can_delete: form.can_delete,
    can_restore: form.can_restore,
    can_manage_permission: form.can_manage_permission,
  })
}
</script>

<template>
  <el-dialog v-model="visible" :title="member ? '修改成员' : '添加成员'" width="560px">
    <el-form class="document-dialog-form" :model="form" label-width="92px">
      <el-form-item label="用户ID" required>
        <el-input-number v-model="form.user" :disabled="Boolean(member)" :min="1" controls-position="right" />
      </el-form-item>
      <el-form-item label="项目角色">
        <el-select v-model="form.role">
          <el-option label="负责人" value="manager" />
          <el-option label="资料整理员" value="operator" />
          <el-option label="查看者" value="viewer" />
        </el-select>
      </el-form-item>
      <el-form-item label="项目权限">
        <el-checkbox v-model="form.can_upload">上传</el-checkbox>
        <el-checkbox v-model="form.can_download_restricted">下载受限文件</el-checkbox>
        <el-checkbox v-model="form.can_manage_folder">管理文件夹</el-checkbox>
        <el-checkbox v-model="form.can_delete">删除</el-checkbox>
        <el-checkbox v-model="form.can_restore">恢复</el-checkbox>
        <el-checkbox v-model="form.can_manage_permission">管理授权</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :disabled="!form.user" :loading="loading" type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
