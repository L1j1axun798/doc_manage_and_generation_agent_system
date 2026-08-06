<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, watch } from 'vue'

import type { PersonnelRecord, PersonnelUpdatePayload } from '../system.types'

const props = defineProps<{
  modelValue: boolean
  person: PersonnelRecord | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: PersonnelUpdatePayload]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const form = reactive<PersonnelUpdatePayload>({
  gender: 'unknown',
  id_card_number: '',
  phone: '',
})

watch(
  () => [props.modelValue, props.person] as const,
  () => {
    if (!props.modelValue || !props.person) return
    form.gender = props.person.gender
    form.id_card_number = props.person.id_card_number
    form.phone = props.person.phone
  },
  { immediate: true },
)

function submit(): void {
  if (form.id_card_number && !/^\d{17}[\dXx]$/.test(form.id_card_number.trim())) {
    ElMessage.warning('身份证号应为18位，末位可以是X')
    return
  }
  if (form.phone && !/^\+?[\d\s-]{7,24}$/.test(form.phone.trim())) {
    ElMessage.warning('手机号格式不正确')
    return
  }
  emit('submit', {
    gender: form.gender,
    id_card_number: form.id_card_number.trim().toUpperCase(),
    phone: form.phone.trim(),
  })
}
</script>

<template>
  <el-dialog v-model="visible" :title="`编辑人员信息${person ? ` · ${person.name}` : ''}`" width="520px">
    <el-form label-width="92px">
      <el-form-item label="姓名">
        <el-input :model-value="person?.name || ''" disabled />
        <div class="system-dialog-help">姓名取自“资料中心 → 人员资质”下的人员目录名称。</div>
      </el-form-item>
      <el-form-item label="性别">
        <el-select v-model="form.gender" style="width: 100%">
          <el-option label="未填写" value="unknown" />
          <el-option label="男" value="male" />
          <el-option label="女" value="female" />
        </el-select>
      </el-form-item>
      <el-form-item label="身份证号">
        <el-input v-model="form.id_card_number" maxlength="18" clearable />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="form.phone" maxlength="30" clearable />
      </el-form-item>
      <el-alert
        title="这些字段会在 Agent 选择人员后写入当前任务上下文，并可发送给已配置的 LLM。"
        type="warning"
        :closable="false"
        show-icon
      />
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.system-dialog-help {
  margin-top: 4px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  line-height: 1.5;
}
</style>
