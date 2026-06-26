import { describe, expect, it } from 'vitest'
import { CHAPTER_STATUS_OPTIONS, WORLD_SETTING_CATEGORY_OPTIONS, WORLD_SETTING_CATEGORIES } from '@/constants/options'

describe('options constants', () => {
  it('CHAPTER_STATUS_OPTIONS covers all values', () => {
    const values = CHAPTER_STATUS_OPTIONS.map((o) => o.value)
    expect(values).toEqual(['draft', 'reviewed', 'locked'])
    expect(CHAPTER_STATUS_OPTIONS[0]).toEqual({ value: 'draft', label: '草稿' })
    expect(CHAPTER_STATUS_OPTIONS[1]).toEqual({ value: 'reviewed', label: '已确认' })
    expect(CHAPTER_STATUS_OPTIONS[2]).toEqual({ value: 'locked', label: '锁定' })
  })

  it('WORLD_SETTING_CATEGORY_OPTIONS includes all filter', () => {
    const values = WORLD_SETTING_CATEGORY_OPTIONS.map((o) => o.value)
    expect(values).toEqual(['all', 'geography', 'faction', 'rule', 'history', 'culture', 'other'])
  })

  it('WORLD_SETTING_CATEGORIES covers all categories', () => {
    const values = WORLD_SETTING_CATEGORIES.map((o) => o.value)
    expect(values).toEqual(['geography', 'faction', 'rule', 'history', 'culture', 'other'])
    expect(WORLD_SETTING_CATEGORIES.find((o) => o.value === 'geography')?.label).toBe('地理')
    expect(WORLD_SETTING_CATEGORIES.find((o) => o.value === 'other')?.label).toBe('其他')
  })
})
