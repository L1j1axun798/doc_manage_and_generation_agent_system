import { flattenFolderOptions } from '@/modules/documents/utils/folders'

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
