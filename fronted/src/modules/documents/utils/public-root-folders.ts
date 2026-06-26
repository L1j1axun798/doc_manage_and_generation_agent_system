import type { FolderTreeNode } from '../documents.types'

export type PublicRootFolderKey =
  | 'completion'
  | 'company'
  | 'staff'
  | 'tools'
  | 'instrument'
  | 'vehicle'
  | 'protection'

export interface PublicRootFolderDefinition {
  key: PublicRootFolderKey
  label: string
  matches: string[]
}

export interface PublicRootFolderNode extends FolderTreeNode {
  displayName: string
  publicRootKey: PublicRootFolderKey
}

export const PUBLIC_ROOT_FOLDER_DEFINITIONS: PublicRootFolderDefinition[] = [
  {
    key: 'completion',
    label: '竣工档案资料',
    matches: ['竣工', '完工', '档案'],
  },
  {
    key: 'company',
    label: '公司资质',
    matches: ['公司资质'],
  },
  {
    key: 'staff',
    label: '人员资质',
    matches: ['人员资质'],
  },
  {
    key: 'tools',
    label: '工具及年检资质',
    matches: ['工具', '工器具'],
  },
  {
    key: 'instrument',
    label: '仪器仪表设备年检资质',
    matches: ['仪器', '仪表', '设备年检'],
  },
  {
    key: 'vehicle',
    label: '车辆年检资质',
    matches: ['车辆'],
  },
  {
    key: 'protection',
    label: '个人防护用品',
    matches: ['防护', '劳动防护'],
  },
]

export function getPublicRootFolderDefinition(
  folderName: string,
): PublicRootFolderDefinition | undefined {
  return PUBLIC_ROOT_FOLDER_DEFINITIONS.find((definition) =>
    definition.matches.some((match) => folderName.includes(match)),
  )
}

export function getPublicRootFolderNodes(nodes: FolderTreeNode[]): PublicRootFolderNode[] {
  const byKey = new Map<PublicRootFolderKey, PublicRootFolderNode>()

  for (const node of nodes) {
    if (node.parent !== null) {
      continue
    }

    const definition = getPublicRootFolderDefinition(node.name)
    if (!definition || byKey.has(definition.key)) {
      continue
    }

    byKey.set(definition.key, {
      ...node,
      displayName: definition.label,
      publicRootKey: definition.key,
    })
  }

  return PUBLIC_ROOT_FOLDER_DEFINITIONS
    .map((definition) => byKey.get(definition.key))
    .filter((node): node is PublicRootFolderNode => node !== undefined)
}
