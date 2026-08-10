<script setup lang="ts">
import {
  ArrowDown,
  ArrowUp,
  Bottom,
  ChatDotRound,
  DocumentAdd,
  Paperclip,
  User,
} from '@element-plus/icons-vue'
import type { InputInstance } from 'element-plus'
import { computed, nextTick, ref } from 'vue'

const GENERAL_PROJECT_PROMPT_TEMPLATE = `请根据当前已选择的甲方模板，编制本项目完整的工程技术文件，保持模板现有结构和排版。

项目名称：{项目名称}
项目地点：{项目地点}
作业/检测单位：{单位名称}
工作内容：{主要工作内容}
工期要求：{工期要求}
相关风险：{可选}
特殊要求：{可选}

项目人员以当前系统已选择人员为准。

其余施工/检测流程、技术措施、安全措施、危险源分析和应急处置等内容，请结合当前项目资料、系统专业规则及已审核知识库合理编制。

无法确认的项目事实标记“【待确认】”，不得自行编造。`

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
const composerInput = ref<InputInstance>()
const canApplyPromptTemplate = computed(
  () => Boolean(props.editableContext) && !props.disabled && !props.modelValue.trim(),
)

function applyPromptTemplate(): void {
  if (!canApplyPromptTemplate.value) return
  emit('update:modelValue', GENERAL_PROJECT_PROMPT_TEMPLATE)
  void nextTick(() => {
    composerInput.value?.focus()
    const textarea = composerInput.value?.textarea
    textarea?.setSelectionRange(textarea.value.length, textarea.value.length)
  })
}

function handleKeydown(event: KeyboardEvent): void {
  if (
    event.key === 'Tab' &&
    !event.shiftKey &&
    !event.isComposing &&
    canApplyPromptTemplate.value
  ) {
    event.preventDefault()
    applyPromptTemplate()
    return
  }
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
          <div
            class="chat-composer__attachments"
            :class="{ 'has-prompt-suggestion': canApplyPromptTemplate }"
          >
            <slot name="attachments" />
            <button
              v-if="canApplyPromptTemplate"
              type="button"
              class="chat-composer__prompt-suggestion"
              data-test="prompt-template-suggestion"
              aria-label="按 Tab 或点击此处填入通用项目提示词"
              @click="applyPromptTemplate"
            >
              <span class="chat-composer__prompt-copy">
                <kbd>Tab</kbd><span class="chat-composer__prompt-label">一键补全</span>
              </span>
              <span class="chat-composer__prompt-arrow" aria-hidden="true">
                <el-icon><Bottom /></el-icon>
              </span>
            </button>
          </div>
          <slot name="context-extra" />
          <el-input
            ref="composerInput"
            :model-value="modelValue"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 7 }"
            maxlength="4000"
            resize="none"
            :disabled="disabled"
            :placeholder="
              canApplyPromptTemplate
                ? '按 Tab 一键填入通用项目提示词，或直接输入项目关键信息…'
                : placeholder || '输入本次编制要求…'
            "
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
  position: relative;
  min-width: 0;
  padding-right: 36px;
}

.chat-composer__attachments.has-prompt-suggestion {
  padding-right: 158px;
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

.chat-composer__prompt-suggestion {
  position: absolute;
  z-index: 1;
  top: 50%;
  right: 0;
  display: inline-flex;
  min-height: 32px;
  padding: 4px 7px 4px 9px;
  align-items: center;
  border: 1px solid color-mix(in srgb, var(--color-brand) 34%, var(--color-border));
  border-radius: 999px;
  appearance: none;
  background: color-mix(in srgb, var(--color-brand) 8%, var(--color-bg-surface));
  color: var(--color-text-primary);
  cursor: pointer;
  font: inherit;
  gap: 7px;
  text-align: left;
  transform: translateY(-50%);
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.chat-composer__prompt-suggestion:hover,
.chat-composer__prompt-suggestion:focus-visible {
  border-color: var(--color-brand);
  box-shadow: var(--shadow-focus);
  outline: none;
  transform: translateY(calc(-50% - 1px));
}

.chat-composer__prompt-arrow {
  display: grid;
  width: 23px;
  height: 23px;
  border-radius: 50%;
  background: var(--color-brand);
  color: var(--color-text-inverse);
  font-size: 14px;
  place-items: center;
  animation: prompt-arrow-bounce 1.25s ease-in-out infinite;
}

.chat-composer__prompt-copy {
  display: inline-flex;
  align-items: center;
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 600;
  gap: 5px;
  white-space: nowrap;
}

.chat-composer__prompt-copy kbd {
  display: inline-flex;
  min-width: 28px;
  min-height: 20px;
  padding-inline: 5px;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--color-brand) 45%, var(--color-border));
  border-radius: 5px;
  background: var(--color-bg-surface);
  box-shadow: 0 2px 0 color-mix(in srgb, var(--color-brand) 22%, var(--color-border));
  color: var(--color-brand);
  font-family: inherit;
  font-size: 11px;
  line-height: 1;
}

@keyframes prompt-arrow-bounce {
  0%,
  100% {
    transform: translateY(-3px);
  }

  50% {
    transform: translateY(4px);
  }
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
  .chat-composer__attachments.has-prompt-suggestion {
    padding-right: 80px;
  }

  .chat-composer__prompt-label {
    display: none;
  }

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
  .chat-composer-collapse-leave-active,
  .chat-composer__prompt-arrow {
    animation: none;
    transition: none;
  }
}
</style>
