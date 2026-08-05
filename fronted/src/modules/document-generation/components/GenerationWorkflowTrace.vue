<script setup lang="ts">
import { computed, ref } from 'vue'

import { formatDateTime } from '@/shared/utils/format'
import type {
  GenerationTask,
  GenerationTraceEvent,
  GenerationTraceEventType,
  GenerationTraceStatus,
} from '../document-generation.types'

const props = defineProps<{
  task: GenerationTask
  events: GenerationTraceEvent[]
}>()

const detailsExpanded = ref(false)
const COLLAPSED_EVENT_COUNT = 3

const stageLabels: Record<string, string> = {
  initialized: '准备编制任务',
  parsing: '读取并解析项目资料',
  extracting_facts: '模型识别项目事实',
  validating_facts: '核验事实与来源',
  building_risk_profile: '建立项目风险画像',
  selecting_clauses: '匹配已批准条款',
  retrieving_references: 'RAG检索参考章节',
  generating_sections: '模型逐章编写',
  validating_sections: '章节规则校验',
  rendering: '生成Word版式',
  storing: '保存Word草稿',
  completed: '编制完成',
  failed: '执行失败',
  cancelled: '会话已停止',
}

const typeLabels: Record<GenerationTraceEventType, string> = {
  system: '系统',
  tool: 'Tool Use',
  model: '模型',
  rag: 'RAG',
}

const sectionLabels: Record<string, string> = {
  overview: '工程概况与编制依据',
  organization_measures: '组织措施',
  construction_plan: '施工方案',
  technical_measures: '技术措施',
  safety_measures: '安全措施',
  risk_identification: '风险辨识与预控',
  emergency_plan: '应急预案',
  environmental_measures: '环境保护与文明施工',
}

const latestEvent = computed(() => props.events.at(-1) || null)
const toolCount = computed(
  () => props.events.filter((event) => event.event_type === 'tool').length,
)
const modelCount = computed(
  () => props.events.filter((event) => event.event_type === 'model').length,
)
const ragCount = computed(
  () => props.events.filter((event) => event.event_type === 'rag').length,
)
const visibleEvents = computed(() => detailsExpanded.value
  ? props.events
  : props.events.slice(-COLLAPSED_EVENT_COUNT))

function tagType(
  status: GenerationTraceStatus,
): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'failed') {
    return 'danger'
  }
  if (status === 'succeeded') {
    return 'success'
  }
  if (status === 'started') {
    return 'primary'
  }
  return 'info'
}

function statusLabel(status: GenerationTraceStatus): string {
  return {
    started: '执行中',
    succeeded: '已完成',
    failed: '失败',
    skipped: '已复用',
  }[status]
}

function displayDetail(detail: string): string {
  const separator = detail.indexOf(':')
  const sectionCode = separator >= 0 ? detail.slice(0, separator) : detail
  const label = sectionLabels[sectionCode]
  if (!label) {
    return detail
  }
  return separator >= 0 ? `${label}：${detail.slice(separator + 1)}` : label
}
</script>

