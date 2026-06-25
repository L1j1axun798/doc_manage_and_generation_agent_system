import { buildMainMenu } from '@/core/router/menu-builder'

it('builds administrator menus', () => {
  const menuTitles = buildMainMenu('system_admin').map((item) => item.title)

  expect(menuTitles).toContain('用户管理')
  expect(menuTitles).toContain('审计中心')
  expect(menuTitles).toContain('系统管理')
})

it('hides administrator-only menus from data operators', () => {
  const menuTitles = buildMainMenu('data_operator').map((item) => item.title)

  expect(menuTitles).toContain('资料中心')
  expect(menuTitles).not.toContain('用户管理')
  expect(menuTitles).not.toContain('审计中心')
})
