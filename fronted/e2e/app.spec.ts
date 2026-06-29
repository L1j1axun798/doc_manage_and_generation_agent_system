import { expect, test, type Page } from '@playwright/test'
import type { FolderTreeNode } from '../src/modules/documents/documents.types'

test('redirects anonymous users from root to login', async ({ page }) => {
  await page.route('**/api/v1/auth/csrf/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ csrfToken: 'test-csrf-token' }),
    })
  })
  await page.route('**/api/v1/auth/me/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      status: 401,
      body: JSON.stringify({ detail: '未登录' }),
    })
  })

  await page.goto('/')

  await expect(page.getByRole('heading', { name: '绿能信盾资料管理系统' })).toBeVisible()
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})

test('shows the not found page for unknown routes', async ({ page }) => {
  await page.goto('/missing-page')

  await expect(page.getByRole('heading', { name: '页面不存在' })).toBeVisible()
})

test('shows document center with folder tree and document detail', async ({ page }) => {
  await mockAuthenticatedSession(page)
  const publicFolderTree: FolderTreeNode[] = [
    {
      id: 10,
      project: null,
      parent: null,
      name: '公司资质',
      code: 'PUBLIC-COMPANY',
      sort_order: 2,
      is_active: true,
      is_system_root: true,
      children: [],
    },
    {
      id: 30,
      project: null,
      parent: null,
      name: '人员资质',
      code: 'PUBLIC-STAFF',
      sort_order: 8,
      is_active: true,
      is_system_root: true,
      children: [
        {
          id: 31,
          project: null,
          parent: 30,
          name: '张三',
          code: '',
          sort_order: 1,
          is_active: true,
          is_system_root: false,
          children: [],
        },
        {
          id: 32,
          project: null,
          parent: 30,
          name: '李四',
          code: '',
          sort_order: 2,
          is_active: true,
          is_system_root: false,
          children: [],
        },
      ],
    },
    {
      id: 40,
      project: null,
      parent: null,
      name: '人员保险单',
      code: 'PUBLIC-STAFF-INSURANCE',
      sort_order: 9,
      is_active: true,
      is_system_root: true,
      children: [],
    },
    {
      id: 50,
      project: null,
      parent: null,
      name: '技术方案',
      code: 'PUBLIC-TECH-SOLUTION',
      sort_order: 3,
      is_active: true,
      is_system_root: true,
      children: [
        {
          id: 51,
          project: null,
          parent: 50,
          name: '风机叶片',
          code: '',
          sort_order: 1,
          is_active: true,
          is_system_root: false,
          children: [],
        },
      ],
    },
    {
      id: 60,
      project: null,
      parent: null,
      name: '报告模板',
      code: 'PUBLIC-REPORT-TEMPLATE',
      sort_order: 4,
      is_active: true,
      is_system_root: true,
      children: [],
    },
    {
      id: 90,
      project: null,
      parent: null,
      name: '已归档文件',
      code: 'PUBLIC-ARCHIVE',
      sort_order: 99,
      is_active: true,
      is_system_root: true,
      children: [],
    },
  ]
  await page.route('**/api/v1/folders/tree/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(publicFolderTree),
    })
  })
  await page.route('**/api/v1/folders/', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }

    const payload = route.request().postDataJSON() as { name: string; parent: number }
    const createdFolder: FolderTreeNode = {
      id: 33,
      project: null,
      parent: payload.parent,
      name: payload.name,
      code: '',
      sort_order: 3,
      is_active: true,
      is_system_root: false,
      children: [],
    }
    publicFolderTree
      .find((folder) => folder.id === payload.parent)
      ?.children.push(createdFolder)
    await route.fulfill({
      contentType: 'application/json',
      status: 201,
      body: JSON.stringify(createdFolder),
    })
  })
  await page.route('**/api/v1/documents/?**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [documentFixture],
      }),
    })
  })
  await page.route('**/api/v1/documents/1/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(documentFixture),
    })
  })
  await page.route('**/api/v1/documents/1/download/', async (route) => {
    await route.fulfill({
      contentType: 'application/pdf',
      headers: {
        'Content-Disposition': "attachment; filename*=UTF-8''license.pdf",
      },
      body: 'demo file',
    })
  })
  await mockAccessEndpoints(page)

  await page.goto('/documents')

  await expect(page.getByRole('heading', { name: '资料中心' })).toBeVisible()
  await expect(page.getByRole('button', { name: '公司资质' })).toBeVisible()
  await expect(page.getByRole('button', { name: '人员保险单' })).toBeVisible()
  await expect(page.getByRole('button', { name: '技术方案' })).toBeVisible()
  await expect(page.getByRole('button', { name: '报告模板' })).toBeVisible()
  await expect(page.getByRole('button', { name: '已归档文件' })).toBeVisible()
  await expect(page.getByText('安全生产许可证')).toBeVisible()
  await expect(page.getByRole('button', { name: '上传资料' })).toBeVisible()
  await expect(page.getByRole('link', { name: '回收站' })).toBeVisible()

  await page.getByRole('button', { name: '人员资质' }).click()
  await expect(page.getByRole('heading', { name: '人员项' })).toBeVisible()
  await expect(page.getByText('员工数：2')).toBeVisible()
  await expect(page.getByRole('button', { name: '张三' })).toBeVisible()
  await expect(page.getByRole('button', { name: '李四' })).toBeVisible()
  const staffGridColumnCount = await page
    .locator('.document-subfolder-panel--staff .document-subfolder-panel__grid')
    .evaluate((element) =>
      getComputedStyle(element).gridTemplateColumns.split(' ').filter(Boolean).length,
    )
  expect(staffGridColumnCount).toBe(1)
  await expect(page.getByRole('button', { name: '上传资料' })).toHaveCount(0)
  await page.getByRole('button', { name: '添加用户' }).click()
  await page.getByRole('textbox', { name: '请输入人员姓名' }).fill('王五')
  await page.getByRole('button', { name: '添加', exact: true }).click()
  await expect(page.getByText('用户已添加')).toBeVisible()
  await expect(page.getByText('员工数：3')).toBeVisible()
  await expect(page.getByRole('button', { name: '王五' })).toBeVisible()

  await page.getByRole('button', { name: '张三' }).click()
  await expect(page.getByRole('button', { name: '上传资料' })).toBeVisible()
  await expect(page.getByText('安全生产许可证')).toBeVisible()
  await page.getByRole('button', { name: '关闭模块' }).click()
  await expect(page.getByRole('heading', { name: '人员项' })).toBeVisible()
  await expect(page.getByRole('button', { name: '张三' })).toBeVisible()
  await expect(page.getByRole('button', { name: '上传资料' })).toHaveCount(0)
  await page.getByRole('button', { name: '张三' }).click()
  await expect(page.getByRole('button', { name: '上传资料' })).toBeVisible()

  await page.getByRole('button', { name: '技术方案' }).click()
  await expect(page.getByRole('heading', { name: '部件分类' })).toBeVisible()
  await expect(page.getByRole('button', { name: '风机叶片' })).toBeVisible()
  await page.getByRole('button', { name: '风机叶片' }).click()
  await page.getByRole('button', { name: '关闭模块' }).click()
  await expect(page.getByRole('heading', { name: '部件分类' })).toBeVisible()
  await expect(page.getByRole('button', { name: '风机叶片' })).toBeVisible()
  await expect(page.getByRole('button', { name: '详情' })).toHaveCount(0)
  await page.getByRole('button', { name: '风机叶片' }).click()

  await page.getByRole('button', { name: '详情' }).click()
  await expect(page.getByText('文档详情')).toBeVisible()
  await expect(page.getByLabel('基础信息').getByText('license.pdf', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByText('文档详情')).toBeHidden()

  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载' }).click()
  await expect((await download).suggestedFilename()).toBe('license.pdf')

  await page.getByRole('button', { name: '上传资料' }).click()
  await expect(page.getByRole('heading', { name: '上传资料' })).toBeVisible()
})

