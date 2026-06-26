import { getPublicRootFolderNodes } from '@/modules/documents/utils/public-root-folders'
import type { FolderTreeNode } from '@/modules/documents/documents.types'

function folder(partial: Partial<FolderTreeNode>): FolderTreeNode {
  return {
    id: 1,
    project: null,
    parent: null,
    name: '公司资质',
    code: 'CERT',
    sort_order: 1,
    is_active: true,
    is_system_root: true,
    children: [],
    ...partial,
  }
}

it('keeps only requested public root folders in fixed display order', () => {
  const nodes = getPublicRootFolderNodes([
    folder({ id: 20, name: '开发公共资料' }),
    folder({ id: 30, parent: 20, name: '公司资质' }),
    folder({ id: 7, name: '车辆年检及资质' }),
    folder({ id: 1, name: '完工资料档案' }),
    folder({ id: 4, name: '工器具年检资质' }),
    folder({ id: 5, name: '劳动防护用品资料' }),
    folder({ id: 2, name: '公司资质' }),
    folder({ id: 3, name: '人员资质' }),
    folder({ id: 6, name: '仪器设备年检资质' }),
    folder({ id: 8, name: '公司资质' }),
  ])

  expect(nodes.map((node) => node.displayName)).toEqual([
    '竣工档案资料',
    '公司资质',
    '人员资质',
    '工具及年检资质',
    '仪器仪表设备年检资质',
    '车辆年检资质',
    '个人防护用品',
  ])
  expect(nodes.map((node) => node.id)).toEqual([1, 2, 3, 4, 6, 7, 5])
})
