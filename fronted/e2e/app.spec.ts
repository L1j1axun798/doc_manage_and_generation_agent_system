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

test('shows the admin personnel map and RAG overview on the dashboard', async ({ page }) => {
  await mockAuthenticatedSession(page)
  const pageResult = {
    count: 1,
    next: null,
    previous: null,
    results: [{}],
  }
  await page.route('**/api/v1/documents/?**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(pageResult) })
  })
  await page.route('**/api/v1/projects/?**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(pageResult) })
  })
  await page.route('**/api/v1/notifications/?**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(pageResult) })
  })
  await page.route('**/api/v1/document-grants/?**', async (route) => {
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(pageResult) })
  })
  const locationSnapshot = {
    user: {
      id: 1,
      username: 'admin',
      real_name: '管理员',
      employee_no: 'A001',
      role: 'system_admin',
      phone: '',
    },
    latest_report: {
      id: 1,
      longitude: '116.397128',
      latitude: '39.916527',
      accuracy: '20.00',
      address: '北京市东城区',
      report_status: 'success',
      failure_reason: '',
      reported_at: '2026-07-30T10:00:00+08:00',
      created_at: '2026-07-30T10:00:00+08:00',
    },
    location_status: 'normal',
    should_report: false,
  }
  await page.route('**/api/v1/locations/me/latest/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(locationSnapshot),
    })
  })
  await page.route('**/api/v1/locations/admin/latest/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([locationSnapshot]),
    })
  })
  await page.route('**/api/v1/document-generation/overview/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        knowledge_status: 'ready',
        knowledge_chunks: 948,
        source_documents: 27,
        covered_section_count: 8,
        total_section_count: 8,
        section_coverage: [
          { code: 'overview', name: '工程概况与编制依据', chunk_count: 82 },
          { code: 'organization_measures', name: '组织措施', chunk_count: 86 },
          { code: 'construction_plan', name: '施工方案', chunk_count: 132 },
          { code: 'technical_measures', name: '技术措施', chunk_count: 81 },
          { code: 'safety_measures', name: '安全措施', chunk_count: 117 },
          { code: 'risk_identification', name: '风险辨识与预控', chunk_count: 31 },
          { code: 'emergency_plan', name: '应急预案', chunk_count: 373 },
          { code: 'environmental_measures', name: '环境保护与文明施工', chunk_count: 46 },
        ],
        last_indexed_at: '2026-07-30T11:11:26+08:00',
        embedding_model_alias: 'text-embedding-v4',
        embedding_dimension: 1024,
        operations: {
          status: 'healthy',
          redis_status: 'ok',
          worker_status: 'idle',
          queue_depth: 0,
          processing_uploads: 0,
          failed_uploads: 0,
          latest_upload_status: 'succeeded',
          latest_upload_at: '2026-07-30T11:11:26+08:00',
        },
      }),
    })
  })

  await page.goto('/dashboard')

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('首页')
  await expect(page.getByRole('heading', { name: '人员位置概览' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'RAG 知识库概览' })).toBeVisible()
  await expect(page.getByText('948', { exact: true })).toBeVisible()
  await expect(page.getByText('text-embedding-v4 · 1024 维')).toBeVisible()
  await expect(page.getByText('运行正常')).toBeVisible()
  await page.getByRole('button', { name: '切换深色模式' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  await page.getByRole('link', { name: '查看人员位置目录' }).click()
  await expect(page).toHaveURL(/\/locations\/admin/)
  await expect(page.locator('.main-layout__page-context strong')).toHaveText('人员位置')
  await expect(page.locator('.main-layout__page-description')).toHaveText(
    '查看员工最近一次上报位置，所有位置均以员工主动上报时间为准。',
  )
})

