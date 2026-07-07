import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import FolderTree from '@/modules/documents/components/FolderTree.vue'
import type { FolderTreeNode } from '@/modules/documents/documents.types'

function folder(partial: Partial<FolderTreeNode>): FolderTreeNode {
  return {
    id: 1,
    project: null,
    parent: null,
    name: '已归档文件',
    code: 'PUBLIC-ARCHIVE',
    sort_order: 99,
    is_active: true,
    is_system_root: true,
    children: [],
    ...partial,
  }
}

it('only shows archive years in the top archive folder area', async () => {
  const wrapper = mount(FolderTree, {
    props: {
      modelValue: 90,
      presentation: 'top',
      nodes: [
        folder({
          id: 90,
          children: [
            folder({
              id: 91,
              parent: 90,
              name: '2026年归档资料',
              code: 'PUBLIC-ARCHIVE-2026',
              is_system_root: false,
              children: [
                folder({
                  id: 92,
                  project: 2,
                  parent: 91,
                  name: 'P002 归档项目',
                  code: 'PROJECT-ARCHIVE-2',
                  is_system_root: false,
                }),
              ],
            }),
          ],
        }),
      ],
    },
    global: {
      plugins: [ElementPlus],
    },
  })

  expect(wrapper.text()).toContain('2026年归档资料')
  expect(wrapper.text()).not.toContain('P002 归档项目')

  const yearButton = wrapper
    .findAll('button')
    .find((button) => button.text().includes('2026年归档资料'))
  expect(yearButton).toBeDefined()
  await yearButton?.trigger('click')
  expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([91])

  await wrapper.setProps({ modelValue: 91 })
  expect(wrapper.text()).not.toContain('P002 归档项目')
})
