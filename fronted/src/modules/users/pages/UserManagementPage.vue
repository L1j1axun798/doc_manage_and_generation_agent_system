<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import type { ApiPage } from '@/shared/types/api.types'
import {
  createUser,
  disableUser,
  fetchUser,
  fetchUsers,
  resetUserPassword,
  updateUser,
} from '../api/users.api'
import ResetPasswordDialog from '../components/ResetPasswordDialog.vue'
import UserDetailDrawer from '../components/UserDetailDrawer.vue'
import UserFormDialog from '../components/UserFormDialog.vue'
import UserTable from '../components/UserTable.vue'
import type { ResetPasswordPayload, SystemUser, UserCreatePayload, UserPayload } from '../users.types'

const users = ref<SystemUser[]>([])
const total = ref(0)
const page = ref(1)
const search = ref('')
const loading = ref(false)
const mutationLoading = ref(false)
const formVisible = ref(false)
const detailVisible = ref(false)
const resetVisible = ref(false)
const editingUser = ref<SystemUser | null>(null)
const selectedUser = ref<SystemUser | null>(null)
const resetUser = ref<SystemUser | null>(null)
const temporaryPassword = ref('')

onMounted(loadUsers)

async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    const response: ApiPage<SystemUser> = await fetchUsers({
      page: page.value,
      search: search.value,
      ordering: 'id',
    })
    users.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function submitSearch(): void {
  page.value = 1
  void loadUsers()
}

function resetSearch(): void {
  search.value = ''
  submitSearch()
}

function openCreate(): void {
  editingUser.value = null
  formVisible.value = true
}

function openEdit(user: SystemUser): void {
  editingUser.value = user
  formVisible.value = true
}

async function openDetail(user: SystemUser): Promise<void> {
  selectedUser.value = user
  detailVisible.value = true
  try {
    selectedUser.value = await fetchUser(user.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function submitUser(payload: UserCreatePayload | UserPayload): Promise<void> {
  mutationLoading.value = true
  try {
    if (editingUser.value) {
      await updateUser(editingUser.value.id, payload)
      ElMessage.success('用户已修改')
    } else {
      await createUser(payload as UserCreatePayload)
      ElMessage.success('用户已创建')
    }
    formVisible.value = false
    await loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function disableCurrentUser(user: SystemUser): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认停用用户“${user.real_name || user.username}”？`, '停用用户', {
      confirmButtonText: '停用',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  mutationLoading.value = true
  try {
    await disableUser(user.id)
    ElMessage.success('用户已停用')
    await loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

function openResetPassword(user: SystemUser): void {
  resetUser.value = user
  temporaryPassword.value = ''
  resetVisible.value = true
}

async function submitResetPassword(newPassword?: string): Promise<void> {
  if (!resetUser.value) {
    return
  }

  const payload: ResetPasswordPayload = {}
  if (newPassword) {
    payload.new_password = newPassword
  }

  mutationLoading.value = true
  try {
    const response = await resetUserPassword(resetUser.value.id, payload)
    temporaryPassword.value = response.temporary_password
    ElMessage.success('密码已重置')
    await loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}
</script>

<template>
  <section class="user-page">
    <header class="user-page__header">
      <div>
        <h1>用户管理</h1>
        <p>维护系统账号、角色、状态和首次登录改密要求。</p>
      </div>
      <div class="user-page__header-actions">
        <el-button type="primary" @click="openCreate">创建用户</el-button>
      </div>
    </header>

    <section class="user-page__search">
      <el-input v-model="search" clearable placeholder="搜索用户名、姓名、工号或邮箱" @keyup.enter="submitSearch" />
      <el-button :loading="loading" type="primary" @click="submitSearch">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </section>

    <UserTable
      :loading="loading || mutationLoading"
      :users="users"
      @disable="disableCurrentUser"
      @edit="openEdit"
      @reset-password="openResetPassword"
      @view="openDetail"
    />

    <footer class="user-page__pagination">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="20"
        :total="total"
        @current-change="(nextPage: number) => { page = nextPage; void loadUsers() }"
      />
    </footer>

    <UserFormDialog
      v-model="formVisible"
      :loading="mutationLoading"
      :user="editingUser"
      @submit="submitUser"
    />

    <UserDetailDrawer v-model="detailVisible" :user="selectedUser" />

    <ResetPasswordDialog
      v-model="resetVisible"
      :loading="mutationLoading"
      :temporary-password="temporaryPassword"
      @submit="submitResetPassword"
    />
  </section>
</template>
