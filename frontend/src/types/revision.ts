export type DraftVersionStatus = 'draft' | 'accepted' | 'rejected' | 'archived'
export type DraftRevisionStatus = 'candidate' | 'applied' | 'rejected' | 'superseded'
export type DraftRevisionSource =
  | 'planning_decision'
  | 'review_issue'
  | 'author_request'
  | 'manual_edit'
  | 'restore'
export type ReviewIssueSeverity = 'blocking' | 'major' | 'minor'
export type ReviewIssueResolutionMode = 'auto_fixable' | 'needs_intent'

export interface RevisionPatch {
  start_offset: number
  end_offset: number
  original_text: string
  replacement_text: string
  reason: string
}

export interface DraftVersion {
  id: number
  novel_id: number
  chapter_id: number | null
  writing_run_id: number
  based_on_version_id: number | null
  version: number
  title: string
  content: string
  word_count: number
  change_reason: string
  status: DraftVersionStatus
  revision_sequence: number
  acceptance_override_reason: string | null
  created_at: string
  updated_at: string
}

export interface DraftRevision {
  id: number
  novel_id: number
  writing_run_id: number | null
  draft_version_id: number | null
  parent_revision_id: number | null
  decision_id: number | null
  sequence: number
  source_type: DraftRevisionSource
  source_id: number | null
  base_revision_sequence: number
  base_content_hash: string
  base_content: string
  candidate_content: string
  patches_json: RevisionPatch[]
  scope_json: Record<string, unknown>
  diff_json: Record<string, unknown>
  reason: string
  expanded_scope: boolean
  expanded_scope_reason: string | null
  status: DraftRevisionStatus
  created_at: string
  updated_at: string
}

export interface ReviewIssue {
  id: number
  novel_id: number
  chapter_id: number | null
  writing_run_id: number | null
  issue_type: string
  severity: ReviewIssueSeverity
  resolution_mode: ReviewIssueResolutionMode
  location: string
  description: string
  related_memory: string | null
  suggestion: string
  repair_options_json: RepairOption[] | null
  resolved_by_revision_id: number | null
  ignored_reason: string | null
  acceptance_blocking: boolean
  status: string
  created_at: string
}

export interface RepairOption {
  label: string
  summary: string
  action: string
  expected_effect: string
  estimated_scope: Record<string, unknown>
  recommended: boolean
  recommendation_reason: string
}

// Request types

export interface CreateDraftVersionRequest {
  based_on_version_id: number
  change_reason: string
}

export interface RestoreVersionRequest {
  base_revision_sequence: number
  change_reason: string
}

export interface ManualRevisionRequest {
  content: string
  change_reason: string
  base_revision_sequence: number
}

export interface CreateRevisionRequest {
  option_index?: number | null
  custom_intent?: string | null
}

export interface IgnoreIssueRequest {
  reason: string
}

export interface ApplyRevisionRequest {
  confirm_expanded_scope: boolean
}

// Response type for mutations that return version + revision
export interface RevisionMutationResponse {
  version: DraftVersion
  revision: DraftRevision
}
