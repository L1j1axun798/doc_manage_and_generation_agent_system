<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { AvailableAgentPersonnel } from '../document-generation.types'

const props = defineProps<{
  modelValue: boolean
  personnel: AvailableAgentPersonnel[]
  selectedIds: number[]
  loading?: boolean
  error?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  confirm: [personnelIds: number[]]
  retry: []
}>()

const search = ref('')
const draftIds = ref<number[]>([])
const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const filteredPersonnel = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return props.personnel
  return props.personnel.filter((person) =>
    `${person.name} ${person.gender_display} ${person.id_card_number} ${person.phone}`
      .toLowerCase()
      .includes(keyword),
  )
})

watch(
  () => props.modelValue,
  (opened) => {
    if (opened) {
      search.value = ''
      draftIds.value = [...props.selectedIds]
    }
  },
)

function confirm(): void {
  emit('confirm', [...draftIds.value])
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" title="选择本次入场人员" width="min(720px, 94vw)" destroy-on-close>
    <el-input v-model="search" clearable placeholder="搜索姓名、岗位或部门" />
    <div v-loading="loading" class="personnel-selector__body">
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
        show-icon
      >
        <template #default><el-button link type="primary" @click="emit('retry')">重新加载</el-button></template>
      </el-alert>
      <el-checkbox-group v-else-if="filteredPersonnel.length" v-model="draftIds" class="personnel-selector__list">
        <el-checkbox
          v-for="person in filteredPersonnel"
          :key="person.folder_id"
          :value="person.folder_id"
          class="personnel-selector__item"
        >
          <span class="personnel-selector__copy">
            <strong>{{ person.name }}</strong>
            <small>
              {{ person.gender_display }} · {{ person.id_card_number || '身份证未填写' }} ·
              {{ person.phone || '手机号未填写' }}
            </small>
            <el-tag v-if="!person.profile_complete" size="small" type="warning" effect="light">资料待完善</el-tag>
          </span>
        </el-checkbox>
      </el-checkbox-group>
      <el-empty v-else-if="!loading" :image-size="72" description="“人员资质”中没有可选人员" />
    </div>
    <template #footer>
      <span class="personnel-selector__count">已选择 {{ draftIds.length }} 人</span>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="confirm">确认选择</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.personnel-selector__body {
  min-height: 260px;
  margin-top: 12px;
}

.personnel-selector__list {
  display: grid;
  max-height: 360px;
  overflow-y: auto;
  gap: 6px;
}

.personnel-selector__item {
  width: 100%;
  height: auto;
  min-height: 54px;
  margin-right: 0;
  padding: 8px 12px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.personnel-selector__item.is-checked {
  border-color: var(--color-brand);
  background: var(--color-brand-soft);
}

.personnel-selector__copy {
  display: grid;
  gap: 2px;
}

.personnel-selector__copy small,
.personnel-selector__count {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.personnel-selector__count {
  margin-right: auto;
}
</style>
