import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type { ProjectMember, ProjectMemberPayload } from '../projects.types'

export async function fetchProjectMembers(projectId: number): Promise<ProjectMember[]> {
  const response = await apiClient.get<ProjectMember[] | ApiPage<ProjectMember>>(
    `/projects/${projectId}/members/`,
  )
  return Array.isArray(response.data) ? response.data : response.data.results
}

export async function createProjectMember(
  projectId: number,
  payload: ProjectMemberPayload,
): Promise<ProjectMember> {
  const response = await apiClient.post<ProjectMember>(`/projects/${projectId}/members/`, payload)
  return response.data
}

export async function updateProjectMember(
  projectId: number,
  memberId: number,
  payload: ProjectMemberPayload,
): Promise<ProjectMember> {
  const response = await apiClient.patch<ProjectMember>(
    `/projects/${projectId}/members/${memberId}/`,
    payload,
  )
  return response.data
}

export async function deleteProjectMember(projectId: number, memberId: number): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/members/${memberId}/`)
}
