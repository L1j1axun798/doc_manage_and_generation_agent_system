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
  type PublicRootFolderKey,
} from '../utils/public-root-folders'

interface FlatFolderNode extends FolderTreeNode {
  depth: number
  displayName: string
  icon: Component
  publicRootKey?: PublicRootFolderKey
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
const topTreeStyle = computed(() =>
  isTopPresentation.value
    ? { '--folder-tree-top-count': String(Math.max(visibleNodes.value.length, 1)) }
    : undefined,
)
const archiveNode = computed(() =>
  isTopPresentation.value
    ? visibleNodes.value.find((node) => node.publicRootKey === 'archive')
    : undefined,
)
const archiveYearNodes = computed<FlatFolderNode[]>(() =>
  archiveNode.value
    ? archiveNode.value.children.map((node) => archiveFolderNode(node, 1))
    : [],
)
const showArchiveYears = computed(
  () =>
    isTopPresentation.value &&
    archiveYearNodes.value.length > 0 &&
    archiveNode.value !== undefined &&
    isNodeActive(archiveNode.value),
)

function selectFolder(folderId: number | undefined): void {
  if (props.modelValue === folderId) {
    return
  }

  emit('update:modelValue', folderId)
}

function isNodeActive(node: FlatFolderNode): boolean {
  if (props.modelValue === node.id) {
    return true
  }

  if (
    isTopPresentation.value &&
    props.modelValue !== undefined &&
    hasDescendant(node, props.modelValue)
  ) {
    return true
  }

  return false
}

function flattenFolders(nodes: FolderTreeNode[], depth = 0): FlatFolderNode[] {
  return nodes.flatMap((node) => [
    { ...node, depth, displayName: node.name, icon: getFolderIcon(node.name) },
    ...flattenFolders(node.children, depth + 1),
  ])
}

function archiveFolderNode(node: FolderTreeNode, depth: number): FlatFolderNode {
  return {
    ...node,
    depth,
    displayName: node.name,
    icon: FolderChecked,
    publicRootKey: 'archive',
  }
}

function hasDescendant(node: FolderTreeNode, folderId: number): boolean {
  return node.children.some((child) => child.id === folderId || hasDescendant(child, folderId))
}

function getFolderIcon(name: string): Component {
  const definition = getPublicRootFolderDefinition(name)

  if (definition?.key === 'archive') {
    return FolderChecked
  }

  if (definition?.key === 'company') {
    return OfficeBuilding
  }

  if (definition?.key === 'staff') {
    return User
  }

  if (definition?.key === 'technicalSolution') {
    return Tools
  }

  if (definition?.key === 'reportTemplate' || definition?.key === 'staffInsurance') {
    return Document
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
    :style="topTreeStyle"
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

      <template v-if="isTopPresentation">
        <div class="folder-tree__roots">
          <div
            v-for="node in visibleNodes"
            :key="node.id"
            class="folder-tree__item"
            :class="{ 'folder-tree__item--archive': node.publicRootKey === 'archive' }"
          >
            <button
              class="folder-tree__node"
              :class="{ 'is-active': isNodeActive(node) }"
              type="button"
              @click="selectFolder(node.id)"
            >
              <el-icon class="folder-tree__icon">
                <component :is="node.icon" />
              </el-icon>
              <span>{{ node.displayName }}</span>
            </button>
          </div>
        </div>

        <div v-if="showArchiveYears" class="folder-tree__archive-list">
          <div
            v-for="yearNode in archiveYearNodes"
            :key="yearNode.id"
            class="folder-tree__archive-group"
          >
            <button
              class="folder-tree__archive-node"
              :class="{ 'is-active': isNodeActive(yearNode) }"
              type="button"
              @click="selectFolder(yearNode.id)"
            >
              <el-icon class="folder-tree__archive-icon">
                <component :is="yearNode.icon" />
              </el-icon>
              <span>{{ yearNode.displayName }}</span>
            </button>
          </div>
        </div>
      </template>

      <template v-else>
        <div
          v-for="node in visibleNodes"
          :key="node.id"
          class="folder-tree__item"
        >
          <button
            class="folder-tree__node"
            :class="{ 'is-active': isNodeActive(node) }"
            :style="{ paddingLeft: `${12 + node.depth * 18}px` }"
            type="button"
            @click="selectFolder(node.id)"
          >
            <span>{{ node.displayName }}</span>
          </button>
        </div>
      </template>

      <el-empty v-if="visibleNodes.length === 0" description="暂无目录" :image-size="72" />
    </template>
  </aside>
</template>
