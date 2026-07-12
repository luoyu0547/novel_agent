export type PlotPlanStatus = 'draft' | 'active' | 'stale' | 'blocked' | 'superseded' | 'completed'
export type DecisionSource = 'during_generation' | 'during_review'
export type DecisionStatus = 'pending' | 'resolved' | 'superseded'
export type DraftRevisionStatus = 'candidate' | 'applied' | 'superseded'

export interface AuthorFoundation {
  id: number
  novel_id: number
  outline: string
  current_intent: string
  stage_goal: string
  constraints_json: Record<string, unknown>
  version: number
  created_at: string
  updated_at: string
}

export interface AuthorFoundationUpdate {
  outline?: string
  current_intent?: string
  stage_goal?: string
  constraints_json?: Record<string, unknown>
}

export interface AuthorFoundationRevision {
  id: number
  novel_id: number
  foundation_id: number
  version: number
  snapshot_json: Record<string, unknown>
  change_reason: string
  created_at: string
}

export interface PlotUnit {
  id: number
  novel_id: number
  title: string
  scope_type: string
  start_position: number
  end_position: number
  author_goal: string
  start_state: string
  end_state: string
  foundation_revision_id: number
  status: string
  created_at: string
  updated_at: string
}

export interface PlotUnitCreate {
  title: string
  scope_type: string
  start_position: number
  end_position: number
  author_goal: string
  start_state: string
  end_state: string
}

export interface PlotPlanRevision {
  id: number
  novel_id: number
  plot_unit_id: number
  foundation_revision_id: number
  based_on_published_chapter_id: number | null
  version: number
  plan_json: Record<string, unknown>
  change_reason: string
  status: PlotPlanStatus
  created_at: string
  updated_at: string
}

export interface PlanningDecision {
  id: number
  novel_id: number
  plot_unit_id: number | null
  plot_plan_revision_id: number | null
  chapter_brief_id: number | null
  writing_run_id: number | null
  source: DecisionSource
  status: DecisionStatus
  conflict_summary: string
  evidence_json: Record<string, unknown>
  options_json: DecisionOption[]
  recommended_index: number
  recommendation_reason: string
  impact_scope_json: Record<string, unknown>
  selected_option_index?: number
  custom_intent?: string
  created_at: string
  updated_at: string
}

export interface DecisionOption {
  label: string
  action: string
  consequence: string
}

export interface DraftRevision {
  id: number
  novel_id: number
  writing_run_id: number | null
  parent_revision_id: number | null
  decision_id: number | null
  base_content: string
  candidate_content: string
  scope_json: Record<string, unknown>
  diff_json: Record<string, unknown>
  reason: string
  status: DraftRevisionStatus
  created_at: string
  updated_at: string
}

export interface ChooseDecisionRequest {
  option_index?: number
  custom_intent?: string
}

export interface DecisionResolution {
  decision: PlanningDecision
  new_plan: PlotPlanRevision | null
  draft_revision: DraftRevision
}

export interface ReviewWritingRunResponse {
  decision: PlanningDecision | null
  review_issues: unknown[]
}
