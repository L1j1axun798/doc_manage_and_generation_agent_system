import { apiClient } from '@/core/http/client'
import type { AvailableAgentPersonnel } from '../document-generation.types'

export async function fetchAvailableAgentPersonnel(
  projectId: number,
): Promise<AvailableAgentPersonnel[]> {
  const response = await apiClient.get<AvailableAgentPersonnel[]>(
    '/document-generation/tasks/available-personnel/',
    { params: { project_id: projectId } },
  )
  return response.data.map((person) => ({
    ...person,
    job_title: '',
    department: '',
    contact: person.phone,
    certifications: [],
    certificate_valid_until: null,
    additional_info: {
      personnel_folder_id: person.folder_id,
      profile_complete: person.profile_complete,
    },
  }))
}
