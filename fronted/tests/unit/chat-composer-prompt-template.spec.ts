import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import ChatComposer from '@/modules/document-generation/components/ChatComposer.vue'

describe('ChatComposer prompt template suggestion', () => {
  it('fills the general project prompt when Tab is pressed on an empty editable input', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        editableContext: true,
      },
      global: { plugins: [ElementPlus] },
    })

    const suggestion = wrapper.get('[data-test="prompt-template-suggestion"]')
    expect(suggestion.text()).toContain('Tab一键补全')
    expect(suggestion.element.parentElement?.classList.contains('chat-composer__attachments')).toBe(
      true,
    )
    expect(wrapper.find('.chat-composer__prompt-arrow').exists()).toBe(true)
    expect(wrapper.find('.chat-composer__prompt-copy small').exists()).toBe(false)
    expect(wrapper.get('textarea').attributes('placeholder')).toContain('按 Tab 一键填入')

    await wrapper.get('textarea').trigger('keydown', { key: 'Tab' })

    const updates = wrapper.emitted('update:modelValue')
    expect(updates).toHaveLength(1)
    expect(updates?.[0]?.[0]).toContain('项目名称：{项目名称}')
    expect(updates?.[0]?.[0]).toContain('项目人员以当前系统已选择人员为准。')
    expect(updates?.[0]?.[0]).toContain('无法确认的项目事实标记“【待确认】”')
  })

  it('also supports click completion and never takes over Tab after the user has typed', async () => {
    const emptyWrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        editableContext: true,
      },
      global: { plugins: [ElementPlus] },
    })

    await emptyWrapper.get('[data-test="prompt-template-suggestion"]').trigger('click')
    expect(emptyWrapper.emitted('update:modelValue')).toHaveLength(1)

    const filledWrapper = mount(ChatComposer, {
      props: {
        modelValue: '我已经开始填写项目要求',
        editableContext: true,
      },
      global: { plugins: [ElementPlus] },
    })

    expect(filledWrapper.find('[data-test="prompt-template-suggestion"]').exists()).toBe(false)
    await filledWrapper.get('textarea').trigger('keydown', { key: 'Tab' })
    expect(filledWrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
