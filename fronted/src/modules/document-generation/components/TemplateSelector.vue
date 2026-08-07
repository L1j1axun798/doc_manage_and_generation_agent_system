<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { DocumentGenerationTemplate } from '../document-generation.types'

const props = defineProps<{
  modelValue: boolean
  templates: DocumentGenerationTemplate[]
  selectedId: number | null
  uploading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  select: [templateId: number | null]
  upload: [file: File]
}>()

const search = ref('')
const draftSelectedId = ref<number | null>(null)
const fileInput = ref<HTMLInputElement>()
const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const filteredTemplates = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  if (!keyword) return props.templates
  return props.templates.filter((template) =>
    `${template.display_name} ${template.client_name} ${template.filename}`
      .toLowerCase()
      .includes(keyword),
  )
})

watch(
  () => props.modelValue,
  (opened) => {
    if (opened) {
      draftSelectedId.value = props.selectedId
      search.value = ''
    }
  },
)

function confirm(): void {
  emit('select', draftSelectedId.value)
  visible.value = false
}

function removeSelection(): void {
  draftSelectedId.value = null
  emit('select', null)
  visible.value = false
}

function handleFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('upload', file)
  input.value = ''
}
</script>

<template>
  <el-dialog v-model="visible" title="选择甲方模板" width="min(720px, 94vw)" destroy-on-close>
    <el-alert
      title="普通用户和管理员均可自主选择或上传甲方提供的 DOCX 模板，无需审核即可用于生成；当前项目存在“入场前置资料”目录时会自动同步。"
      type="info"
      :closable="false"
      show-icon
    />
    <div class="template-selector__toolbar">
      <el-input v-model="search" clearable placeholder="搜索模板名称、甲方或文件名" />
      <input
        ref="fileInput"
        class="template-selector__file-input"
        type="file"
        accept=".docx"
        @change="handleFile"
      />
      <el-button :loading="uploading" @click="fileInput?.click()">上传甲方模板</el-button>
    </div>

    <el-radio-group v-if="filteredTemplates.length" v-model="draftSelectedId" class="template-selector__list">
      <el-radio
        v-for="template in filteredTemplates"
        :key="template.id"
        :value="template.id"
        class="template-selector__item"
      >
        <span class="template-selector__copy">
          <strong>{{ template.display_name }}</strong>
          <small>{{ template.client_name || '通用甲方' }} · {{ template.version }} · {{ template.filename }}</small>
        </span>
      </el-radio>
    </el-radio-group>
    <el-empty v-else :image-size="72" description="没有匹配的可用模板" />

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button v-if="selectedId" @click="removeSelection">移除当前模板</el-button>
      <el-button type="primary" :disabled="!draftSelectedId" @click="confirm">确认使用</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.template-selector__toolbar {
  display: grid;
  margin: 18px 0 12px;
  gap: 10px;
  grid-template-columns: minmax(0, 1fr) auto;
}

.template-selector__file-input {
  display: none;
}

.template-selector__list {
  display: grid;
  height: 330px;
  max-height: 330px;
  overflow-y: auto;
  align-content: start;
  gap: 8px;
  scrollbar-gutter: stable;
}

.template-selector__item {
  width: 100%;
  height: auto;
  min-height: 62px;
  margin-right: 0;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.template-selector__item.is-checked {
  border-color: var(--color-brand);
  background: var(--color-brand-soft);
}

.template-selector__copy {
  display: grid;
  min-width: 0;
  gap: 4px;
  white-space: normal;
}

.template-selector__copy small {
  overflow: hidden;
  color: var(--color-text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .template-selector__toolbar {
    grid-template-columns: 1fr;
  }

  .template-selector__list {
    height: 280px;
    max-height: 40vh;
  }
}
</style>
