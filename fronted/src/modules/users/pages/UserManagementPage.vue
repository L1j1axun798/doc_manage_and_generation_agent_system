<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { createWebAuthnEnrollmentTicket } from '@/modules/auth/api/auth.api'
import type { ApiPage } from '@/shared/types/api.types'
import {
  createUser,
  disableUser,
  fetchUser,
  fetchUsers,
  resetUserPassword,
  resetUserWebAuthn,
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
const webauthnTicketVisible = ref(false)
const webauthnTicketUrl = ref('')
const webauthnTicketExpiresAt = ref('')

onMounted(loadUsers)

async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    const response: ApiPage<SystemUser> = await fetchUsers({
      page: page.value,
      search: search.value,
      ordering: '-is_active,id',
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

async function createWebauthnTicket(user: SystemUser): Promise<void> {
  mutationLoading.value = true
  try {
    const response = await createWebAuthnEnrollmentTicket(user.id)
    webauthnTicketUrl.value = `${window.location.origin}/webauthn/register?ticket=${encodeURIComponent(response.token)}`
    webauthnTicketExpiresAt.value = response.expires_at
    webauthnTicketVisible.value = true
    ElMessage.success('本人验证绑定链接已生成')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function resetWebauthn(user: SystemUser): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认重置用户“${user.real_name || user.username}”的本人验证设备？`,
      '重置本人验证',
      {
        confirmButtonText: '重置',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  mutationLoading.value = true
  try {
    const response = await resetUserWebAuthn(user.id)
    ElMessage.success(`已撤销 ${response.revoked_credentials} 个本人验证设备`)
    await loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function copyWebauthnTicketUrl(): Promise<void> {
  try {
    await navigator.clipboard.writeText(webauthnTicketUrl.value)
    ElMessage.success('绑定链接已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制绑定链接')
  }
}
</script>

<template>
  <section class="user-page">
    <header class="user-page__header page-action-bar">
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
      @create-webauthn-ticket="createWebauthnTicket"
      @disable="disableCurrentUser"
      @edit="openEdit"
      @reset-password="openResetPassword"
      @reset-webauthn="resetWebauthn"
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

    <el-dialog v-model="webauthnTicketVisible" title="本人验证绑定链接" width="560px">
      <el-form label-width="92px">
        <el-form-item label="有效期至">
          {{ webauthnTicketExpiresAt }}
        </el-form-item>
        <el-form-item label="绑定链接">
          <el-input v-model="webauthnTicketUrl" readonly>
            <template #append>
              <el-button @click="copyWebauthnTicketUrl">复制</el-button>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
    </el-dialog>
  </section>
</template>