test('manages document grants and temporary access from document detail', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/folders/tree/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 10,
          project: null,
          parent: null,
          name: '公司资质',
          code: 'CERT',
          sort_order: 10,
          is_active: true,
          is_system_root: true,
          children: [],
        },
      ]),
    })
  })
  await page.route('**/api/v1/documents/?**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [{ ...documentFixture, access_level: 'restricted' }],
      }),
    })
  })
  await page.route('**/api/v1/documents/1/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ ...documentFixture, access_level: 'restricted' }),
    })
  })
  await page.route('**/api/v1/document-grants/**', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        contentType: 'application/json',
        status: 201,
        body: JSON.stringify(documentGrantFixture),
      })
      return
    }

    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [documentGrantFixture],
      }),
    })
  })
  await page.route('**/api/v1/temporary-access-grants/**', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        contentType: 'application/json',
        status: 201,
        body: JSON.stringify(temporaryAccessCreatedFixture),
      })
      return
    }

    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [temporaryAccessFixture],
      }),
    })
  })

  await page.goto('/documents')
  await page.getByRole('button', { name: '详情' }).click()
  await page.getByRole('tab', { name: '授权管理' }).click()

  await expect(page.getByText('用户级授权')).toBeVisible()
  await expect(page.getByRole('cell', { name: '授权用户' })).toBeVisible()
  await page.getByRole('button', { name: '添加授权' }).click()
  await expect(page.getByRole('heading', { name: '添加授权' })).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: '生成临时链接' }).click()
  await expect(page.getByRole('heading', { name: '生成临时链接' })).toBeVisible()
  await page.getByRole('button', { name: '生成', exact: true }).click()
  await expect(page.getByText('临时链接只在创建后显示一次')).toBeVisible()
  await expect(page.locator('.temporary-access-created input').first()).toHaveValue(
    /\/share\/temp-token-001/,
  )
})

