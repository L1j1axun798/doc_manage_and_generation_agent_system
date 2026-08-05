<script setup lang="ts">
import type {
  AgentPersonnelContext,
  ClientTemplateCandidate,
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
  candidates?: ClientTemplateCandidate[]
  editable?: boolean
}>()

const emit = defineEmits<{
  template: []
  personnel: []
  sources: []
  removeTemplate: []
  removePersonnel: [personnelId: string]
  removeSource: [versionId: number]
  removeCandidate: [versionId: number]
}>()
</script>

<template>
  <div class="context-attachment-bar">
    <div class="context-attachment-bar__items">
      <el-tag
        v-if="template || templateName"
        type="primary"
        :closable="editable"
        effect="light"
        @close="emit('removeTemplate')"
      >
        模板：{{ template?.display_name || templateName }}
      </el-tag>
      <button v-else class="context-attachment-bar__missing" type="button" @click="emit('template')">
        尚未选择甲方模板
      </button>
      <el-tag
        v-for="person in personnel"
        :key="person.id"
        :closable="editable"
        type="info"
        @close="emit('removePersonnel', person.id)"
      >
        {{ person.name }}{{ person.job_title ? ` · ${person.job_title}` : '' }}
      </el-tag>
      <el-tag
        v-for="candidate in candidates || []"
        :key="candidate.document_version_id"
        type="warning"
        :closable="editable"
        @close="emit('removeCandidate', candidate.document_version_id)"
      >
        待登记模板：{{ candidate.filename }}
      </el-tag>
      <el-tag
        v-for="source in sources"
        :key="source.document_version_id"
        :closable="editable"
        type="info"
        effect="plain"
        @close="emit('removeSource', source.document_version_id)"
      >
        资料：{{ source.filename || source.title }}
      </el-tag>
      <el-button link type="primary" @click="emit('sources')">
        参考资料 {{ sourceCount }}/{{ maxSourceCount }} 份
      </el-button>
    </div>
    <div v-if="template || templateName" class="context-attachment-bar__lock">
      <span aria-hidden="true">✓</span>
      本次生成将严格使用当前模板，锁定章节、标题层级、表格和版式
    </div>
  </div>
</template>

<style scoped>
.context-attachment-bar {
  display: grid;
  gap: 8px;
}

.context-attachment-bar__items {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 7px;
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
  color: var(--color-success);
  font-size: 12px;
  line-height: 1.5;
}
</style>
