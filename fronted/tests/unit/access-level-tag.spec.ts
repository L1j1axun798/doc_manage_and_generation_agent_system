import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'

import AccessLevelTag from '@/modules/documents/components/AccessLevelTag.vue'

it('renders access level labels', () => {
  const wrapper = mount(AccessLevelTag, {
    props: {
      value: 'restricted',
    },
    global: {
      plugins: [ElementPlus],
    },
  })

  expect(wrapper.text()).toContain('受限')
})
