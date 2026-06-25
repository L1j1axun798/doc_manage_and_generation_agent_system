import type { FolderTreeNode } from '../documents.types'

export interface FolderOption {
  id: number
  label: string
}

export function flattenFolderOptions(nodes: FolderTreeNode[], depth = 0): FolderOption[] {
  return nodes.flatMap((node) => [
    {
      id: node.id,
      label: `${'　'.repeat(depth)}${node.name}`,
    },
    ...flattenFolderOptions(node.children, depth + 1),
  ])
}
