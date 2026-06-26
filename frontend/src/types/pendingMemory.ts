export interface PendingMemory {
  id: number
  novel_id: number
  chapter_id: number
  memory_type: 'character_change' | 'plot_fact' | 'world_setting' | 'foreshadowing'
  content: Record<string, unknown>
  status: 'pending' | 'confirmed' | 'rejected'
  created_at: string
}

export interface ExtractRequest {
  mode: 'standard' | 'deep'
}

export interface ExtractResponse {
  chapter_summary: string | null
  pending_ids: number[]
  pending_count: number
}
