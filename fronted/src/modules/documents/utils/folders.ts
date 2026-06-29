import type { FolderTreeNode } from '../documents.types'
import { isStaffRootFolderNode } from './public-root-folders'

export interface FolderOption {
  id: number
  label: string
}

export interface FlattenFolderOptionsConfig {
  exclude?: (node: FolderTreeNode) => boolean
}

export function flattenFolderOptions(
  nodes: FolderTreeNode[],
  depth = 0,
  config: FlattenFolderOptionsConfig = {},
): FolderOption[] {
  return nodes.flatMap((node) => {
    const current = config.exclude?.(node)
      ? []
      : [
          {
            id: node.id,
            label: `${'　'.repeat(depth)}${node.name}`,
          },
        ]

    return [...current, ...flattenFolderOptions(node.children, depth + 1, config)]
  })
}

export function flattenDocumentTargetFolderOptions(nodes: FolderTreeNode[]): FolderOption[] {
  return flattenFolderOptions(nodes, 0, { exclude: isStaffRootFolderNode })
}
