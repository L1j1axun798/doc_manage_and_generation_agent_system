import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type { Project, ProjectListQuery, ProjectPayload } from '../projects.types'

export async function fetchProjects(query: ProjectListQuery): Promise<ApiPage<Project>> {
  const response = await apiClient.get<ApiPage<Project>>('/projects/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function fetchProject(projectId: number): Promise<Project> {
  const response = await apiClient.get<Project>(`/projects/${projectId}/`)
  return response.data
}

export async function createProject(payload: ProjectPayload): Promise<Project> {
  const response = await apiClient.post<Project>('/projects/', payload)
  return response.data
}

export async function updateProject(projectId: number, payload: ProjectPayload): Promise<Project> {
  const response = await apiClient.patch<Project>(`/projects/${projectId}/`, payload)
  return response.data
}

export async function archiveProject(projectId: number): Promise<Project> {
  const response = await apiClient.post<Project>(`/projects/${projectId}/archive/`)
  return response.data
}

export async function unarchiveProject(projectId: number): Promise<Project> {
  const response = await apiClient.post<Project>(`/projects/${projectId}/unarchive/`)
  return response.data
}

function cleanQuery(query: ProjectListQuery): ProjectListQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
