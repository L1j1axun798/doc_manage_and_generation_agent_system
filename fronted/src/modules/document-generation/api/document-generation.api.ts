import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type {
  ConfirmedFactPayload,
  CreateGenerationPipelinePayload,
  CreateGenerationTaskPayload,
  DocumentGenerationTemplate,
  GeneratedSection,
  GenerationTask,
  GenerationTraceEvent,
} from '../document-generation.types'

const TASKS = '/document-generation/tasks'

export async function fetchGenerationTemplates(): Promise<DocumentGenerationTemplate[]> {
  const response = await apiClient.get<DocumentGenerationTemplate[]>(
    '/document-generation/templates/',
  )
  return response.data
}

export async function fetchGenerationTasks(projectId: number): Promise<ApiPage<GenerationTask>> {
  const response = await apiClient.get<ApiPage<GenerationTask>>(`${TASKS}/`, {
    params: { project: projectId, ordering: '-created_at' },
  })
  return response.data
}

export async function fetchGenerationTask(taskId: string): Promise<GenerationTask> {
  const response = await apiClient.get<GenerationTask>(`${TASKS}/${taskId}/`)
  return response.data
}

export async function createGenerationTask(
  payload: CreateGenerationTaskPayload,
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/`, payload)
  return response.data
}

export async function startGenerationPipeline(
  payload: CreateGenerationPipelinePayload,
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/pipeline/`, payload)
  return response.data
}

export async function addGenerationSources(
  taskId: string,
  documentVersionIds: number[],
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/sources/`, {
    document_version_ids: documentVersionIds,
  })
  return response.data
}

export async function extractGenerationFacts(taskId: string): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/extract/`)
  return response.data
}

export async function confirmGenerationFacts(
  taskId: string,
  facts: ConfirmedFactPayload[],
): Promise<GenerationTask> {
  const response = await apiClient.put<GenerationTask>(`${TASKS}/${taskId}/facts/confirm/`, {
    facts,
  })
  return response.data
}

export async function confirmAndGenerate(
  taskId: string,
  facts: ConfirmedFactPayload[],
): Promise<GenerationTask> {
  const response = await apiClient.put<GenerationTask>(
    `${TASKS}/${taskId}/facts/confirm-and-generate/`,
    { facts },
  )
  return response.data
}

export async function fetchGenerationEvents(
  taskId: string,
  afterSequence = 0,
): Promise<GenerationTraceEvent[]> {
  const response = await apiClient.get<GenerationTraceEvent[]>(`${TASKS}/${taskId}/events/`, {
    params: { after_sequence: afterSequence },
  })
  return response.data
}

export async function generateEntryPlan(taskId: string): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/generate/`)
  return response.data
}

export async function retryGenerationTask(taskId: string): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/retry/`)
  return response.data
}

export async function updateGeneratedSection(
  taskId: string,
  sectionCode: string,
  content: string,
  expectedRevision: number,
): Promise<GeneratedSection> {
  const response = await apiClient.patch<GeneratedSection>(
    `${TASKS}/${taskId}/sections/${sectionCode}/`,
    { content, expected_revision: expectedRevision },
  )
  return response.data
}

export async function setGeneratedSectionLock(
  taskId: string,
  sectionCode: string,
  locked: boolean,
): Promise<GeneratedSection> {
  const response = await apiClient.post<GeneratedSection>(
    `${TASKS}/${taskId}/sections/${sectionCode}/lock/`,
    { locked },
  )
  return response.data
}

export async function lockAllGeneratedSections(taskId: string): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(
    `${TASKS}/${taskId}/sections/lock-all/`,
  )
  return response.data
}

export async function regenerateSection(
  taskId: string,
  sectionCode: string,
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(
    `${TASKS}/${taskId}/sections/${sectionCode}/regenerate/`,
  )
  return response.data
}

export async function submitGenerationReview(
  taskId: string,
  comment = '',
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/submit-review/`, {
    comment,
  })
  return response.data
}

export async function approveGenerationTask(
  taskId: string,
  comment = '',
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/approve/`, {
    comment,
  })
  return response.data
}

export async function exportGenerationTask(
  taskId: string,
  idempotencyKey: string,
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/export/`, {
    idempotency_key: idempotencyKey,
  })
  return response.data
}