test('moves the document agent description into the main header', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/projects/?**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
    })
  })

  await page.goto('/document-generation')

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('入场资料Agent V1.0')
  const pageDescription = page.locator('.main-layout__page-description')
  await expect(pageDescription).toBeVisible()
  await expect(pageDescription).toHaveText(
    '在一个会话内完成模板、人员、资料、生成、修改与审核。',
  )
  expect(
    await pageDescription.evaluate((element) =>
      element.parentElement?.classList.contains('main-layout__header-context'),
    ),
  ).toBe(true)
  await expect(page.locator('.document-generation-page h1')).toHaveCount(0)
  await expect(page.locator('.document-generation-page')).not.toContainText(
    '在一个会话内完成模板、人员、资料、生成、修改与审核。',
  )
  await expect(page.getByRole('button', { name: '上传 RAG 资料' })).toBeVisible()

  const featuredAgentItem = page.locator('.el-menu-item.is-featured-agent')
  await expect(featuredAgentItem).toContainText('四措两案Agent V1.0')
  await expect(featuredAgentItem.locator('.main-layout__featured-badge')).toHaveText('🎉')
  await featuredAgentItem.hover()
  await expect(featuredAgentItem.locator('.main-layout__menu-liquid-bg')).toHaveCSS('opacity', '1')

  await featuredAgentItem.click({ position: { x: 116, y: 22 } })
  await expect(featuredAgentItem.locator('.main-layout__menu-burst-particle')).toHaveCount(12)
  const firstBurstId = await featuredAgentItem.locator('.main-layout__menu-burst').getAttribute('data-burst-id')
  await featuredAgentItem.click({ position: { x: 132, y: 24 } })
  await expect(featuredAgentItem.locator('.main-layout__menu-burst')).toHaveCount(1)
  await expect(featuredAgentItem.locator('.main-layout__menu-burst-particle')).toHaveCount(12)
  await expect(featuredAgentItem.locator('.main-layout__menu-burst')).not.toHaveAttribute(
    'data-burst-id',
    firstBurstId ?? '',
  )
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
      children: [
        {
          id: 11,
          project: null,
          parent: 10,
          name: '华能新能源有限公司',
          code: '',
          sort_order: 1,
          is_active: true,
          is_system_root: false,
          children: [],
        },
        {
          id: 12,
          project: null,
          parent: 10,
          name: '大唐风电有限公司',
          code: '',
          sort_order: 2,
          is_active: true,
          is_system_root: false,
          children: [],
        },
      ],
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
  await page.route('**/api/v1/folders/*/disable/', async (route) => {
    const folderId = Number(route.request().url().match(/\/folders\/(\d+)\/disable\//)?.[1])
    for (const root of publicFolderTree) {
      root.children = root.children.filter((child) => child.id !== folderId)
    }
    await route.fulfill({
      status: 204,
    })
  })
  let nextFolderId = 100
  await page.route('**/api/v1/folders/', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }

    const payload = route.request().postDataJSON() as { name: string; parent: number }
    const createdFolder: FolderTreeNode = {
      id: nextFolderId++,
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

  await expect(page.getByRole('button', { name: '公司资质' })).toBeVisible()
  await expect(page.getByRole('button', { name: '人员保险单' })).toBeVisible()
  await expect(page.getByRole('button', { name: '技术方案' })).toBeVisible()
  await expect(page.getByRole('button', { name: '报告模板' })).toBeVisible()
  await expect(page.getByRole('button', { name: '已归档文件' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '公司名单' })).toBeVisible()
  await expect(page.getByText('公司数：2')).toBeVisible()
  await expect(page.getByRole('button', { name: '华能新能源有限公司' })).toBeVisible()
  await expect(page.getByRole('button', { name: '大唐风电有限公司' })).toBeVisible()
  await expect(page.getByRole('button', { name: '上传资料' })).toHaveCount(0)
  await page.getByRole('button', { name: '添加公司' }).click()
  await page.getByRole('textbox', { name: '请输入公司名称' }).fill('中广核风电有限公司')
  await page.getByRole('button', { name: '添加', exact: true }).click()
  await expect(page.getByText('公司已添加')).toBeVisible()
  await expect(page.getByText('公司数：3')).toBeVisible()
  await expect(page.getByRole('button', { name: '中广核风电有限公司' })).toBeVisible()
  await page
    .locator('.document-subfolder-panel__item')
    .filter({ hasText: '中广核风电有限公司' })
    .getByRole('button', { name: '删除子项' })
    .click()
  await expect(page.getByText('删除公司')).toBeVisible()
  await page.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByText('公司已删除')).toBeVisible()
  await expect(page.getByText('公司数：2')).toBeVisible()
  await expect(page.getByRole('button', { name: '中广核风电有限公司' })).toHaveCount(0)
  await page.getByRole('button', { name: '华能新能源有限公司' }).click()
  await expect(page.getByRole('button', { name: '上传资料' })).toBeVisible()
  await expect(page.locator('tbody').getByRole('button', { name: '安全生产许可证' })).toBeVisible()
  await expect(page.getByRole('link', { name: '回收站' })).toBeVisible()

  await page.getByRole('button', { name: '人员资质' }).click()
  await expect(page.getByRole('heading', { name: '人员名单' })).toBeVisible()
  await expect(page.getByText('人员数：2')).toBeVisible()
  await expect(page.getByRole('button', { name: '张三' })).toBeVisible()
  await expect(page.getByRole('button', { name: '李四' })).toBeVisible()
  await expect(page.getByRole('button', { name: '上传资料' })).toHaveCount(0)
  await page.getByRole('button', { name: '添加用户' }).click()
  await page.getByRole('textbox', { name: '请输入人员姓名' }).fill('王五')
  await page.getByRole('button', { name: '添加', exact: true }).click()
  await expect(page.getByText('用户已添加')).toBeVisible()
  await expect(page.getByText('人员数：3')).toBeVisible()
  await expect(page.getByRole('button', { name: '王五' })).toBeVisible()
  await page
    .locator('.document-subfolder-panel__item')
    .filter({ hasText: '王五' })
    .getByRole('button', { name: '删除子项' })
    .click()
  await expect(page.getByText('删除人员')).toBeVisible()
  await page.getByRole('button', { name: '删除', exact: true }).click()
  await expect(page.getByText('人员已删除')).toBeVisible()
  await expect(page.getByText('人员数：2')).toBeVisible()
  await expect(page.getByRole('button', { name: '王五' })).toHaveCount(0)

  await page.getByRole('button', { name: '张三' }).click()
  await expect(page.getByRole('button', { name: '上传资料' })).toBeVisible()
  await expect(page.locator('tbody').getByRole('button', { name: '安全生产许可证' })).toBeVisible()
  await page.getByRole('button', { name: '关闭模块' }).click()
  await expect(page.getByRole('heading', { name: '人员名单' })).toBeVisible()
  await expect(page.getByRole('button', { name: '张三' })).toBeVisible()
  await expect(page.getByRole('button', { name: '上传资料' })).toHaveCount(0)
  await page.getByRole('button', { name: '张三' }).click()
  await expect(page.getByRole('button', { name: '上传资料' })).toBeVisible()

  await page.getByRole('button', { name: '技术方案' }).click()
  await expect(page.getByRole('heading', { name: '部件分类' })).toHaveCount(0)
  await expect(page.locator('tbody').getByRole('button', { name: '安全生产许可证' })).toBeVisible()

  await page.getByRole('button', { name: '详情' }).click()
  await expect(page.getByText('文档详情')).toBeVisible()
  await expect(page.getByLabel('基础信息').getByText('license.pdf', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByText('文档详情')).toBeHidden()

  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载', exact: true }).click()
  await expect((await download).suggestedFilename()).toBe('license.pdf')

  await page.getByRole('button', { name: '上传资料' }).click()
  await expect(page.getByRole('heading', { name: '上传资料' })).toBeVisible()
})

test('shows archived year documents as read-only table', async ({ page }) => {
  await mockAuthenticatedSession(page)
  await page.route('**/api/v1/folders/tree/**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 90,
          project: null,
          parent: null,
          name: '已归档文件',
          code: 'PUBLIC-ARCHIVE',
          sort_order: 99,
          is_active: true,
          is_system_root: true,
          children: [
            {
              id: 91,
              project: null,
              parent: 90,
              name: '2026年归档资料',
              code: 'PUBLIC-ARCHIVE-2026',
              sort_order: 2026,
              is_active: true,
              is_system_root: false,
              children: [],
            },
          ],
        },
      ]),
    })
  })
  const requestedFolders: Array<string | null> = []
  await page.route('**/api/v1/documents/?**', async (route) => {
    const folder = new URL(route.request().url()).searchParams.get('folder')
    requestedFolders.push(folder)
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        count: folder === '91' ? 1 : 0,
        next: null,
        previous: null,
        results:
          folder === '91'
            ? [
                {
                  ...documentFixture,
                  id: 91,
                  project: 2,
                  project_name: 'P002 归档项目',
                  folder: 93,
                  folder_name: '竣工资料档案',
                  title: '归档检测报告',
                },
              ]
            : [],
      }),
    })
  })
  await mockAccessEndpoints(page)

  await page.goto('/documents')

  await expect(page.getByRole('button', { name: '2026年归档资料' })).toBeVisible()
  expect(requestedFolders).not.toContain('90')
  await expect(page.getByText('归档检测报告')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '上传资料' })).toHaveCount(0)

  await page.getByRole('button', { name: '已归档文件' }).click()
  await expect(page.getByRole('button', { name: '2026年归档资料' })).toBeVisible()
  await page.getByRole('button', { name: '2026年归档资料' }).click()

  await expect(page.locator('tbody').getByRole('button', { name: '归档检测报告' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'P002 归档项目' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '竣工资料档案' })).toBeVisible()
  await expect(page.getByRole('button', { name: '上传资料' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '下载', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '修改' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '移动' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '新版本' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '删除' })).toHaveCount(0)
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
          name: '技术方案',
          code: 'PUBLIC-TECH-SOLUTION',
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
  await page.route('**/api/v1/users/?**', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
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
    /\/share#token=temp-token-001/,
  )
})

