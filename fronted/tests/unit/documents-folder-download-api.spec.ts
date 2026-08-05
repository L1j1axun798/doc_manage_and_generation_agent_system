import { afterEach, expect, it, vi } from 'vitest'

import { apiClient } from '@/core/http/client'
import { saveBlob } from '@/core/http/download'
import {
  downloadDocumentCenter,
  downloadFolder,
} from '@/modules/documents/api/documents.api'

vi.mock('@/core/http/download', async () => {
  const actual = await vi.importActual<typeof import('@/core/http/download')>(
    '@/core/http/download',
  )
  return {
    ...actual,
    saveBlob: vi.fn(),
  }
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

it('downloads a folder ZIP using the response filename', async () => {
  const archive = new Blob(['zip'], { type: 'application/zip' })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: archive,
    status: 200,
    headers: {
      'content-disposition': "attachment; filename*=UTF-8''%E8%B5%84%E6%96%99.zip",
    },
  })

  await downloadFolder(42)

  expect(post).toHaveBeenCalledWith(
    '/documents/folder-download/',
    { folder: 42 },
    expect.objectContaining({
      responseType: 'blob',
      validateStatus: expect.any(Function),
    }),
  )
  expect(saveBlob).toHaveBeenCalledWith(archive, '资料.zip')
})

it('downloads the complete document center ZIP', async () => {
  const archive = new Blob(['zip'], { type: 'application/zip' })
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: archive,
    status: 200,
    headers: {
      'content-disposition': (
        "attachment; filename*=UTF-8''%E8%B5%84%E6%96%99%E4%B8%AD%E5%BF%83"
        + "%E5%85%A8%E9%83%A8%E8%B5%84%E6%96%99.zip"
      ),
    },
  })

  await downloadDocumentCenter()

  expect(post).toHaveBeenCalledWith(
    '/documents/center-download/',
    {},
    expect.objectContaining({
      responseType: 'blob',
      validateStatus: expect.any(Function),
    }),
  )
  expect(saveBlob).toHaveBeenCalledWith(archive, '资料中心全部资料.zip')
})

it('surfaces the backend detail for a failed folder download', async () => {
  const errorBlob = {
    text: vi.fn().mockResolvedValue(JSON.stringify({
      message: '当前目录及子目录没有可下载文件',
    })),
  } as unknown as Blob
  vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: errorBlob,
    status: 400,
    headers: {},
  })

  await expect(downloadFolder(42)).rejects.toMatchObject({
    status: 400,
    detail: '当前目录及子目录没有可下载文件',
  })
  expect(saveBlob).not.toHaveBeenCalled()
})
