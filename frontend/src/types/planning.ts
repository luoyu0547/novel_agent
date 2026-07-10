export interface VolumeArc {
  id: number
  novel_id: number
  blueprint_id: number | null
  order_index: number
  title: string
  goal: string
  start_state: string
  end_state: string
  key_events: string[]
  pacing_notes: string
  foreshadowing_plan: Record<string, unknown>[]
  status: 'draft' | 'active' | 'archived'
  created_at: string
  updated_at: string
}

export interface PlanVersion {
  id: number
  novel_id: number
  plan_type: 'blueprint' | 'chapter_plan' | 'volume_arc'
  plan_id: number
  version: number
  change_reason: string
  impact_scope: string
  snapshot_json: Record<string, unknown>
  status: 'current' | 'archived'
  created_at: string
  updated_at: string
}

export type ReviewIssueType =
  | 'task_completion'
  | 'style'
  | 'character'
  | 'continuity'
  | 'world'
  | 'foreshadowing'
  | 'length'

export type ReviewIssueSeverity = 'auto_fixable' | 'needs_intent'

export interface ReviewIssue {
  id: number
  novel_id: number
  writing_run_id: number | null
  issue_type: ReviewIssueType
  severity: ReviewIssueSeverity
  location: string
  description: string
  related_memory: string | null
  suggestion: string
  acceptance_blocking: boolean
  status: 'open' | 'resolved' | 'dismissed'
  created_at: string
  updated_at: string
}
