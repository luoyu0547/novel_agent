/** Phase 6 Author Studio — TypeScript contracts. */

export type StudioMessageRole = 'author' | 'assistant' | 'system'
export type StudioActionStatus = 'running' | 'completed' | 'needs_confirmation' | 'failed'
export type StudioConfirmationAction = 'accept' | 'discard' | 'apply_revision' | 'force_accept' | 'restore_version'

export interface WritingSession {
  id: number
  novel_id: number
  target_chapter_id: number | null
  active_writing_run_id: number | null
  title: string
  status: string
}

export interface WritingMessage {
  id: number
  session_id: number
  role: StudioMessageRole
  message_type: string
  content_json: Record<string, unknown>
  action_status: StudioActionStatus
  writing_run_id: number | null
  context_package_id: number | null
  draft_version_id: number | null
}

export interface DraftWorkingCopy {
  writing_run_id: number
  draft_version_id: number
  title: string
  content: string
  base_revision_sequence: number
}

export interface StudioDocument {
  kind: 'chapter' | 'draft'
  chapterId?: number
  writingRunId?: number
  draftVersionId?: number
  title: string
  content: string
  baseRevisionSequence: number
}

export interface StudioWorkspace {
  session: WritingSession
  messages: WritingMessage[]
  working_copy: DraftWorkingCopy | null
}

export interface StudioMessageResult {
  assistant_message: WritingMessage
  workspace: StudioWorkspace
}

export interface StudioSource {
  source_id: string
  source_type: string
  title: string
  locator: Record<string, unknown>
  preview: string
  inclusion_reason: string
}
