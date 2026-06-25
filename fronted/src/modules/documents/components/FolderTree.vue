<script setup lang="ts">
import { computed } from 'vue'

import type { FolderTreeNode } from '../documents.types'

interface FlatFolderNode extends FolderTreeNode {
  depth: number
}

const props = defineProps<{
  nodes: FolderTreeNode[]
  modelValue?: number
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number | undefined]
}>()

const flatNodes = computed(() => flattenFolders(props.nodes))

function flattenFolders(nodes: FolderTreeNode[], depth = 0): FlatFolderNode[] {
  return nodes.flatMap((node) => [
    { ...node, depth },
    ...flattenFolders(node.children, depth + 1),
  ])
}
</script>

<template>
  <aside class="folder-tree" aria-label="文件夹树">
    <div class="folder-tree__header">
      <strong>目录</strong>
    </div>

    <el-skeleton v-if="loading" :rows="6" animated />

    <template v-else>
      <button
        class="folder-tree__node"
        :class="{ 'is-active': modelValue === undefined }"
        type="button"
        @click="emit('update:modelValue', undefined)"
      >
        全部资料
      </button>

      <button
        v-for="node in flatNodes"
        :key="node.id"
        class="folder-tree__node"
        :class="{ 'is-active': modelValue === node.id }"
        :style="{ paddingLeft: `${12 + node.depth * 18}px` }"
        type="button"
        @click="emit('update:modelValue', node.id)"
      >
        <span>{{ node.name }}</span>
      </button>

      <el-empty v-if="flatNodes.length === 0" description="暂无目录" :image-size="72" />
    </template>
  </aside>
</template>
