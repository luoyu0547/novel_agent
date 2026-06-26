import type { ChapterStatus, WorldSettingCategory } from '@/types'

export const CHAPTER_STATUS_OPTIONS: { value: ChapterStatus; label: string }[] = [
  { value: 'draft', label: '草稿' },
  { value: 'reviewed', label: '已确认' },
  { value: 'locked', label: '锁定' },
]

export const WORLD_SETTING_CATEGORY_OPTIONS: { value: WorldSettingCategory | 'all'; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'geography', label: '地理' },
  { value: 'faction', label: '势力' },
  { value: 'rule', label: '规则' },
  { value: 'history', label: '历史' },
  { value: 'culture', label: '文化' },
  { value: 'other', label: '其他' },
]

export const WORLD_SETTING_CATEGORIES: { value: WorldSettingCategory; label: string }[] = [
  { value: 'geography', label: '地理' },
  { value: 'faction', label: '势力' },
  { value: 'rule', label: '规则' },
  { value: 'history', label: '历史' },
  { value: 'culture', label: '文化' },
  { value: 'other', label: '其他' },
]
