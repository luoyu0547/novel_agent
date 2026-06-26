export type WorldSettingCategory = 'geography' | 'faction' | 'rule' | 'history' | 'culture' | 'other'

export interface CharacterProfile {
  id: number
  novel_id: number
  name: string
  story_role: string
  identity: string
  personality: string
  motivation: string
  speech_style: string
  behavior_rules: string[]
  current_state: string
  created_at: string
  updated_at: string
}

export interface CharacterCreate {
  name: string
  story_role?: string
  identity?: string
  personality?: string
  motivation?: string
  speech_style?: string
  behavior_rules?: string[]
  current_state?: string
}

export interface CharacterUpdate {
  name?: string | null
  story_role?: string | null
  identity?: string | null
  personality?: string | null
  motivation?: string | null
  speech_style?: string | null
  behavior_rules?: string[] | null
  current_state?: string | null
}

export interface WorldSetting {
  id: number
  novel_id: number
  title: string
  category: WorldSettingCategory
  content: string
  created_at: string
  updated_at: string
}

export interface WorldSettingCreate {
  title: string
  category: WorldSettingCategory
  content?: string
}

export interface WorldSettingUpdate {
  title?: string | null
  category?: WorldSettingCategory | null
  content?: string | null
}