test('downloads from temporary access page', async ({ page }) => {
  await page.route('**/api/v1/temporary-access/download/', async (route) => {
    expect(route.request().method()).toBe('POST')
    expect(route.request().postDataJSON()).toEqual({ token: 'temp-token-001' })
    await route.fulfill({
      contentType: 'application/pdf',
      headers: {
        'Content-Disposition': "attachment; filename*=UTF-8''temporary.pdf",
      },
      body: 'temporary file',
    })
  })

  await page.goto('/share#token=temp-token-001')

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

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('授权管理')
  await expect(page.locator('.main-layout__page-description')).toHaveText(
    '查询可管理范围内的文档授权和临时访问授权。',
  )
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

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('用户管理')
  await expect(page.locator('.main-layout__page-description')).toHaveText(
    '维护系统账号、角色、状态和首次登录改密要求。',
  )
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

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('审计中心')
  await expect(page.locator('.main-layout__page-description')).toHaveText(
    '查询系统关键操作、权限拒绝、下载和授权记录。',
  )
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

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('通知中心')
  await expect(page.locator('.main-layout__page-description')).toHaveText(
    '查看系统、文档和授权相关通知，并维护单条通知的已读状态。',
  )
  await expect(page.getByRole('button', { name: '受限文档授权已创建' })).toBeVisible()
  await page.getByRole('button', { name: '详情' }).click()
  await expect(page.getByText('通知详情')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '标已读' }).click()
  await expect(page.getByText('已标记为已读')).toBeVisible()
})

