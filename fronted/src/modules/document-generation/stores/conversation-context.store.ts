import { defineStore } from 'pinia'
import { reactive } from 'vue'

import type { ClientTemplateCandidate } from '../document-generation.types'

export interface DraftConversationContext {
  projectId: number
  templateId: number | null
  personnelIds: number[]
  sourceVersionIds: number[]
  message: string
  pendingTemplateCandidates: ClientTemplateCandidate[]
}

function emptyDraft(projectId: number): DraftConversationContext {
  return {
    projectId,
    templateId: null,
    personnelIds: [],
    sourceVersionIds: [],
    message: '',
    pendingTemplateCandidates: [],
  }
}

export const useConversationContextStore = defineStore('document-generation-conversation-context', () => {
  const drafts = reactive<Record<number, DraftConversationContext>>({})

  function forProject(projectId: number): DraftConversationContext {
    drafts[projectId] ||= emptyDraft(projectId)
    return drafts[projectId]
  }

  function reset(projectId: number): DraftConversationContext {
    drafts[projectId] = emptyDraft(projectId)
    return drafts[projectId]
  }

  return {
    drafts,
    forProject,
    reset,
  }
})
