import { afterEach, expect, it, vi } from 'vitest'

import { apiClient } from '@/core/http/client'
import { fetchAvailableAgentPersonnel } from '@/modules/document-generation/services/personnel.service'

afterEach(() => {
  vi.restoreAllMocks()
})

it('loads Agent personnel from the public staff personnel endpoint', async () => {
  const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
    data: [
      {
        id: '42',
        folder_id: 42,
        name: '张三',
        gender: 'male',
        gender_display: '男',
        id_card_number: '110101199001010011',
        phone: '13800000000',
        profile_complete: true,
        updated_at: '2026-08-06T10:00:00+08:00',
      },
    ],
  })

  const rows = await fetchAvailableAgentPersonnel(7)

  expect(get).toHaveBeenCalledWith(
    '/document-generation/tasks/available-personnel/',
    { params: { project_id: 7 } },
  )
  expect(rows[0]).toMatchObject({
    id: '42',
    folder_id: 42,
    name: '张三',
    id_card_number: '110101199001010011',
    phone: '13800000000',
    contact: '13800000000',
  })
})
