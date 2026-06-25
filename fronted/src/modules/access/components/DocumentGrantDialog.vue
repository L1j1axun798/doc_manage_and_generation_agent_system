<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, watch } from 'vue'

import type { DocumentGrant, DocumentGrantPayload } from '../access.types'

const props = defineProps<{
  modelValue: boolean
  documentId: number
  grant?: DocumentGrant | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: DocumentGrantPayload]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive<DocumentGrantPayload>({
  document: props.documentId,
  user: 0,
  can_view: true,
  can_download: false,
  can_update: false,
  can_delete: false,
  can_restore: false,
  can_manage: false,
  expires_at: null,
})

const title = computed(() => (props.grant ? '修改授权' : '添加授权'))
const actionFields = [
  'can_view',
  'can_download',
  'can_update',
  'can_delete',
  'can_restore',
  'can_manage',
] as const

watch(
  () => [props.modelValue, props.grant, props.documentId] as const,
  () => {
    if (!props.modelValue) {
      return
    }

    form.document = props.documentId
    form.user = props.grant?.user ?? 0
    form.can_view = props.grant?.can_view ?? true
    form.can_download = props.grant?.can_download ?? false
    form.can_update = props.grant?.can_update ?? false
    form.can_delete = props.grant?.can_delete ?? false
    form.can_restore = props.grant?.can_restore ?? false
    form.can_manage = props.grant?.can_manage ?? false
    form.expires_at = props.grant?.expires_at ?? null
  },
  { immediate: true },
)

function submit(): void {
  if (!form.user) {
    ElMessage.warning('请输入被授权用户 ID')
    return
  }

  if (!actionFields.some((field) => form[field])) {
    ElMessage.warning('至少需要授予一个权限动作')
    return
  }

  emit('submit', { ...form })
}
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="title" width="520px">
    <el-form class="access-dialog-form" label-width="104px">
      <el-form-item label="用户 ID" required>
        <el-input-number
          v-model="form.user"
          :disabled="Boolean(grant)"
          :min="1"
          :step="1"
          controls-position="right"
        />
      </el-form-item>

      <el-form-item label="权限动作" required>
        <div class="access-checkbox-grid">
          <el-checkbox v-model="form.can_view" label="可查看" />
          <el-checkbox v-model="form.can_download" label="可下载" />
          <el-checkbox v-model="form.can_update" label="可更新" />
          <el-checkbox v-model="form.can_delete" label="可删除" />
          <el-checkbox v-model="form.can_restore" label="可恢复" />
          <el-checkbox v-model="form.can_manage" label="可管理授权" />
        </div>
      </el-form-item>

      <el-form-item label="过期时间">
        <el-date-picker
          v-model="form.expires_at"
          clearable
          placeholder="不设置则长期有效"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ssZ"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button :loading="loading" type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>
