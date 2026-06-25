import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import ProjectStatusTag from '@/modules/projects/components/ProjectStatusTag.vue'

it('renders project status labels', () => {
  const wrapper = mount(ProjectStatusTag, {
    props: {
      status: 'archived',
    },
    global: {
      plugins: [ElementPlus],
    },
  })

  expect(wrapper.text()).toContain('已归档')
})