test('downloads from temporary access page', async ({ page }) => {
  await page.route('**/api/v1/temporary-access/temp-token-001/download/', async (route) => {
    await route.fulfill({
      contentType: 'application/pdf',
      headers: {
        'Content-Disposition': "attachment; filename*=UTF-8''temporary.pdf",
      },
      body: 'temporary file',
    })
  })

  await page.goto('/share/temp-token-001')

  await expect(page.getByRole('heading', { name: '临时文件下载' })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载文件' }).click()
  await expect((await download).suggestedFilename()).toBe('temporary.pdf')
})

test('shows global access management lists', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/document-grants/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [documentGrantFixture],
      }),
    })
  })
  await page.route('**/api/v1/temporary-access-grants/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [temporaryAccessFixture],
      }),
    })
  })

  await page.goto('/access/internal')

  await expect(page.getByRole('heading', { name: '授权管理' })).toBeVisible()
  await expect(page.getByLabel('内部文件授权').getByText('安全生产许可证')).toBeVisible()
  await expect(page.getByRole('cell', { name: '授权用户 grant-user' })).toBeVisible()
  await page.getByRole('tab', { name: '临时访问授权' }).click()
  await expect(page.getByRole('cell', { name: 'license.pdf' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '0 / 1' })).toBeVisible()
})

test('shows user management and resets a user password', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/users/**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()

    if (url.endsWith('/api/v1/users/2/reset-password/') && method === 'POST') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          temporary_password: 'TempPass123!',
          must_change_password: true,
        }),
      })
      return
    }

    if (url.endsWith('/api/v1/users/2/')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(userFixture),
      })
      return
    }

    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [userFixture],
      }),
    })
  })

  await page.goto('/users')

  await expect(page.getByRole('heading', { name: '用户管理' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '资料整理员 operator' })).toBeVisible()
  await page.getByRole('button', { name: '详情' }).click()
  await expect(page.getByText('用户详情')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '重置密码' }).click()
  await page.getByLabel('重置密码').getByRole('button', { name: '重置', exact: true }).click()
  await expect(page.getByText('临时密码只在本次响应中显示')).toBeVisible()
  await expect(page.locator('.reset-password-dialog__password input')).toHaveValue('TempPass123!')
})

test('shows audit logs and audit details', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/audit-logs/**', async (route) => {
    if (route.request().url().endsWith('/api/v1/audit-logs/700/')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(auditLogFixture),
      })
      return
    }

    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [auditLogFixture],
      }),
    })
  })

  await page.goto('/audit')

  await expect(page.getByRole('heading', { name: '审计中心' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'document.download' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '成功' })).toBeVisible()
  await page.getByRole('button', { name: '详情' }).click()
  await expect(page.getByText('审计详情')).toBeVisible()
  await expect(page.getByText('req-700')).toBeVisible()
})

test('shows notifications and toggles read state', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/notifications/**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()

    if (url.endsWith('/api/v1/notifications/800/read/') && method === 'POST') {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ ...notificationFixture, is_read: true, read_at: '2026-06-25T10:05:00+08:00' }),
      })
      return
    }

    if (url.endsWith('/api/v1/notifications/800/')) {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(notificationFixture),
      })
      return
    }

    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [notificationFixture],
      }),
    })
  })

  await page.goto('/notifications')

  await expect(page.getByRole('heading', { name: '通知中心' })).toBeVisible()
  await expect(page.getByRole('button', { name: '受限文档授权已创建' })).toBeVisible()
  await page.getByRole('button', { name: '详情' }).click()
  await expect(page.getByText('通知详情')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '标已读' }).click()
  await expect(page.getByText('已标记为已读')).toBeVisible()
})

test('shows system management directories, status and unavailable panels', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/folders/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 2,
        next: null,
        previous: null,
        results: [systemRootFolderFixture, systemChildFolderFixture],
      }),
    })
  })
  await page.route('**/api/v1/health/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        service: 'wind-doc-system-backend',
        debug: true,
        request_id: 'health-001',
      }),
    })
  })

  await page.goto('/system/status')

  await expect(page.getByRole('heading', { name: '系统管理' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '公共根目录 ROOT' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '运行资料 RUN' })).toBeVisible()
  await page.getByRole('button', { name: '创建目录' }).click()
  await expect(page.getByRole('heading', { name: '创建目录' })).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByRole('tab', { name: '系统状态' }).click()
  await expect(page.getByText('wind-doc-system-backend')).toBeVisible()
  await expect(page.getByText('health-001')).toBeVisible()

  await page.getByRole('tab', { name: '系统配置' }).click()
  await expect(page.getByText('后端暂未开放系统配置接口')).toBeVisible()
  await page.getByRole('tab', { name: '备份恢复' }).click()
  await expect(page.getByText('后端暂未开放备份恢复接口')).toBeVisible()
})

