<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, watch } from 'vue'

import type { UserRole } from '@/modules/auth'
import type { SystemUser, UserCreatePayload, UserPayload } from '../users.types'

const props = defineProps<{
  modelValue: boolean
  user?: SystemUser | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: UserCreatePayload | UserPayload]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive<UserCreatePayload>({
  username: '',
  password: '',
  real_name: '',
  employee_no: null,
  role: 'data_operator',
  phone: '',
  email: '',
  is_active: true,
  must_change_password: true,
})

const isEdit = computed(() => Boolean(props.user))
const title = computed(() => {
  if (isEdit.value) {
    return '编辑用户'
  }
  return '创建用户'
})

watch(
  () => [props.modelValue, props.user] as const,
  () => {
    if (!props.modelValue) {
      return
    }

    form.username = props.user?.username ?? ''
    form.password = ''
    form.real_name = props.user?.real_name ?? ''
    form.employee_no = props.user?.employee_no ?? null
    form.role = props.user?.role ?? 'data_operator'
    form.phone = props.user?.phone ?? ''
    form.email = props.user?.email ?? ''
    form.is_active = props.user?.is_active ?? true
    form.must_change_password = props.user?.must_change_password ?? true
  },
  { immediate: true },
)

function submit(): void {
  if (!form.username.trim() || !form.real_name.trim()) {
    ElMessage.warning('请填写用户名和真实姓名')
    return
  }

  if (!isEdit.value && form.password.length < 8) {
    ElMessage.warning('初始密码至少 8 位')
    return
  }

  const payload: UserPayload = {
    username: form.username.trim(),
    real_name: form.real_name.trim(),
    employee_no: form.employee_no?.trim() || null,
    role: form.role,
    phone: form.phone.trim(),
    email: form.email.trim(),
    is_active: form.is_active,
    must_change_password: form.must_change_password,
  }

  if (isEdit.value) {
    emit('submit', payload)
    return
  }

  emit('submit', {
    ...payload,
    password: form.password,
  })
}

const roleOptions = computed<Array<{ label: string; value: UserRole }>>(() => {
  const options: Array<{ label: string; value: UserRole }> = [
    { label: '系统管理员', value: 'system_admin' },
    { label: '资料整理员', value: 'data_operator' },
  ]

  if (props.user?.role === 'temporary_user') {
    options.push({ label: '临时用户', value: 'temporary_user' })
  } else if (props.user?.role === 'project_manager') {
    options.push({ label: '项目负责人', value: 'project_manager' })
  }

  return options
})
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="title" width="560px">
    <el-form class="user-dialog-form" label-width="96px">
      <el-form-item label="用户名" required>
        <el-input v-model="form.username" maxlength="150" />
      </el-form-item>

      <el-form-item v-if="!isEdit" label="初始密码" required>
        <el-input v-model="form.password" show-password type="password" />
      </el-form-item>

      <el-form-item label="真实姓名" required>
        <el-input v-model="form.real_name" maxlength="80" />
      </el-form-item>

      <el-form-item label="员工编号">
        <el-input v-model="form.employee_no" maxlength="50" />
      </el-form-item>

      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option
            v-for="item in roleOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="手机号">
        <el-input v-model="form.phone" maxlength="30" />
      </el-form-item>

      <el-form-item label="邮箱">
        <el-input v-model="form.email" />
      </el-form-item>

      <el-form-item label="账号状态">
        <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
      </el-form-item>

      <el-form-item label="改密要求">
        <el-switch
          v-model="form.must_change_password"
          active-text="下次登录修改密码"
          inactive-text="不强制"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button :loading="loading" type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
