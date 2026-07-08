<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { fetchUsers } from '@/modules/users/api/users.api'
import type { SystemUser } from '@/modules/users/users.types'
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
const userOptions = ref<SystemUser[]>([])
const userLoading = ref(false)
const form = reactive({
  user: undefined as number | undefined,
  role: 'viewer' as ProjectMemberRole,
  can_manage_folder: false,
  can_delete: false,
  can_restore: false,
})

watch(
  () => [props.modelValue, props.member] as const,
  ([opened, member]) => {
    if (!opened) {
      return
    }
    form.user = member?.user
    form.role = member?.role || 'viewer'
    form.can_manage_folder = member?.can_manage_folder || false
    form.can_delete = member?.can_delete || false
    form.can_restore = member?.can_restore || false
    if (member) {
      userOptions.value = [
        {
          id: member.user,
          username: member.user_username,
          real_name: member.user_real_name,
          employee_no: null,
          role: 'data_operator',
          phone: '',
          email: '',
          is_active: true,
          must_change_password: false,
          webauthn_enabled: true,
          webauthn_credentials_count: 1,
          created_at: '',
        },
      ]
    } else {
      userOptions.value = []
    }
  },
  { immediate: true },
)

async function searchUsers(keyword: string): Promise<void> {
  const search = keyword.trim()
  if (!visible.value || props.member || search.length < 1) {
    userOptions.value = []
    return
  }

  userLoading.value = true
  try {
    const response = await fetchUsers({
      search,
      ordering: 'real_name',
    })
    userOptions.value = response.results.filter((user) => user.is_active)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    userLoading.value = false
  }
}

function formatUserOption(user: SystemUser): string {
  const phone = user.phone ? ` / ${user.phone}` : ''
  return `${user.real_name || user.username}${phone}`
}

function submit(): void {
  emit('submit', {
    user: form.user,
    role: form.role,
    can_manage_folder: form.can_manage_folder,
    can_delete: form.can_delete,
    can_restore: form.can_restore,
  })
}
</script>

<template>
  <el-dialog v-model="visible" :title="member ? '修改成员' : '添加成员'" width="560px">
    <el-form class="document-dialog-form" :model="form" label-width="92px">
      <el-form-item label="用户" required>
        <el-select
          v-model="form.user"
          :disabled="Boolean(member)"
          :loading="userLoading"
          clearable
          filterable
          placeholder="输入姓名或手机号检索"
          remote
          :remote-method="searchUsers"
        >
          <el-option
            v-for="user in userOptions"
            :key="user.id"
            :label="formatUserOption(user)"
            :value="user.id"
          >
            <span>{{ user.real_name || user.username }}</span>
            <span class="project-member-dialog__user-meta">
              {{ user.phone || user.username }}
            </span>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="项目角色">
        <el-select v-model="form.role">
          <el-option label="负责人" value="manager" />
          <el-option label="资料整理员" value="operator" />
          <el-option label="查看者" value="viewer" />
        </el-select>
      </el-form-item>
      <el-form-item label="项目权限">
        <el-checkbox v-model="form.can_manage_folder">管理文件夹</el-checkbox>
        <el-checkbox v-model="form.can_delete">删除</el-checkbox>
        <el-checkbox v-model="form.can_restore">恢复</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :disabled="!form.user" :loading="loading" type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.project-member-dialog__user-meta {
  float: right;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
