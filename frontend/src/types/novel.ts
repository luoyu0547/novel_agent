export type ChapterStatus = 'draft' | 'reviewed' | 'locked'

export interface NovelCreate {
  title: string
  description?: string | null
  genre?: string | null
  style_guide?: string | null
}

export interface NovelUpdate {
  title?: string | null
  description?: string | null
  genre?: string | null
  style_guide?: string | null
}

export interface NovelListItem {
  id: number
  title: string
  description?: string | null
  genre?: string | null
  style_guide?: string | null
  created_at: string
  updated_at: string
}

export interface ChapterCreate {
  title: string
  content?: string
  summary?: string
  status?: ChapterStatus
}

export interface ChapterUpdate {
  title?: string | null
  content?: string | null
  summary?: string | null
  status?: ChapterStatus | null
}

export interface ChapterOut {
  id: number
  novel_id: number
  title: string
  content: string
  summary: string
  status: ChapterStatus
  created_at: string
  updated_at: string
}

export interface NovelOut extends NovelListItem {
  chapters?: ChapterOut[]
}
