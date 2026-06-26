export interface PlotFact {
  id: number
  novel_id: number
  chapter_id: number
  fact_type: 'event' | 'relationship' | 'location' | 'item' | 'knowledge'
  content: string
  related_characters: string[]
  importance: 'major' | 'minor'
  created_at: string
}