test('shows system management directories, status and backup state', async ({ page }) => {
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
  await page.route('**/api/v1/system/backups/latest/', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        trigger: 'scheduled',
        status: 'success',
        started_at: '2026-07-09T01:00:00+08:00',
        finished_at: '2026-07-09T01:05:00+08:00',
        local_available: true,
        offsite_available: false,
        sha256: 'a'.repeat(64),
        size_bytes: 1048576,
        error_summary: '',
        created_by: null,
        created_by_username: '',
        created_by_real_name: '',
        created_at: '2026-07-09T01:00:00+08:00',
        updated_at: '2026-07-09T01:05:00+08:00',
      }),
    })
  })

  await page.goto('/system/status')

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('系统管理')
  await expect(page.locator('.main-layout__page-description')).toHaveText(
    '维护资料目录，查看后端健康状态；未开放的系统能力保持只读提示。',
  )
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
  await expect(page.getByRole('heading', { name: '系统备份状态' })).toBeVisible()
  await expect(page.getByText('计划任务')).toBeVisible()
  await expect(page.getByText('待定期下载')).toBeVisible()
  await expect(page.getByText('已生成')).toBeVisible()
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

  await expect(page.locator('.main-layout__page-context strong')).toHaveText('项目管理')
  await expect(page.locator('.main-layout__page-description')).toHaveText(
    '查询当前账号可见项目，并进入项目详情维护成员和资料。',
  )
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
  await page.getByRole('combobox', { name: /目录/ }).click()
  await expect(page.getByText('人员资质')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '取消' }).click()

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
        webauthn_enabled: true,
        webauthn_credentials_count: 1,
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
  can_download: true,
  can_update: true,
  can_delete: true,
  can_restore: true,
  can_create_version: true,
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
  download_url: '/share#token=temp-token-001',
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
  webauthn_enabled: true,
  webauthn_credentials_count: 1,
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
  can_download_restricted: true,
  can_manage_folder: true,
  can_delete: true,
  can_restore: true,
  can_manage_permission: true,
  joined_at: '2026-06-25T10:00:00+08:00',
}
