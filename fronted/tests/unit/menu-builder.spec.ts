import { buildMainMenu } from '@/core/router/menu-builder'

it('builds administrator menus', () => {
  const menuTitles = buildMainMenu('system_admin').map((item) => item.title)

  expect(menuTitles).toContain('用户管理')
  expect(menuTitles).toContain('审计中心')
  expect(menuTitles).toContain('人员位置')
  expect(menuTitles).toContain('系统管理')
})

it('hides administrator-only menus from data operators', () => {
  const menuTitles = buildMainMenu('data_operator').map((item) => item.title)

  expect(menuTitles).toContain('资料中心')
  expect(menuTitles).not.toContain('用户管理')
  expect(menuTitles).not.toContain('审计中心')
  expect(menuTitles).not.toContain('人员位置')
})

it('places document generation after project management for every regular role when enabled', () => {
  for (const role of ['system_admin', 'project_manager', 'data_operator'] as const) {
    const menuTitles = buildMainMenu(role, true).map((item) => item.title)
    const projectIndex = menuTitles.indexOf('项目管理')
    const agentIndex = menuTitles.indexOf('四措两案Agent V1.0')

    expect(projectIndex).toBeGreaterThanOrEqual(0)
    expect(agentIndex).toBe(projectIndex + 1)
  }
})

it('does not expose main menus to temporary users', () => {
  expect(buildMainMenu('temporary_user')).toEqual([])
})
