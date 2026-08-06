<script setup lang="ts">
import { Delete, Plus, Refresh, VideoPause } from '@element-plus/icons-vue'

import type { GenerationTask, GenerationTaskStatus } from '../document-generation.types'

const props = defineProps<{
  tasks: GenerationTask[]
  username: string
  activeTaskId: string | null
  openingTaskId: string | null
  actionTaskId: string | null
  refreshingTaskId: string | null
  loading: boolean
  projectSelected: boolean
  statusLabels: Record<GenerationTaskStatus, string>
}>()

const emit = defineEmits<{
  new: []
  open: [task: GenerationTask]
  refresh: [task: GenerationTask]
  stop: [task: GenerationTask]
  delete: [task: GenerationTask]
}>()

function isRunning(task: GenerationTask): boolean {
  return ['extracting', 'queued', 'generating'].includes(task.status)
}

function statusType(task: GenerationTask): 'danger' | 'success' | 'warning' | 'info' {
  if (task.status === 'failed') return 'danger'
  if (task.status === 'exported') return 'success'
  if (task.status === 'cancelled') return 'warning'
  return 'info'
}
</script>

<template>
  <aside class="conversation-sidebar" aria-label="四措两案编制会话">
    <div class="conversation-sidebar__header">
      <div>
        <strong>编制会话</strong>
        <span>{{ tasks.length }} 项</span>
      </div>
      <el-button type="primary" :icon="Plus" :disabled="loading || !projectSelected" @click="emit('new')">
        新建
      </el-button>
    </div>

    <div v-if="loading && !tasks.length" class="conversation-sidebar__loading">正在载入会话…</div>
    <el-empty
      v-else-if="!tasks.length"
      :image-size="64"
      :description="projectSelected ? '暂无历史会话' : '请先选择项目'"
    />
    <div v-else class="doc-agent__conversation-list">
      <div
        v-for="(task, index) in tasks"
        :key="task.id"
        class="doc-agent__conversation-row"
        :class="{ 'is-active': task.id === activeTaskId }"
      >
        <button
          class="doc-agent__conversation-item"
          type="button"
          :disabled="openingTaskId !== null || actionTaskId !== null || refreshingTaskId !== null"
          @click="emit('open', task)"
        >
          <span class="doc-agent__conversation-copy">
            <span class="doc-agent__conversation-title">{{ `对话${index + 1}-${username}` }}</span>
          </span>
          <span class="doc-agent__conversation-state">
            <el-tag size="small" :type="statusType(task)">
              {{ props.statusLabels[task.status] }}
            </el-tag>
            <small v-if="task.conversation_context?.personnel?.length">
              {{ task.conversation_context.personnel.length }} 人
            </small>
          </span>
        </button>
        <div class="doc-agent__conversation-actions">
          <el-tooltip content="刷新该会话" placement="top">
            <el-button
              data-test="refresh-conversation"
              type="primary"
              link
              :icon="Refresh"
              :loading="refreshingTaskId === task.id"
              :disabled="actionTaskId !== null || (refreshingTaskId !== null && refreshingTaskId !== task.id)"
              aria-label="刷新会话"
              @click="emit('refresh', task)"
            />
          </el-tooltip>
          <el-button
            v-if="isRunning(task)"
            data-test="stop-conversation"
            type="warning"
            link
            :icon="VideoPause"
            :loading="actionTaskId === task.id"
            aria-label="停止会话"
            @click="emit('stop', task)"
          />
          <el-button
            v-else
            data-test="delete-conversation"
            type="danger"
            link
            :icon="Delete"
            :loading="actionTaskId === task.id"
            aria-label="删除会话"
            @click="emit('delete', task)"
          />
        </div>
      </div>
    </div>

    <p class="conversation-sidebar__scope-note">
      本功能仅编制入场前四措两案，不生成检测报告、实测结论或完工资料。
    </p>
  </aside>
</template>

<style scoped>
.conversation-sidebar {
  display: flex;
  width: 240px;
  height: 100%;
  min-width: 0;
  min-height: 0;
  max-height: 100%;
  overflow: hidden;
  padding: 16px 12px;
  box-sizing: border-box;
  border-right: 1px solid var(--color-border-light);
  background: var(--color-bg-surface-secondary);
  flex-direction: column;
}

.conversation-sidebar__header,
.conversation-sidebar__header > div {
  display: flex;
  align-items: center;
}

.conversation-sidebar__header {
  justify-content: space-between;
  gap: 8px;
  padding: 0 4px 14px;
}

.conversation-sidebar__header > div {
  min-width: 0;
  gap: 8px;
}

.conversation-sidebar__header span,
.conversation-sidebar__loading {
  color: var(--color-text-tertiary);
  font-size: 12px;
}

.conversation-sidebar__loading {
  flex: 1 1 auto;
  padding: 24px 8px;
  text-align: center;
}

.conversation-sidebar :deep(.el-empty) {
  min-height: 0;
  flex: 1 1 auto;
}

.doc-agent__conversation-list {
  display: grid;
  min-height: 0;
  overflow: hidden auto;
  align-content: start;
  flex: 1 1 auto;
  gap: 4px;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.doc-agent__conversation-row {
  display: flex;
  align-items: center;
  min-width: 0;
  border-radius: var(--radius-md);
}

.doc-agent__conversation-row:hover,
.doc-agent__conversation-row.is-active {
  background: var(--color-bg-surface-active);
}

.doc-agent__conversation-row.is-active {
  box-shadow: inset 3px 0 0 var(--color-brand);
}

.doc-agent__conversation-item {
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 11px 8px 11px 12px;
  border: 0;
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
  flex: 1;
  font: inherit;
  gap: 8px;
  text-align: left;
}

.doc-agent__conversation-item:disabled {
  cursor: wait;
  opacity: 0.68;
}

.doc-agent__conversation-copy,
.doc-agent__conversation-state {
  display: grid;
  gap: 3px;
}

.doc-agent__conversation-copy {
  min-width: 0;
  flex: 1;
}

.doc-agent__conversation-title {
  overflow: hidden;
  font-size: 12px;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-agent__conversation-state small {
  color: var(--color-text-tertiary);
  font-size: 11px;
}

.doc-agent__conversation-state {
  flex: 0 0 auto;
  justify-items: end;
}

.doc-agent__conversation-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  padding-right: 4px;
  gap: 2px;
}

.doc-agent__conversation-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.conversation-sidebar__scope-note {
  margin: 12px 4px 0;
  padding-top: 12px;
  border-top: 1px solid var(--color-border-light);
  color: var(--color-text-tertiary);
  font-size: 11px;
  line-height: 1.55;
  text-align: left;
}

@media (max-width: 900px) {
  .conversation-sidebar {
    width: 100%;
    height: 230px;
    max-height: 230px;
    border-right: 0;
    border-bottom: 1px solid var(--color-border-light);
  }
}
</style>
