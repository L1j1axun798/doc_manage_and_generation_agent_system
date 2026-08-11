import { afterEach, expect, it, vi } from 'vitest'

import { apiClient } from '@/core/http/client'
import { saveBlob } from '@/core/http/download'
import {
  cancelArchiveDownload,
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
  const onProgress = vi.fn()
  const controller = new AbortController()
  const downloadId = '83dc299f-6a55-472a-8d33-7a1a647cc02f'
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
    data: archive,
    status: 200,
    headers: {
      'content-disposition': "attachment; filename*=UTF-8''%E8%B5%84%E6%96%99.zip",
    },
  })

  await downloadFolder(42, onProgress, controller.signal, downloadId)

  expect(post).toHaveBeenCalledWith(
    '/documents/folder-download/',
    { folder: 42, download_id: downloadId },
    expect.objectContaining({
      responseType: 'blob',
      signal: controller.signal,
      validateStatus: expect.any(Function),
    }),
  )
  expect(saveBlob).toHaveBeenCalledWith(archive, '资料.zip')
  expect(onProgress).toHaveBeenCalledWith(100)

  onProgress.mockClear()
  post.mock.calls[0]?.[2]?.onDownloadProgress?.({ loaded: 25, total: 100 } as never)
  expect(onProgress).toHaveBeenCalledWith(25)
})

it('downloads the complete document center ZIP', async () => {
  const archive = new Blob(['zip'], { type: 'application/zip' })
  const onProgress = vi.fn()
  const controller = new AbortController()
  const downloadId = '5fd775cd-5991-4662-a05f-4a1d2e332bde'
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

  await downloadDocumentCenter(onProgress, controller.signal, downloadId)

  expect(post).toHaveBeenCalledWith(
    '/documents/center-download/',
    { download_id: downloadId },
    expect.objectContaining({
      responseType: 'blob',
      signal: controller.signal,
      validateStatus: expect.any(Function),
    }),
  )
  expect(saveBlob).toHaveBeenCalledWith(archive, '资料中心全部资料.zip')
  expect(onProgress).toHaveBeenCalledWith(100)

  onProgress.mockClear()
  post.mock.calls[0]?.[2]?.onDownloadProgress?.({ loaded: 10 } as never)
  expect(onProgress).toHaveBeenCalledWith(null)
})

it('requests cooperative cancellation for an active archive download', async () => {
  const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ status: 204 })
  const downloadId = '72ae37ec-8125-4f25-8a79-43317a0c39cc'

  await cancelArchiveDownload(downloadId)

  expect(post).toHaveBeenCalledWith(
    '/documents/archive-download-cancel/',
    { download_id: downloadId },
    { timeout: 5000 },
  )
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
