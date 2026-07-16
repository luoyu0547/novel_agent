import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/writingStudio'
import { useWritingStudioStore } from '@/stores/writingStudio'
import type { StudioWorkspace, StudioMessageResult, WritingSession, WritingMessage, DraftWorkingCopy } from '@/types/writingStudio'

// ── Fixtures ──────────────────────────────────────────────────────────

const sessionFixture: WritingSession = {
  id: 7,
  novel_id: 1,
  target_chapter_id: 42,
  active_writing_run_id: 100,
  title: '第十八章创作',
  status: 'active',
}

const assistantMessage: WritingMessage = {
  id: 20,
  session_id: 7,
  role: 'assistant',
  message_type: 'text',
  content_json: { text: '好的，我来调整结尾' },
  action_status: 'completed',
  writing_run_id: null,
  context_package_id: null,
  draft_version_id: null,
}

const workingCopyFixture: DraftWorkingCopy = {
  writing_run_id: 100,
  draft_version_id: 5,
  title: '第十八章',
  content: '草稿正文内容',
  base_revision_sequence: 3,
}

const workspaceFixture: StudioWorkspace = {
  session: sessionFixture,
  messages: [assistantMessage],
  working_copy: workingCopyFixture,
}

const messageResultFixture: StudioMessageResult = {
  assistant_message: assistantMessage,
  workspace: workspaceFixture,
}

// ── Mocks ─────────────────────────────────────────────────────────────

vi.mock('@/api/writingStudio')

// ── Tests ─────────────────────────────────────────────────────────────

