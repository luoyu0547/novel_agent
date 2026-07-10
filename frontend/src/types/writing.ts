export interface NovelBlueprint {
  id: number
  novel_id: number
  version: number
  status: 'draft' | 'active' | 'archived'
  content_json: {
    core_promise: string
    theme: string
    main_conflict: string
    character_arcs: string
    world_rules: string
    narrative_perspective: string
    style_constraints: string
    ending_direction: string
  }
  created_at: string
  updated_at: string
}

export interface ChapterPlan {
  id: number
  novel_id: number
  chapter_id: number | null
  position: number
  status: 'draft' | 'ready' | 'used'
  content_json: {
    chapter_title: string
    plot_task: string
    character_task: string
    information_task: string
    emotional_effect: string
    pacing: string
    foreshadowing_task: string
  }
  created_at: string
  updated_at: string
}

export interface ChapterBrief {
  id: number
  novel_id: number
  chapter_plan_id: number
  chapter_id: number | null
  status: 'draft' | 'ready' | 'used'
  brief_json: {
    writing_goal: string
    scenes: { name: string; purpose: string; conflict: string; expected_words: number }[]
    participating_characters: string
    conflict_design: string
    information_control: string
    foreshadowing_handling: string
    writing_constraints: string
    acceptance_criteria: string
  }
  length_contract_json: {
    target_words: number
    min_words: number
    max_words: number
    scene_word_allocation: { scene: string; words: number }[]
    density_requirements: string
    expansion_strategy: string
    compression_strategy: string
  }
  created_at: string
  updated_at: string
}

export interface ContextPackage {
  id: number
  novel_id: number
  chapter_brief_id: number
  package_json: Record<string, unknown>
  created_at: string
}

export interface WritingRun {
  id: number
  novel_id: number
  chapter_brief_id: number
  context_package_id: number
  target_chapter_id: number | null
  status: 'running' | 'completed' | 'decision_required' | 'failed' | 'accepted' | 'discarded'
  draft_content: string
  word_count: number
  gate_result_json: {
    passed: boolean
    reasons: string[]
    min_words: number
    target_words: number
    max_words: number
    outline_like: boolean
  }
  gated: boolean
  has_pending_repairs: boolean
  error_message: string | null
  decision_id: number | null
  context_snapshot_json: Record<string, unknown>
  planning_blocked: boolean
  accepted_at: string | null
  created_at: string
  updated_at: string
}

export interface RepairLog {
  id: number
  novel_id: number
  writing_run_id: number
  issue_type: string
  description: string
  location: string
  old_text: string
  new_text: string
  created_at: string
}

export interface PendingRepairOption {
  label: string
  summary: string
}

export interface PendingRepair {
  id: number
  novel_id: number
  chapter_id: number | null
  writing_run_id: number
  issue_type: string
  description: string
  location: string
  context: string
  options: PendingRepairOption[] | null
  intent_type: 'choice' | 'freeform'
  status: 'pending' | 'applied' | 'dismissed'
  created_at: string
}

export interface RepairsResponse {
  repair_logs: RepairLog[]
  pending_repairs: PendingRepair[]
}