test('shows project management detail, members, documents and archive', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/projects/?**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [projectFixture],
      }),
    })
  })
  await page.route('**/api/v1/projects/1/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(projectFixture),
    })
  })
  await page.route('**/api/v1/projects/1/members/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([projectMemberFixture]),
    })
  })
  await page.route('**/api/v1/folders/tree/?project_id=1', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 20,
          project: 1,
          parent: null,
          name: '竣工资料档案',
          code: 'PUBLIC-COMPLETION',
          sort_order: 10,
          is_active: true,
          is_system_root: false,
          children: [],
        },
        {
          id: 21,
          project: 1,
          parent: null,
          name: '人员资质',
          code: 'PUBLIC-STAFF',
          sort_order: 8,
          is_active: true,
          is_system_root: false,
          children: [],
        },
      ]),
    })
  })
  await page.route('**/api/v1/documents/?**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            ...documentFixture,
            project: 1,
            project_name: '前端联调示例项目',
            folder: 20,
            folder_name: '竣工资料档案',
          },
        ],
      }),
    })
  })
  await page.route('**/api/v1/projects/1/archive/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ ...projectFixture, status: 'archived', archived_at: '2026-06-25T10:00:00+08:00' }),
    })
  })

  await page.goto('/projects')

  await expect(page.getByRole('heading', { name: '项目管理' })).toBeVisible()
  await expect(page.getByText('前端联调示例项目')).toBeVisible()
  await page.getByRole('button', { name: '详情' }).click()

  await expect(page.getByRole('heading', { name: '前端联调示例项目' })).toBeVisible()
  await page.getByRole('tab', { name: '项目成员' }).click()
  await expect(page.getByRole('cell', { name: 'manager' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '项目负责人' })).toBeVisible()

  await page.getByRole('tab', { name: '项目资料' }).click()
  await expect(page.getByRole('button', { name: '竣工资料档案' })).toHaveCount(0)
  await expect(page.getByText('安全生产许可证')).toBeVisible()
  await page.getByRole('button', { name: '上传资料' }).click()
  await expect(page.getByRole('heading', { name: '上传资料' })).toBeVisible()
  await page.getByPlaceholder('选择目录').click()
  await expect(page.getByText('人员资质')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')

  await page.getByRole('tab', { name: '归档信息' }).click()
  await page.getByRole('button', { name: '归档项目' }).click()
  await expect(page.getByLabel('归档信息').getByText('已归档')).toBeVisible()
})

async function mockAuthenticatedSession(page: Page): Promise<void> {
  await page.route('**/api/v1/auth/csrf/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ csrfToken: 'test-csrf-token' }),
    })
  })
  await page.route('**/api/v1/auth/me/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        username: 'admin',
        real_name: '管理员',
        employee_no: 'A001',
        role: 'system_admin',
        phone: '',
        email: 'admin@example.com',
        is_active: true,
        must_change_password: false,
        created_at: '2026-06-25T10:00:00+08:00',
      }),
    })
  })
}

async function mockAccessEndpoints(page: Page): Promise<void> {
  await page.route('**/api/v1/document-grants/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    })
  })
  await page.route('**/api/v1/temporary-access-grants/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: 0,
        next: null,
        previous: null,
        results: [],
      }),
    })
  })
}

const documentFixture = {
  id: 1,
  project: null,
  project_name: null,
  folder: 10,
  folder_name: '公司资质',
  title: '安全生产许可证',
  description: '证照扫描件',
  access_level: 'internal',
  current_version: {
    id: 100,
    document: 1,
    version_number: 1,
    original_filename: 'license.pdf',
    content_type: 'application/pdf',
    file_size: 2048,
    sha256: 'abc',
    uploaded_by: 1,
    uploaded_by_name: '管理员',
    created_at: '2026-06-25T10:00:00+08:00',
  },
  lock_version: 1,
  deleted_at: null,
  deleted_by: null,
  deleted_by_name: null,
  created_by: 1,
  created_by_name: '管理员',
  created_at: '2026-06-25T10:00:00+08:00',
  updated_at: '2026-06-25T10:00:00+08:00',
}

