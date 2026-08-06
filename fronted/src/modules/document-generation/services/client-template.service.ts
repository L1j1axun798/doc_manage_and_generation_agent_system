import { uploadDocument } from '@/modules/documents/api/documents.api'
import { fetchFolderTree } from '@/modules/documents/api/folders.api'
import type { DocumentItem, FolderTreeNode } from '@/modules/documents/documents.types'
import { uploadGenerationTemplate } from '../api/document-generation.api'
import type { TemplateSelectionResult } from '../document-generation.types'

const ENTRY_PREPARATION_ROOT_CODE = 'PUBLIC-COMPLETION'

function findFolderByCode(folders: FolderTreeNode[], code: string): FolderTreeNode | null {
  for (const folder of folders) {
    if (folder.code === code && folder.is_active) {
      return folder
    }
    const nested = findFolderByCode(folder.children, code)
    if (nested) {
      return nested
    }
  }
  return null
}

async function uploadEntryPreparationFile(
  projectId: number,
  file: File,
  description: string,
): Promise<DocumentItem> {
  const folders = await fetchFolderTree(projectId)
  const target = findFolderByCode(folders, ENTRY_PREPARATION_ROOT_CODE)
  if (!target) {
    throw new Error('当前项目缺少“入场前置资料”目录，请联系项目负责人处理')
  }
  return uploadDocument({
    folder: target.id,
    file,
    title: file.name.replace(/\.[^.]+$/, ''),
    description,
    access_level: 'internal',
    source_type: 'entrance_material',
  })
}

export async function uploadClientTemplate(
  projectId: number,
  file: File,
): Promise<TemplateSelectionResult> {
  return uploadGenerationTemplate(projectId, file)
}

export async function uploadConversationAttachment(
  projectId: number,
  file: File,
): Promise<DocumentItem> {
  return uploadEntryPreparationFile(
    projectId,
    file,
    '四措两案 Agent 当前会话使用的入场前置资料。',
  )
}
