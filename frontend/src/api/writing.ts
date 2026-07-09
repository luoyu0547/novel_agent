import client from './client'
import type { NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun, RepairsResponse } from '@/types/writing'
import type { ChapterOut } from '@/types/novel'

export function generateBlueprint(novelId: number, authorInput: string): Promise<NovelBlueprint> {
  return client.post(`/novels/${novelId}/blueprints/generate`, { author_input: authorInput })
}

export function listBlueprints(novelId: number): Promise<NovelBlueprint[]> {
  return client.get(`/novels/${novelId}/blueprints`)
}

export function updateBlueprint(novelId: number, blueprintId: number, data: Partial<NovelBlueprint>): Promise<NovelBlueprint> {
  return client.put(`/novels/${novelId}/blueprints/${blueprintId}`, data)
}

export function activateBlueprint(novelId: number, blueprintId: number): Promise<NovelBlueprint> {
  return client.put(`/novels/${novelId}/blueprints/${blueprintId}/activate`)
}

export function generateChapterPlan(novelId: number): Promise<ChapterPlan> {
  return client.post(`/novels/${novelId}/chapter-plans/next/generate`)
}

export function updateChapterPlan(novelId: number, planId: number, data: Partial<ChapterPlan>): Promise<ChapterPlan> {
  return client.put(`/novels/${novelId}/chapter-plans/${planId}`, data)
}

export function generateChapterBrief(novelId: number, chapterPlanId: number): Promise<ChapterBrief> {
  return client.post(`/novels/${novelId}/chapter-briefs/generate`, { chapter_plan_id: chapterPlanId })
}

export function updateChapterBrief(novelId: number, briefId: number, data: Partial<ChapterBrief>): Promise<ChapterBrief> {
  return client.put(`/novels/${novelId}/chapter-briefs/${briefId}`, data)
}

export function generateContextPackage(novelId: number, chapterBriefId: number): Promise<ContextPackage> {
  return client.post(`/novels/${novelId}/context-packages/generate`, { chapter_brief_id: chapterBriefId })
}

export function createWritingRun(novelId: number, chapterBriefId: number): Promise<WritingRun> {
  return client.post(`/novels/${novelId}/writing-runs`, { chapter_brief_id: chapterBriefId })
}

export function listWritingRuns(novelId: number): Promise<WritingRun[]> {
  return client.get(`/novels/${novelId}/writing-runs`)
}

export function getWritingRun(novelId: number, runId: number): Promise<WritingRun> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}`)
}

export function acceptWritingRun(novelId: number, runId: number): Promise<ChapterOut> {
  return client.put(`/novels/${novelId}/writing-runs/${runId}/accept`)
}

export function discardWritingRun(novelId: number, runId: number): Promise<void> {
  return client.put(`/novels/${novelId}/writing-runs/${runId}/discard`)
}

export function getRepairs(novelId: number, runId: number): Promise<RepairsResponse> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}/repairs`)
}

export function getPendingRepairs(novelId: number, runId: number): Promise<{ id: number; issue_type: string }[]> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}/repairs/pending`)
}

export function resolveRepair(
  novelId: number,
  repairId: number,
  payload: { action: 'apply' | 'dismiss'; choice_index?: number; intent_text?: string },
): Promise<void> {
  return client.put(`/novels/${novelId}/writing/repairs/${repairId}/resolve`, payload)
}
