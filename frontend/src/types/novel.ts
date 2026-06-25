export interface NovelCreate {
  title: string
  description?: string | null
}

export interface NovelUpdate {
  title?: string | null
  description?: string | null
}

export interface NovelListItem {
  id: number
  title: string
  description?: string | null
  created_at: string
  updated_at: string
}

export interface ChapterCreate {
  title: string
  content?: string
}

export interface ChapterUpdate {
  title?: string | null
  content?: string | null
}

export interface ChapterOut {
  id: number
  novel_id: number
  title: string
  content: string
  created_at: string
  updated_at: string
}

export interface NovelOut extends NovelListItem {
  chapters?: ChapterOut[]
}
