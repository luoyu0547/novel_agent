import { describe, expect, it } from 'vitest'
import { joinBehaviorRules, splitBehaviorRules } from '@/utils/behaviorRules'

describe('behaviorRules utilities', () => {
  it('splits non-empty trimmed lines into rules', () => {
    expect(splitBehaviorRules('不会主动背叛朋友\n\n不会公开示弱\n  ')).toEqual([
      '不会主动背叛朋友',
      '不会公开示弱',
    ])
  })

  it('joins rules with newlines for textarea editing', () => {
    expect(joinBehaviorRules(['不会主动背叛朋友', '不会公开示弱'])).toBe('不会主动背叛朋友\n不会公开示弱')
  })
})
