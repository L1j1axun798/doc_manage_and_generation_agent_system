import {
  flattenDocumentTargetFolderOptions,
  flattenFolderOptions,
  getPublicRootFolderOptions,
} from '@/modules/documents/utils/folders'
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

it('flattens nested folder tree nodes', () => {
  const options = flattenFolderOptions([
    {
      id: 1,
      project: null,
      parent: null,
      name: '公司资质',
      code: 'CERT',
      sort_order: 1,
      is_active: true,
      is_system_root: true,
      children: [
        {
          id: 2,
          project: null,
          parent: 1,
          name: '证照',
          code: 'LICENSE',
          sort_order: 1,
          is_active: true,
          is_system_root: false,
          children: [],
        },
      ],
    },
  ])

  expect(options).toEqual([
    { id: 1, label: '公司资质' },
    { id: 2, label: '　证照' },
  ])
})

it('excludes public qualification roots as document targets but keeps child folders', () => {
  const options = flattenDocumentTargetFolderOptions([
    folder({
      id: 1,
      name: '公司资质',
      code: 'PUBLIC-COMPANY',
      children: [
        folder({
          id: 2,
          parent: 1,
          name: '示例公司',
          code: '',
          is_system_root: false,
        }),
      ],
    }),
    folder({
      id: 3,
      name: '人员资质',
      code: 'PUBLIC-STAFF',
      children: [
        folder({
          id: 4,
          parent: 3,
          name: '张三',
          code: '',
          is_system_root: false,
        }),
      ],
    }),
    folder({ id: 5, name: '人员保险单', code: 'PUBLIC-STAFF-INSURANCE' }),
  ])

  expect(options).toEqual([
    { id: 2, label: '　示例公司' },
    { id: 4, label: '　张三' },
    { id: 5, label: '人员保险单' },
  ])
})

it('keeps project qualification roots as document targets', () => {
  const options = flattenDocumentTargetFolderOptions([
    folder({
      id: 4,
      project: 1,
      name: '人员资质',
      code: 'PUBLIC-STAFF',
      is_system_root: false,
    }),
    folder({
      id: 5,
      project: 1,
      name: '公司资质',
      code: 'PUBLIC-COMPANY',
      is_system_root: false,
    }),
  ])

  expect(options).toEqual([
    { id: 4, label: '人员资质' },
    { id: 5, label: '公司资质' },
  ])
})

it('builds public root folder options for document center move targets', () => {
  const options = getPublicRootFolderOptions([
    folder({
      id: 1,
      name: '公司资质',
      code: 'PUBLIC-COMPANY',
      children: [
        folder({
          id: 2,
          parent: 1,
          name: '示例公司',
          code: '',
          is_system_root: false,
        }),
      ],
    }),
    folder({
      id: 3,
      name: '人员资质',
      code: 'PUBLIC-STAFF',
      children: [
        folder({
          id: 4,
          parent: 3,
          name: '张三',
          code: '',
          is_system_root: false,
        }),
      ],
    }),
    folder({ id: 5, name: '人员保险单', code: 'PUBLIC-STAFF-INSURANCE' }),
  ])

  expect(options).toEqual([
    { id: 1, label: '公司资质' },
    { id: 3, label: '人员资质' },
    { id: 5, label: '人员保险单' },
  ])
})
