<script setup lang="ts">
import type {
  AgentPersonnelContext,
  ConversationSourceAttachment,
  DocumentGenerationTemplate,
} from '../document-generation.types'

defineProps<{
  template: DocumentGenerationTemplate | null
  templateName?: string
  personnel: AgentPersonnelContext[]
  sources: ConversationSourceAttachment[]
  sourceCount: number
  maxSourceCount: number
  editable?: boolean
}>()

const emit = defineEmits<{
  template: []
  personnel: []
  sources: []
  removeTemplate: []
  removePersonnel: [personnelId: string]
  removeSource: [versionId: number]
}>()
</script>

<template>
  <div class="context-attachment-bar">
    <div class="context-attachment-bar__row">
      <span class="context-attachment-bar__label">模板</span>
      <div class="context-attachment-bar__items">
        <el-tag
          v-if="template || templateName"
          type="primary"
          :closable="editable"
          effect="light"
          :title="template?.display_name || templateName"
          @close="emit('removeTemplate')"
        >
          {{ template?.display_name || templateName }}
        </el-tag>
        <button v-else class="context-attachment-bar__missing" type="button" @click="emit('template')">
          尚未选择甲方模板
        </button>
        <span
          v-if="template || templateName"
          class="context-attachment-bar__lock"
          title="本次生成将严格使用当前模板，锁定章节、标题层级、表格和版式"
        >
          ✓ 本次生成将严格使用当前模板，锁定章节、标题层级、表格和版式
        </span>
      </div>
    </div>

    <div class="context-attachment-bar__row">
      <span class="context-attachment-bar__label">材料</span>
      <div class="context-attachment-bar__items">
        <el-tag
          v-for="source in sources"
          :key="source.document_version_id"
          :closable="editable"
          type="info"
          effect="plain"
          :title="source.filename || source.title"
          @close="emit('removeSource', source.document_version_id)"
        >
          {{ source.filename || source.title }}
        </el-tag>
        <el-button link type="primary" @click="emit('sources')">
          参考资料 {{ sourceCount }}/{{ maxSourceCount }} 份
        </el-button>
      </div>
    </div>

    <div class="context-attachment-bar__row">
      <span class="context-attachment-bar__label">人员</span>
      <div class="context-attachment-bar__items">
        <el-tag
          v-for="person in personnel"
          :key="person.id"
          :closable="editable"
          type="info"
          :title="person.name"
          @close="emit('removePersonnel', person.id)"
        >
          {{ person.name }}{{ person.job_title ? ` · ${person.job_title}` : '' }}
        </el-tag>
        <el-button v-if="personnel.length === 0" link type="primary" @click="emit('personnel')">
          尚未选择人员
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.context-attachment-bar {
  display: grid;
  min-width: 0;
  gap: 6px;
}

.context-attachment-bar__row {
  display: flex;
  min-width: 0;
  min-height: 28px;
  align-items: center;
  gap: 8px;
}

.context-attachment-bar__label {
  width: 34px;
  flex: 0 0 34px;
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.context-attachment-bar__items {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  overflow-x: auto;
  flex-wrap: nowrap;
  gap: 7px;
  scrollbar-width: none;
}

.context-attachment-bar__items::-webkit-scrollbar {
  display: none;
}

.context-attachment-bar__items :deep(.el-tag),
.context-attachment-bar__items :deep(.el-button) {
  flex: 0 0 auto;
}

.context-attachment-bar__items :deep(.el-tag) {
  max-width: min(420px, 70vw);
}

.context-attachment-bar__items :deep(.el-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-attachment-bar__missing {
  padding: 5px 9px;
  border: 1px dashed var(--color-warning);
  border-radius: var(--radius-sm);
  background: var(--color-warning-soft);
  color: var(--color-warning);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.context-attachment-bar__lock {
  flex: 0 0 auto;
  color: var(--color-success);
  font-size: 12px;
  white-space: nowrap;
}
</style>