describe('useWritingStudioStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('loadSession', () => {
    it('hydrates session, messages, and document from workspace', async () => {
      vi.mocked(api.getStudioSession).mockResolvedValue(workspaceFixture)

      const store = useWritingStudioStore()
      await store.loadSession(1, 7)

      expect(api.getStudioSession).toHaveBeenCalledWith(1, 7)
      expect(store.session).toEqual(sessionFixture)
      expect(store.messages).toEqual([assistantMessage])
      expect(store.document).toEqual({
        kind: 'draft',
        writingRunId: 100,
        draftVersionId: 5,
        title: '第十八章',
        content: '草稿正文内容',
        baseRevisionSequence: 3,
      })
    })

    it('sets document to null when working_copy is null', async () => {
      const workspaceNoCopy: StudioWorkspace = {
        ...workspaceFixture,
        working_copy: null,
      }
      vi.mocked(api.getStudioSession).mockResolvedValue(workspaceNoCopy)

      const store = useWritingStudioStore()
      await store.loadSession(1, 7)

      expect(store.document).toBeNull()
    })
  })

  describe('sendMessage', () => {
    it('keeps a pending author message and replaces it with the server session result', async () => {
      vi.mocked(api.sendStudioMessage).mockResolvedValue(messageResultFixture)
      const store = useWritingStudioStore()
      store.session = sessionFixture

      await store.sendMessage(1, '让结尾更克制')

      expect(api.sendStudioMessage).toHaveBeenCalledWith(
        1,
        7,
        expect.objectContaining({ text: '让结尾更克制' }),
      )
      expect(store.messages[store.messages.length - 1]?.role).toBe('assistant')
    })

    it('throws when no session is loaded', async () => {
      const store = useWritingStudioStore()
      store.session = null

      await expect(store.sendMessage(1, 'hello')).rejects.toThrow('请先选择创作会话')
    })

    it('uses crypto.randomUUID for idempotency_key', async () => {
      vi.mocked(api.sendStudioMessage).mockResolvedValue(messageResultFixture)
      const store = useWritingStudioStore()
      store.session = sessionFixture

      await store.sendMessage(1, 'test')

      const call = vi.mocked(api.sendStudioMessage).mock.calls[0]!
      expect(call[2].idempotency_key).toBeTruthy()
      expect(typeof call[2].idempotency_key).toBe('string')
    })
  })

  describe('confirmAction', () => {
    it('calls confirmStudioAction and hydrates workspace', async () => {
      vi.mocked(api.confirmStudioAction).mockResolvedValue(messageResultFixture)
      const store = useWritingStudioStore()
      store.session = sessionFixture

      await store.confirmAction(1, 20, 'accept')

      expect(api.confirmStudioAction).toHaveBeenCalledWith(1, 7, 20, {
        action: 'accept',
        payload: {},
      })
      expect(store.session).toEqual(sessionFixture)
    })

    it('passes custom payload', async () => {
      vi.mocked(api.confirmStudioAction).mockResolvedValue(messageResultFixture)
      const store = useWritingStudioStore()
      store.session = sessionFixture

      await store.confirmAction(1, 20, 'force_accept', { reason: '紧急' })

      expect(api.confirmStudioAction).toHaveBeenCalledWith(1, 7, 20, {
        action: 'force_accept',
        payload: { reason: '紧急' },
      })
    })

    it('throws when no session is loaded', async () => {
      const store = useWritingStudioStore()
      store.session = null

      await expect(store.confirmAction(1, 20, 'accept')).rejects.toThrow('请先选择创作会话')
    })
  })

  describe('saveWorkingCopy', () => {
    it('saves and updates baseRevisionSequence on success', async () => {
      const savedCopy: DraftWorkingCopy = {
        ...workingCopyFixture,
        base_revision_sequence: 4,
      }
      vi.mocked(api.saveStudioWorkingCopy).mockResolvedValue(savedCopy)

      const store = useWritingStudioStore()
      store.session = sessionFixture
      store.document = {
        kind: 'draft',
        writingRunId: 100,
        draftVersionId: 5,
        title: '第十八章',
        content: '修改后的正文',
        baseRevisionSequence: 3,
      }

      await store.saveWorkingCopy(1)

      expect(api.saveStudioWorkingCopy).toHaveBeenCalledWith(1, 7, {
        title: '第十八章',
        content: '修改后的正文',
        base_revision_sequence: 3,
      })
      expect(store.document?.baseRevisionSequence).toBe(4)
      expect(store.saveState).toBe('saved')
    })

    it('does not replace local document text when working-copy save fails', async () => {
      vi.mocked(api.saveStudioWorkingCopy).mockRejectedValue(new Error('network'))
      const store = useWritingStudioStore()
      store.session = sessionFixture
      store.document = {
        kind: 'draft',
        writingRunId: 100,
        draftVersionId: 5,
        title: '第十八章',
        content: '作者正文',
        baseRevisionSequence: 0,
      }

      await expect(store.saveWorkingCopy(1)).rejects.toThrow('network')
      expect(store.document?.content).toBe('作者正文')
      expect(store.saveState).toBe('error')
    })

    it('sets saveState to conflict on sequence mismatch error', async () => {
      vi.mocked(api.saveStudioWorkingCopy).mockRejectedValue(
        new Error('基础修订序列已过期，请刷新'),
      )
      const store = useWritingStudioStore()
      store.session = sessionFixture
      store.document = {
        kind: 'draft',
        writingRunId: 100,
        draftVersionId: 5,
        title: '第十八章',
        content: '作者正文',
        baseRevisionSequence: 0,
      }

      await expect(store.saveWorkingCopy(1)).rejects.toThrow('基础修订序列已过期')
      expect(store.saveState).toBe('conflict')
    })

    it('returns early when no session or document', async () => {
      const store = useWritingStudioStore()
      store.session = null
      store.document = null

      await store.saveWorkingCopy(1)

      expect(api.saveStudioWorkingCopy).not.toHaveBeenCalled()
    })

    it('returns early when document is not a draft', async () => {
      const store = useWritingStudioStore()
      store.session = sessionFixture
      store.document = {
        kind: 'chapter',
        chapterId: 42,
        title: '第十八章',
        content: '章节内容',
        baseRevisionSequence: 0,
      }

      await store.saveWorkingCopy(1)

      expect(api.saveStudioWorkingCopy).not.toHaveBeenCalled()
    })

    it('sets saveState to saving during the call', async () => {
      let resolveSave!: (value: DraftWorkingCopy) => void
      const savePromise = new Promise<DraftWorkingCopy>((resolve) => {
        resolveSave = resolve
      })
      vi.mocked(api.saveStudioWorkingCopy).mockReturnValue(savePromise)

      const store = useWritingStudioStore()
      store.session = sessionFixture
      store.document = {
        kind: 'draft',
        writingRunId: 100,
        draftVersionId: 5,
        title: '第十八章',
        content: '正文',
        baseRevisionSequence: 0,
      }

      const pending = store.saveWorkingCopy(1)
      expect(store.saveState).toBe('saving')

      resolveSave!(workingCopyFixture)
      await pending
      expect(store.saveState).toBe('saved')
    })
  })
})
