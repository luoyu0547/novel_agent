import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/writingStudio'
import type {
  WritingSession,
  WritingMessage,
  StudioDocument,
  StudioWorkspace,
  StudioConfirmationAction,
} from '@/types/writingStudio'

export const useWritingStudioStore = defineStore('writingStudio', () => {
  const session = ref<WritingSession | null>(null)
  const messages = ref<WritingMessage[]>([])
  const document = ref<StudioDocument | null>(null)
  const saveState = ref<'idle' | 'saving' | 'saved' | 'conflict' | 'error'>('idle')

  function hydrate(workspace: StudioWorkspace): void {
    session.value = workspace.session
    messages.value = workspace.messages
    document.value = workspace.working_copy
      ? {
          kind: 'draft',
          writingRunId: workspace.working_copy.writing_run_id,
          draftVersionId: workspace.working_copy.draft_version_id,
          title: workspace.working_copy.title,
          content: workspace.working_copy.content,
          baseRevisionSequence: workspace.working_copy.base_revision_sequence,
        }
      : null
  }

  async function loadSession(novelId: number, sessionId: number): Promise<void> {
    hydrate(await api.getStudioSession(novelId, sessionId))
  }

  async function sendMessage(novelId: number, text: string): Promise<void> {
    if (!session.value) throw new Error('请先选择创作会话')
    const result = await api.sendStudioMessage(novelId, session.value.id, {
      text,
      idempotency_key: crypto.randomUUID(),
    })
    hydrate(result.workspace)
  }

  async function confirmAction(
    novelId: number,
    messageId: number,
    action: StudioConfirmationAction,
    payload: Record<string, unknown> = {},
  ): Promise<void> {
    if (!session.value) throw new Error('请先选择创作会话')
    const result = await api.confirmStudioAction(novelId, session.value.id, messageId, {
      action,
      payload,
    })
    hydrate(result.workspace)
  }

  async function saveWorkingCopy(novelId: number): Promise<void> {
    if (!session.value || !document.value || document.value.kind !== 'draft') return
    saveState.value = 'saving'
    try {
      const copy = await api.saveStudioWorkingCopy(novelId, session.value.id, {
        title: document.value.title,
        content: document.value.content,
        base_revision_sequence: document.value.baseRevisionSequence,
      })
      document.value.baseRevisionSequence = copy.base_revision_sequence
      saveState.value = 'saved'
    } catch (error) {
      saveState.value =
        error instanceof Error && error.message.includes('基础修订序列已过期')
          ? 'conflict'
          : 'error'
      throw error
    }
  }

  return {
    session,
    messages,
    document,
    saveState,
    loadSession,
    sendMessage,
    confirmAction,
    saveWorkingCopy,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useWritingStudioStore, import.meta.hot))
}
