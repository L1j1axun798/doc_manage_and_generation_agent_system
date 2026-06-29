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
    folder({ id: 11, name: '人员保险单' }),
    folder({ id: 12, name: '技术方案' }),
    folder({ id: 13, name: '报告模板' }),
    folder({ id: 6, name: '仪器设备年检资质' }),
    folder({ id: 8, name: '公司资质' }),
    folder({ id: 9, name: '2026年归档资料' }),
    folder({ id: 10, name: '2025年归档资料' }),
  ])

  expect(nodes.map((node) => node.displayName)).toEqual([
    '竣工资料档案',
    '公司资质',
    '技术方案',
    '报告模板',
    '工器具及年检资质',
    '仪器仪表设备年检资质',
    '车辆年检资质',
    '人员资质',
    '人员保险单',
    '个人防护用品',
    '已归档文件',
  ])
  expect(nodes.map((node) => node.id)).toEqual([1, 2, 12, 13, 4, 6, 7, 3, 11, 5, 9])
  expect(nodes.at(-1)?.children.map((node) => node.name)).toEqual([
    '2026年归档资料',
    '2025年归档资料',
  ])
})

it('uses real archive root with archive years as child folders', () => {
  const nodes = getPublicRootFolderNodes([
    folder({ id: 1, name: '竣工资料档案' }),
    folder({
      id: 9,
      name: '已归档文件',
      code: 'PUBLIC-ARCHIVE',
      sort_order: 99,
      children: [
        folder({ id: 11, parent: 9, name: '2025年归档资料', code: 'PUBLIC-ARCHIVE-2025' }),
        folder({ id: 10, parent: 9, name: '2026年归档资料', code: 'PUBLIC-ARCHIVE-2026' }),
      ],
    }),
  ])

  expect(nodes.map((node) => node.displayName)).toEqual(['竣工资料档案', '已归档文件'])
  expect(nodes.at(-1)?.id).toBe(9)
  expect(nodes.at(-1)?.children.map((node) => node.name)).toEqual([
    '2026年归档资料',
    '2025年归档资料',
  ])
})
