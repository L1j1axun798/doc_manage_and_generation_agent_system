import { expect, test } from '@playwright/test'

test('opens the dashboard from the root path', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: '风电资料系统' })).toBeVisible()
  await expect(page.getByText('首页').first()).toBeVisible()
})

test('shows the not found page for unknown routes', async ({ page }) => {
  await page.goto('/missing-page')

  await expect(page.getByRole('heading', { name: '页面不存在' })).toBeVisible()
})
