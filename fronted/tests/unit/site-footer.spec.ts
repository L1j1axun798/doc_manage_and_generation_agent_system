import { mount } from '@vue/test-utils'

import SiteFooter from '@/shared/components/SiteFooter.vue'

describe('site footer', () => {
  it('shows the copyright owner, domain, and official ICP filing link', () => {
    const wrapper = mount(SiteFooter)
    const footer = wrapper.get('footer')
    const filingLink = footer.get('a')

    expect(footer.attributes('aria-label')).toBe('网站备案与版权信息')
    expect(footer.text()).toContain('© 2026 绿能信盾检测技术服务(保定)有限公司')
    expect(footer.text()).toContain('www.greenenergyinsp.cn')
    expect(filingLink.text()).toBe('冀ICP备2026028278号-1')
    expect(filingLink.attributes('href')).toBe('https://beian.miit.gov.cn/')
    expect(filingLink.attributes('target')).toBe('_blank')
    expect(filingLink.attributes('rel')).toBe('noopener noreferrer')
  })
})
