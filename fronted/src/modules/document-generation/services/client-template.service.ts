import { uploadDocument } from '@/modules/documents/api/documents.api'
import { fetchFolderTree } from '@/modules/documents/api/folders.api'
import type { DocumentItem, FolderTreeNode } from '@/modules/documents/documents.types'
import type { ClientTemplateCandidate } from '../document-generation.types'

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

export async function uploadClientTemplateCandidate(
  projectId: number,
  file: File,
): Promise<ClientTemplateCandidate> {
  if (!file.name.toLowerCase().endsWith('.docx')) {
    throw new Error('甲方模板仅支持 DOCX 文件')
  }
  const document = await uploadEntryPreparationFile(
    projectId,
    file,
    '四措两案 Agent 上传的甲方模板候选；完成审核和模板登记后方可用于正式生成。',
  )
  if (!document.current_version) {
    throw new Error('模板已上传但未返回可用版本，请刷新资料中心后重试')
  }
  return {
    document_id: document.id,
    document_version_id: document.current_version.id,
    filename: document.current_version.original_filename,
    title: document.title,
    registration_status: 'pending_registration',
  }
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
