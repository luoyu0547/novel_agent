import client from './client'
import type { NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun, RepairsResponse } from '@/types/writing'
import type { AcceptWritingRunResponse, Chapter } from '@/types/novel'
import type { ReviewWritingRunResponse } from '@/types/plotPlanning'

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

export function generateChapterBrief(
  novelId: number,
  chapterPlanId: number,
  plotPlanRevisionId?: number,
  authorInput?: string,
): Promise<ChapterBrief> {
  const body: Record<string, unknown> = { chapter_plan_id: chapterPlanId }
  if (plotPlanRevisionId !== undefined) body.plot_plan_revision_id = plotPlanRevisionId
  if (authorInput !== undefined) body.author_input = authorInput
  return client.post(`/novels/${novelId}/chapter-briefs/generate`, body)
}

export function updateChapterBrief(novelId: number, briefId: number, data: Partial<ChapterBrief>): Promise<ChapterBrief> {
  return client.put(`/novels/${novelId}/chapter-briefs/${briefId}`, data)
}

export function generateContextPackage(
  novelId: number,
  chapterBriefId: number,
  plotPlanRevisionId?: number,
  authorInput?: string,
): Promise<ContextPackage> {
  const body: Record<string, unknown> = { chapter_brief_id: chapterBriefId }
  if (plotPlanRevisionId !== undefined) body.plot_plan_revision_id = plotPlanRevisionId
  if (authorInput !== undefined) body.author_input = authorInput
  return client.post(`/novels/${novelId}/context-packages/generate`, body)
}

export function createWritingRun(
  novelId: number,
  chapterBriefId: number,
  plotPlanRevisionId?: number,
  authorInput?: string,
): Promise<WritingRun> {
  const body: Record<string, unknown> = { chapter_brief_id: chapterBriefId }
  if (plotPlanRevisionId !== undefined) body.plot_plan_revision_id = plotPlanRevisionId
  if (authorInput !== undefined) body.author_input = authorInput
  return client.post(`/novels/${novelId}/writing-runs`, body)
}

export function listWritingRuns(novelId: number): Promise<WritingRun[]> {
  return client.get(`/novels/${novelId}/writing-runs`)
}

export function getWritingRun(novelId: number, runId: number): Promise<WritingRun> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}`)
}

export function acceptWritingRun(
  novelId: number,
  runId: number,
  options?: { force_accept?: boolean; force_reason?: string },
): Promise<AcceptWritingRunResponse> {
  const body = options ?? {}
  return client.put(`/novels/${novelId}/writing-runs/${runId}/accept`, body)
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

export function reviewWritingRun(novelId: number, runId: number): Promise<ReviewWritingRunResponse> {
  return client.post(`/novels/${novelId}/writing-runs/${runId}/review`)
}

export function publishChapter(novelId: number, chapterId: number): Promise<Chapter> {
  return client.put(`/novels/${novelId}/chapters/${chapterId}/publish`, {})
}
