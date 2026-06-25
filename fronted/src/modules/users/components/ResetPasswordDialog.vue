<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  temporaryPassword?: string
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [newPassword?: string]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const newPassword = ref('')

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      newPassword.value = ''
    }
  },
)

function submit(): void {
  emit('submit', newPassword.value.trim() || undefined)
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="重置密码" width="480px">
    <el-alert
      v-if="temporaryPassword"
      show-icon
      title="临时密码只在本次响应中显示"
      type="success"
      :closable="false"
    >
      <el-input class="reset-password-dialog__password" :model-value="temporaryPassword" readonly />
    </el-alert>

    <el-form v-else class="user-dialog-form" label-width="120px">
      <el-form-item label="指定新密码">
        <el-input
          v-model="newPassword"
          placeholder="留空则由后端生成临时密码"
          show-password
          type="password"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button v-if="!temporaryPassword" :loading="loading" type="primary" @click="submit">
        重置
      </el-button>
    </template>
  </el-dialog>
</template>