const documentGrantFixture = {
  id: 501,
  document: 1,
  document_title: '安全生产许可证',
  user: 4,
  user_username: 'grant-user',
  user_real_name: '授权用户',
  can_view: true,
  can_download: true,
  can_update: false,
  can_delete: false,
  can_restore: false,
  can_manage: false,
  expires_at: '2026-07-25T10:00:00+08:00',
  is_expired: false,
  is_active: true,
  created_by: 1,
  created_by_name: '管理员',
  created_at: '2026-06-25T10:00:00+08:00',
  updated_at: '2026-06-25T10:00:00+08:00',
  revoked_at: null,
  revoked_by: null,
  revoked_by_name: '',
}

const temporaryAccessFixture = {
  id: 601,
  document_version: 100,
  document: 1,
  document_title: '安全生产许可证',
  original_filename: 'license.pdf',
  max_downloads: 1,
  used_count: 0,
  remaining_downloads: 1,
  expires_at: '2026-06-26T10:00:00+08:00',
  is_expired: false,
  is_active: true,
  created_by: 1,
  created_by_name: '管理员',
  created_at: '2026-06-25T10:00:00+08:00',
  revoked_at: null,
  revoked_by: null,
  revoked_by_name: '',
  last_used_at: null,
}

const temporaryAccessCreatedFixture = {
  ...temporaryAccessFixture,
  token: 'temp-token-001',
  download_url: 'http://127.0.0.1:8000/api/v1/temporary-access/temp-token-001/download/',
}

const userFixture = {
  id: 2,
  username: 'operator',
  real_name: '资料整理员',
  employee_no: 'D002',
  role: 'data_operator',
  phone: '13800000000',
  email: 'operator@example.com',
  is_active: true,
  must_change_password: false,
  created_at: '2026-06-25T10:00:00+08:00',
}

const auditLogFixture = {
  id: 700,
  user: 1,
  user_username: 'admin',
  user_real_name: '管理员',
  action: 'document.download',
  resource_type: 'Document',
  resource_id: '1',
  result: 'success',
  ip_address: '127.0.0.1',
  user_agent: 'Playwright',
  request_id: 'req-700',
  before_data: null,
  after_data: { document_id: 1 },
  error_message: '',
  created_at: '2026-06-25T10:00:00+08:00',
}

const notificationFixture = {
  id: 800,
  title: '受限文档授权已创建',
  message: '管理员为你创建了受限文档授权。',
  category: 'access',
  resource_type: 'DocumentGrant',
  resource_id: '501',
  is_read: false,
  read_at: null,
  created_at: '2026-06-25T10:00:00+08:00',
}

const systemRootFolderFixture = {
  id: 10,
  project: null,
  project_name: null,
  parent: null,
  name: '公共根目录',
  code: 'ROOT',
  sort_order: 0,
  is_active: true,
  is_system_root: true,
  created_by: 1,
  created_by_name: '管理员',
  created_at: '2026-06-25T10:00:00+08:00',
  updated_at: '2026-06-25T10:00:00+08:00',
}

const systemChildFolderFixture = {
  id: 11,
  project: null,
  project_name: null,
  parent: 10,
  name: '运行资料',
  code: 'RUN',
  sort_order: 10,
  is_active: true,
  is_system_root: false,
  created_by: 1,
  created_by_name: '管理员',
  created_at: '2026-06-25T10:00:00+08:00',
  updated_at: '2026-06-25T10:00:00+08:00',
}

const projectFixture = {
  id: 1,
  name: '前端联调示例项目',
  code: 'DEMO-FRONTEND',
  description: '项目说明',
  manager: 2,
  manager_name: '项目负责人',
  status: 'active',
  created_by: 1,
  created_by_name: '管理员',
  created_at: '2026-06-25T10:00:00+08:00',
  updated_at: '2026-06-25T10:00:00+08:00',
  archived_at: null,
  archived_by: null,
}

const projectMemberFixture = {
  id: 10,
  project: 1,
  user: 2,
  user_username: 'manager',
  user_real_name: '项目负责人',
  role: 'manager',
  can_upload: true,
  can_download_restricted: true,
  can_manage_folder: true,
  can_delete: true,
  can_restore: true,
  can_manage_permission: true,
  joined_at: '2026-06-25T10:00:00+08:00',
}
