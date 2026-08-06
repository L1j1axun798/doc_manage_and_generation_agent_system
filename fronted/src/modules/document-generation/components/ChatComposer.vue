<script setup lang="ts">
import {
  ArrowDown,
  ArrowUp,
  ChatDotRound,
  DocumentAdd,
  Paperclip,
  User,
} from '@element-plus/icons-vue'
import { ref } from 'vue'

const props = defineProps<{
  modelValue: string
  loading?: boolean
  uploadLoading?: boolean
  disabled?: boolean
  canSend?: boolean
  placeholder?: string
  helperText?: string
  editableContext?: boolean
  sourceCount?: number
  maxSourceCount?: number
  collapsed?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:collapsed': [value: boolean]
  send: []
  template: []
  personnel: []
  sources: []
  upload: [files: File[]]
}>()

const fileInput = ref<HTMLInputElement>()

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  if (props.canSend && !props.loading) emit('send')
}

function handleFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (files.length) emit('upload', files)
  input.value = ''
}
</script>

<template>
  <div
    class="chat-composer"
    :class="{ 'is-disabled': disabled, 'is-collapsed': collapsed }"
  >
    <div class="chat-composer__collapse-row">
      <div v-if="collapsed" class="chat-composer__collapsed-copy">
        <strong>聊天框已收起</strong>
        <span>{{ helperText || '点击右侧箭头展开聊天框' }}</span>
      </div>
      <span v-else aria-hidden="true" />
      <el-tooltip :content="collapsed ? '展开聊天框' : '收起聊天框'" placement="top">
        <el-button
          class="chat-composer__collapse-button"
          text
          circle
          :icon="collapsed ? ArrowUp : ArrowDown"
          :aria-label="collapsed ? '展开聊天框' : '收起聊天框'"
          @click="emit('update:collapsed', !collapsed)"
        />
      </el-tooltip>
    </div>
    <Transition name="chat-composer-collapse">
      <div v-show="!collapsed" class="chat-composer__body-shell">
        <div class="chat-composer__body">
          <div class="chat-composer__attachments">
            <slot name="attachments" />
          </div>
          <slot name="context-extra" />
          <el-input
            :model-value="modelValue"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 7 }"
            maxlength="4000"
            resize="none"
            :disabled="disabled"
            :placeholder="placeholder || '输入本次编制要求…'"
            @update:model-value="emit('update:modelValue', $event)"
            @keydown="handleKeydown"
          />
          <div class="chat-composer__footer">
            <div class="chat-composer__tools">
            <el-button
              class="chat-composer__tool-button"
              size="small"
              :icon="DocumentAdd"
              :disabled="!editableContext"
              @click="emit('template')"
            >
              上传甲方模板
            </el-button>
            <el-button
              class="chat-composer__tool-button"
              size="small"
              :icon="User"
              :disabled="!editableContext"
              @click="emit('personnel')"
            >
              选择人员
            </el-button>
            <el-button
              class="chat-composer__tool-button"
              size="small"
              :icon="ChatDotRound"
              :disabled="!editableContext"
              @click="emit('sources')"
            >
              选择系统内参考资料
            </el-button>
            <input
              ref="fileInput"
              class="chat-composer__file-input"
              type="file"
              accept=".docx,.pdf"
              multiple
              @change="handleFile"
            />
            <el-button
              class="chat-composer__tool-button"
              size="small"
              :icon="Paperclip"
              :loading="uploadLoading"
              :disabled="!editableContext || uploadLoading || sourceCount === maxSourceCount"
              :title="sourceCount === maxSourceCount ? `当前会话最多添加 ${maxSourceCount} 份资料` : ''"
              @click="fileInput?.click()"
            >
              从本机上传参考资料
            </el-button>
            </div>
            <div class="chat-composer__actions">
              <span class="chat-composer__count">{{ modelValue.length }}/4000</span>
              <el-button
                data-test="chat-send"
                type="primary"
                :loading="loading"
                :disabled="!canSend"
                @click="emit('send')"
              >
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.chat-composer {
  position: relative;
  display: grid;
  min-height: 0;
  padding: 12px;
  box-sizing: border-box;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-bg-surface);
  box-shadow: var(--shadow-2);
  gap: 10px;
  overflow: hidden;
  transition:
    min-height 900ms cubic-bezier(0.4, 0, 0.2, 1),
    padding-block 900ms cubic-bezier(0.4, 0, 0.2, 1);
}

.chat-composer:focus-within {
  border-color: var(--color-brand);
  box-shadow: var(--shadow-focus);
}

.chat-composer.is-disabled {
  background: var(--color-bg-surface-secondary);
}

.chat-composer.is-collapsed {
  min-height: 44px;
  padding-block: 8px;
  gap: 0;
}

.chat-composer__collapse-row {
  position: absolute;
  z-index: 1;
  top: 8px;
  right: 8px;
  display: flex;
  min-height: 26px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chat-composer.is-collapsed .chat-composer__collapse-row {
  left: 12px;
}

.chat-composer__body-shell {
  display: grid;
  min-width: 0;
  grid-template-rows: 1fr;
}

.chat-composer__body {
  display: grid;
  min-height: 0;
  overflow: hidden;
  gap: 10px;
}

.chat-composer-collapse-enter-active,
.chat-composer-collapse-leave-active {
  transition:
    grid-template-rows 900ms cubic-bezier(0.4, 0, 0.2, 1),
    opacity 640ms ease-in-out,
    transform 900ms cubic-bezier(0.4, 0, 0.2, 1);
}

.chat-composer-collapse-enter-from,
.chat-composer-collapse-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
  transform: translateY(16px);
}

.chat-composer__attachments {
  min-width: 0;
  padding-right: 36px;
}

.chat-composer__collapsed-copy {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 10px;
}

.chat-composer__collapsed-copy strong {
  flex: 0 0 auto;
  font-size: 12px;
}

.chat-composer__collapsed-copy span {
  overflow: hidden;
  color: var(--color-text-tertiary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-composer__collapse-button {
  flex: 0 0 auto;
}

.chat-composer :deep(.el-textarea__inner) {
  padding: 4px 2px;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.chat-composer__footer,
.chat-composer__tools,
.chat-composer__actions {
  display: flex;
  align-items: center;
}

.chat-composer__footer {
  justify-content: space-between;
  gap: 10px;
}

.chat-composer__tools {
  min-width: 0;
  flex-wrap: wrap;
  gap: 6px;
}

.chat-composer__tools :deep(.el-button + .el-button) {
  margin-left: 0;
}

.chat-composer__tool-button {
  min-height: 26px;
  padding-inline: 9px;
  font-size: 12px;
}

.chat-composer__file-input {
  display: none;
}

.chat-composer__actions {
  flex: 0 0 auto;
  gap: 10px;
}

.chat-composer__count {
  color: var(--color-text-tertiary);
  font-size: 11px;
  white-space: nowrap;
}

@media (max-width: 720px) {
  .chat-composer__footer {
    align-items: stretch;
    flex-direction: column;
  }

  .chat-composer__actions {
    justify-content: flex-end;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chat-composer,
  .chat-composer-collapse-enter-active,
  .chat-composer-collapse-leave-active {
    transition: none;
  }
}
</style>
