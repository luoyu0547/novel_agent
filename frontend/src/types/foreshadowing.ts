export interface Foreshadowing {
  id: number
  novel_id: number
  name: string
  planted_chapter_id: number
  description: string
  hidden_truth: string
  status: 'planted' | 'developing' | 'resolved'
  expected_reveal_chapter_id: number | null
  related_characters: string[]
  risk_warning: string
  created_at: string
  updated_at: string
}
