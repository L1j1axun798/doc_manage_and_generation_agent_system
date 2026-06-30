import type { FolderTreeNode } from '../documents.types'

export type PublicRootFolderKey =
  | 'archive'
  | 'completion'
  | 'company'
  | 'technicalSolution'
  | 'reportTemplate'
  | 'tools'
  | 'instrument'
  | 'vehicle'
  | 'staff'
  | 'staffInsurance'
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

const ARCHIVE_ROOT_DEFINITION: PublicRootFolderDefinition = {
  key: 'archive',
  label: '已归档文件',
  matches: ['已归档文件', '归档材料', '归档资料'],
}

export const PUBLIC_ROOT_FOLDER_DEFINITIONS: PublicRootFolderDefinition[] = [
  {
    key: 'completion',
    label: '竣工资料档案',
    matches: ['竣工', '完工', '档案'],
  },
  {
    key: 'company',
    label: '公司资质',
    matches: ['公司资质'],
  },
  {
    key: 'technicalSolution',
    label: '技术方案',
    matches: ['技术方案'],
  },
  {
    key: 'reportTemplate',
    label: '报告模板',
    matches: ['报告模板'],
  },
  {
    key: 'tools',
    label: '工器具及年检资质',
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
    key: 'staff',
    label: '人员资质',
    matches: ['人员资质'],
  },
  {
    key: 'staffInsurance',
    label: '人员保险单',
    matches: ['人员保险单', '人员报销单'],
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
  if (isArchiveYearRoot(folderName)) {
    return ARCHIVE_ROOT_DEFINITION
  }

  if (folderName === ARCHIVE_ROOT_DEFINITION.label) {
    return ARCHIVE_ROOT_DEFINITION
  }

  return PUBLIC_ROOT_FOLDER_DEFINITIONS.find((definition) =>
    definition.matches.some((match) => folderName.includes(match)),
  )
}

export function getPublicRootFolderNodes(nodes: FolderTreeNode[]): PublicRootFolderNode[] {
  const byKey = new Map<PublicRootFolderKey, PublicRootFolderNode>()
  const archiveYearNodes: PublicRootFolderNode[] = []
  let archiveRoot: PublicRootFolderNode | undefined

  for (const node of nodes) {
    if (node.parent !== null) {
      continue
    }

    const definition = getPublicRootFolderDefinition(node.name)
    if (!definition) {
      continue
    }

    if (definition.key === 'archive') {
      if (ARCHIVE_ROOT_DEFINITION.matches.includes(node.name)) {
        archiveRoot = {
          ...node,
          displayName: ARCHIVE_ROOT_DEFINITION.label,
          publicRootKey: definition.key,
          children: [...node.children].sort(compareArchiveYearsDesc),
        }
        continue
      }

      archiveYearNodes.push({
        ...node,
        displayName: node.name,
        publicRootKey: definition.key,
      })
      continue
    }

    if (byKey.has(definition.key)) {
      continue
    }

    byKey.set(definition.key, {
      ...node,
      displayName: definition.label,
      publicRootKey: definition.key,
    })
  }

  const fixedNodes = PUBLIC_ROOT_FOLDER_DEFINITIONS
    .map((definition) => byKey.get(definition.key))
    .filter((node): node is PublicRootFolderNode => node !== undefined)

  const sortedArchiveYears = archiveYearNodes.sort(compareArchiveYearsDesc)

  if (!archiveRoot && sortedArchiveYears.length === 0) {
    return fixedNodes
  }

  if (archiveRoot) {
    archiveRoot = {
      ...archiveRoot,
      children: [...archiveRoot.children, ...sortedArchiveYears].sort(compareArchiveYearsDesc),
    }
  } else {
    const latestArchiveYear = sortedArchiveYears[0]
    archiveRoot = {
      ...latestArchiveYear,
      name: ARCHIVE_ROOT_DEFINITION.label,
      displayName: ARCHIVE_ROOT_DEFINITION.label,
      publicRootKey: 'archive',
      children: sortedArchiveYears,
    }
  }

  return [...fixedNodes, archiveRoot]
}

export function isQualificationRootFolderNode(
  node: Pick<FolderTreeNode, 'code' | 'name' | 'parent' | 'project'>,
): boolean {
  if (node.parent !== null || node.project !== null) {
    return false
  }

  const definition = getPublicRootFolderDefinition(node.name)
  return (
    node.code === 'PUBLIC-COMPANY' ||
    node.code === 'PUBLIC-STAFF' ||
    definition?.key === 'company' ||
    definition?.key === 'staff'
  )
}

function isArchiveYearRoot(folderName: string): boolean {
  return /^\d{4}年归档资料$/.test(folderName)
}

function compareArchiveYearsDesc(left: FolderTreeNode, right: FolderTreeNode): number {
  return right.name.localeCompare(left.name, 'zh-Hans-CN')
}
