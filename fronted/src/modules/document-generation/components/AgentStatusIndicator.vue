<script setup lang="ts">
import { computed } from 'vue'

import type { GenerationTaskStatus } from '../document-generation.types'

const props = defineProps<{
  status: GenerationTaskStatus
  progress: number
  label: string
}>()

const active = computed(() => ['extracting', 'queued', 'generating'].includes(props.status))
const completed = computed(() => ['review_required', 'pending_approval', 'approved', 'exported'].includes(props.status))
</script>

<template>
  <div class="agent-status" :class="{ 'is-active': active, 'is-completed': completed }" role="status">
    <span class="agent-status__dot" aria-hidden="true" />
    <span>{{ label }}</span>
    <strong>{{ progress }}%</strong>
  </div>
</template>

<style scoped>
.agent-status {
  display: inline-flex;
  align-items: center;
  color: var(--color-text-secondary);
  font-size: 12px;
  gap: 7px;
}

.agent-status strong {
  color: var(--color-text-primary);
}

.agent-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
}

.agent-status.is-active .agent-status__dot {
  background: var(--color-brand);
  box-shadow: 0 0 0 4px var(--color-brand-soft);
}

.agent-status.is-completed .agent-status__dot {
  background: var(--color-success);
}
</style>
