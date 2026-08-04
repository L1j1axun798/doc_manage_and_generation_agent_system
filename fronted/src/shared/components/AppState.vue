<script setup lang="ts">
import {
  CircleCloseFilled,
  Document,
  Loading,
  Lock,
  Search,
  WarningFilled,
} from '@element-plus/icons-vue'
import { computed } from 'vue'

type AppStateVariant = 'empty' | 'loading' | 'error' | 'forbidden' | 'not-found'

const props = withDefaults(
  defineProps<{
    variant?: AppStateVariant
    code?: string
    title: string
    description?: string
    compact?: boolean
  }>(),
  {
    variant: 'empty',
    code: '',
    description: '',
    compact: false,
  },
)

const stateIcon = computed(() => {
  const icons = {
    empty: Document,
    loading: Loading,
    error: CircleCloseFilled,
    forbidden: Lock,
    'not-found': Search,
  }

  return icons[props.variant] || WarningFilled
})

const liveRole = computed(() => (props.variant === 'error' ? 'alert' : 'status'))
</script>

<template>
  <section
    class="app-state"
    :class="[`app-state--${variant}`, { 'app-state--compact': compact }]"
    :role="liveRole"
    :aria-busy="variant === 'loading'"
    :aria-live="variant === 'error' ? 'assertive' : 'polite'"
  >
    <div class="app-state__visual" aria-hidden="true">
      <span class="app-state__visual-halo"></span>
      <el-icon><component :is="stateIcon" /></el-icon>
    </div>
    <p v-if="code" class="app-state__code">{{ code }}</p>
    <h1>{{ title }}</h1>
    <p v-if="description" class="app-state__description">{{ description }}</p>
    <div v-if="$slots.actions" class="app-state__actions">
      <slot name="actions" />
    </div>
  </section>
</template>
