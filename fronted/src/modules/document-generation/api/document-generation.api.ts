import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type {
  ConfirmedFactPayload,
  CreateGenerationPipelinePayload,
  CreateGenerationTaskPayload,
  DocumentGenerationTemplate,
  GeneratedSection,
  GenerationExportInfo,
  GenerationTask,
  GenerationTraceEvent,
  KnowledgeCorpusUpload,
  RagOverview,
} from '../document-generation.types'

const TASKS = '/document-generation/tasks'
const KNOWLEDGE_UPLOADS = '/document-generation/knowledge-uploads'

export async function fetchRagOverview(): Promise<RagOverview> {
  const response = await apiClient.get<RagOverview>('/document-generation/overview/')
  return response.data
}

export async function fetchGenerationTemplates(): Promise<DocumentGenerationTemplate[]> {
  const response = await apiClient.get<DocumentGenerationTemplate[]>(
    '/document-generation/templates/',
  )
  return response.data
}

export async function fetchKnowledgeCorpusUploads(
  page = 1,
): Promise<ApiPage<KnowledgeCorpusUpload>> {
  const response = await apiClient.get<ApiPage<KnowledgeCorpusUpload>>(
    `${KNOWLEDGE_UPLOADS}/`,
    { params: { ordering: '-created_at', page } },
  )
  return response.data
}

export async function uploadKnowledgeCorpus(
  payload: FormData,
): Promise<KnowledgeCorpusUpload> {
  const response = await apiClient.post<KnowledgeCorpusUpload>(
    `${KNOWLEDGE_UPLOADS}/`,
    payload,
  )
  return response.data
}

export async function retryKnowledgeCorpusUpload(
  uploadId: string,
): Promise<KnowledgeCorpusUpload> {
  const response = await apiClient.post<KnowledgeCorpusUpload>(
    `${KNOWLEDGE_UPLOADS}/${uploadId}/retry/`,
  )
  return response.data
}

export async function fetchGenerationTasks(
  projectId: number,
  page = 1,
): Promise<ApiPage<GenerationTask>> {
  const response = await apiClient.get<ApiPage<GenerationTask>>(`${TASKS}/`, {
    params: { project: projectId, ordering: '-created_at', page },
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

export async function stopGenerationTask(taskId: string): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/stop/`)
  return response.data
}

export async function deleteGenerationTask(taskId: string): Promise<void> {
  await apiClient.delete(`${TASKS}/${taskId}/`)
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
  instruction: string,
  ragChunkIds: string[] = [],
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(
    `${TASKS}/${taskId}/sections/${sectionCode}/regenerate/`,
    {
      instruction,
      rag_chunk_ids: ragChunkIds,
    },
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
  filename: string,
): Promise<GenerationTask> {
  const response = await apiClient.post<GenerationTask>(`${TASKS}/${taskId}/export/`, {
    idempotency_key: idempotencyKey,
    filename,
  })
  return response.data
}

export async function fetchGenerationExportInfo(
  taskId: string,
): Promise<GenerationExportInfo> {
  const response = await apiClient.get<GenerationExportInfo>(
    `${TASKS}/${taskId}/export-info/`,
  )
  return response.data
}
