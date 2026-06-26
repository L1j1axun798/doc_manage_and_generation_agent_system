<script setup lang="ts">
import {
  Document,
  FirstAidKit,
  FolderChecked,
  OfficeBuilding,
  Operation,
  Tools,
  User,
  Van,
} from '@element-plus/icons-vue'
import { computed, type Component } from 'vue'

import type { FolderTreeNode } from '../documents.types'
import {
  getPublicRootFolderDefinition,
  getPublicRootFolderNodes,
} from '../utils/public-root-folders'

interface FlatFolderNode extends FolderTreeNode {
  depth: number
  displayName: string
  icon: Component
}

const props = defineProps<{
  nodes: FolderTreeNode[]
  modelValue?: number
  loading?: boolean
  presentation?: 'side' | 'top'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number | undefined]
}>()

const flatNodes = computed(() => flattenFolders(props.nodes))
const isTopPresentation = computed(() => props.presentation === 'top')
const visibleNodes = computed(() => {
  if (!isTopPresentation.value) {
    return flatNodes.value
  }

  return getPublicRootFolderNodes(props.nodes).map((node) => ({
    ...node,
    depth: 0,
    icon: getFolderIcon(node.name),
  }))
})

function selectFolder(folderId: number | undefined): void {
  if (props.modelValue === folderId) {
    return
  }

  emit('update:modelValue', folderId)
}

function flattenFolders(nodes: FolderTreeNode[], depth = 0): FlatFolderNode[] {
  return nodes.flatMap((node) => [
    { ...node, depth, displayName: node.name, icon: getFolderIcon(node.name) },
    ...flattenFolders(node.children, depth + 1),
  ])
}

function getFolderIcon(name: string): Component {
  const definition = getPublicRootFolderDefinition(name)

  if (definition?.key === 'company') {
    return OfficeBuilding
  }

  if (definition?.key === 'staff') {
    return User
  }

  if (definition?.key === 'tools') {
    return Tools
  }

  if (definition?.key === 'instrument') {
    return Operation
  }

  if (definition?.key === 'vehicle') {
    return Van
  }

  if (definition?.key === 'protection') {
    return FirstAidKit
  }

  if (definition?.key === 'completion') {
    return FolderChecked
  }

  return Document
}
</script>

<template>
  <aside
    class="folder-tree"
    :class="{ 'folder-tree--top': isTopPresentation }"
    aria-label="文件夹树"
  >
    <div v-if="!isTopPresentation" class="folder-tree__header">
      <strong>目录</strong>
    </div>

    <el-skeleton v-if="loading" :rows="isTopPresentation ? 2 : 6" animated />

    <template v-else>
      <button
        v-if="!isTopPresentation"
        class="folder-tree__node"
        :class="{ 'is-active': modelValue === undefined }"
        :style="{ paddingLeft: '12px' }"
        type="button"
        @click="selectFolder(undefined)"
      >
        <span>全部资料</span>
      </button>

      <button
        v-for="node in visibleNodes"
        :key="node.id"
        class="folder-tree__node"
        :class="{ 'is-active': modelValue === node.id }"
        :style="isTopPresentation ? undefined : { paddingLeft: `${12 + node.depth * 18}px` }"
        type="button"
        @click="selectFolder(node.id)"
      >
        <el-icon v-if="isTopPresentation" class="folder-tree__icon">
          <component :is="node.icon" />
        </el-icon>
        <span>{{ node.displayName }}</span>
      </button>

      <el-empty v-if="visibleNodes.length === 0" description="暂无目录" :image-size="72" />
    </template>
  </aside>
</template>