<template>
  <section class="workflow-trace" :class="{ 'is-expanded': detailsExpanded }">
    <div class="workflow-trace__heading">
      <div>
        <h3>Agent工作流</h3>
        <p>展示业务阶段、工具调用和RAG使用记录；不展示模型内部思维链。</p>
      </div>
      <el-tag
        :type="task.status === 'failed' ? 'danger' : task.status === 'cancelled' ? 'warning' : 'primary'"
        effect="plain"
      >
        {{ stageLabels[latestEvent?.stage || 'initialized'] || latestEvent?.stage }}
      </el-tag>
    </div>

    <div v-if="!detailsExpanded" class="workflow-trace__compact-meta">
      <span>{{ task.model_alias || '模型尚未调用' }}</span>
      <span>Tool {{ toolCount }}</span>
      <span>模型事件 {{ modelCount }}</span>
      <span>RAG {{ ragCount }}</span>
      <span>共 {{ events.length }} 条状态</span>
    </div>

    <div v-else class="workflow-trace__metrics">
      <div>
        <span>模型状态</span>
        <strong>{{ task.model_alias || '尚未调用模型' }}</strong>
      </div>
      <div>
        <span>Tool Use</span>
        <strong>{{ toolCount }}</strong>
      </div>
      <div>
        <span>模型调用事件</span>
        <strong>{{ modelCount }}</strong>
      </div>
      <div>
        <span>RAG事件</span>
        <strong>{{ ragCount }}</strong>
      </div>
    </div>

    <div v-if="detailsExpanded" class="workflow-trace__references">
      <el-tag effect="plain">
        当前项目事实资料 {{ task.reference_summary.project_source_files }} 份
      </el-tag>
      <el-tag type="success" effect="plain">
        已批准RAG {{ task.reference_summary.approved_rag_chunks }} 段 /
        {{ task.reference_summary.approved_rag_source_files }} 份基线文件
      </el-tag>
      <el-tag type="warning" effect="plain">
        已批准条款 {{ task.reference_summary.approved_clause_blocks }} 条
      </el-tag>
      <el-tag v-if="task.reference_summary.used_rag_citations" type="success">
        本稿采用 {{ task.reference_summary.used_rag_citations }} 条引用
      </el-tag>
    </div>

    <el-empty
      v-if="events.length === 0"
      :image-size="56"
      description="任务启动后，这里会显示实时执行轨迹"
    />
    <el-timeline v-else class="workflow-trace__timeline">
      <el-timeline-item
        v-for="event in visibleEvents"
        :key="event.sequence"
        :timestamp="formatDateTime(event.created_at)"
        placement="top"
        :type="tagType(event.status)"
        :hollow="event.status === 'started'"
      >
        <div class="workflow-trace__event">
          <div class="workflow-trace__event-title">
            <el-tag size="small" :type="event.event_type === 'rag' ? 'success' : 'info'">
              {{ typeLabels[event.event_type] }}
            </el-tag>
            <strong>{{ event.title }}</strong>
            <el-tag size="small" :type="tagType(event.status)" effect="plain">
              {{ statusLabel(event.status) }}
            </el-tag>
          </div>
          <p v-if="event.detail">{{ displayDetail(event.detail) }}</p>
          <small>{{ stageLabels[event.stage] || event.stage }} · {{ event.tool }}</small>
        </div>
      </el-timeline-item>
    </el-timeline>
    <div v-if="events.length" class="workflow-trace__expand-actions">
      <el-button
        link
        type="primary"
        :aria-expanded="detailsExpanded"
        @click="detailsExpanded = !detailsExpanded"
      >
        {{ detailsExpanded ? '收起执行详情' : `展开全部执行详情（${events.length} 条）` }}
      </el-button>
    </div>
  </section>
</template>

<style scoped>
.workflow-trace {
  padding: 18px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  margin: 18px 0;
  background: var(--el-fill-color-extra-light);
}

.workflow-trace__heading,
.workflow-trace__event-title,
.workflow-trace__references {
  display: flex;
  align-items: center;
  gap: 10px;
}

.workflow-trace__heading {
  justify-content: space-between;
}

.workflow-trace__heading h3,
.workflow-trace__heading p,
.workflow-trace__event p {
  margin: 0;
}

.workflow-trace__heading p,
.workflow-trace__event small {
  color: var(--el-text-color-secondary);
}

.workflow-trace__heading p {
  margin-top: 5px;
}

.workflow-trace__metrics {
  display: grid;
  margin: 16px 0;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.workflow-trace__compact-meta {
  display: flex;
  flex-wrap: wrap;
  margin: 14px 0 12px;
  gap: 7px;
}

.workflow-trace__compact-meta span {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--el-bg-color);
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.workflow-trace__metrics > div {
  display: grid;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
  gap: 5px;
}

.workflow-trace__metrics span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.workflow-trace__references {
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.workflow-trace__timeline {
  max-height: 250px;
  overflow: auto;
  padding: 6px 4px 0;
}

.workflow-trace.is-expanded .workflow-trace__timeline {
  max-height: min(50vh, 460px);
}

.workflow-trace__event {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.workflow-trace__event p {
  margin: 8px 0 4px;
}

.workflow-trace:not(.is-expanded) .workflow-trace__event p {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.workflow-trace__expand-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 2px;
}

@media (max-width: 900px) {
  .workflow-trace__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .workflow-trace__heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
