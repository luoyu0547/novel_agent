import client from './client'
import type { AuthorFoundation, AuthorFoundationUpdate, AuthorFoundationRevision, PlotUnit, PlotUnitCreate, PlotPlanRevision, PlanningDecision, ChooseDecisionRequest, DecisionResolution, DraftRevision } from '@/types/plotPlanning'

export function getFoundation(novelId: number): Promise<AuthorFoundation> {
  return client.get(`/novels/${novelId}/author-foundation`)
}

export function updateFoundation(novelId: number, data: AuthorFoundationUpdate): Promise<AuthorFoundation> {
  return client.put(`/novels/${novelId}/author-foundation`, data)
}

export function listFoundationRevisions(novelId: number): Promise<AuthorFoundationRevision[]> {
  return client.get(`/novels/${novelId}/author-foundation/revisions`)
}

export function createPlotUnit(novelId: number, data: PlotUnitCreate): Promise<PlotUnit> {
  return client.post(`/novels/${novelId}/plot-units`, data)
}

export function listPlotUnits(novelId: number): Promise<PlotUnit[]> {
  return client.get(`/novels/${novelId}/plot-units`)
}

export function getPlotUnit(novelId: number, plotUnitId: number): Promise<PlotUnit> {
  return client.get(`/novels/${novelId}/plot-units/${plotUnitId}`)
}

export function generatePlotPlan(novelId: number, plotUnitId: number, authorInput: string): Promise<PlotPlanRevision> {
  return client.post(`/novels/${novelId}/plot-units/${plotUnitId}/plans/generate`, { author_input: authorInput })
}

export function listPlotPlans(novelId: number, plotUnitId: number): Promise<PlotPlanRevision[]> {
  return client.get(`/novels/${novelId}/plot-units/${plotUnitId}/plans`)
}

export function confirmPlotPlan(novelId: number, plotUnitId: number, revisionId: number): Promise<PlotPlanRevision> {
  return client.put(`/novels/${novelId}/plot-units/${plotUnitId}/plans/${revisionId}/confirm`)
}

export function listDecisions(novelId: number, status?: string): Promise<PlanningDecision[]> {
  const params = status ? { status } : undefined
  return client.get(`/novels/${novelId}/planning-decisions`, { params })
}

export function getDecision(novelId: number, decisionId: number): Promise<PlanningDecision> {
  return client.get(`/novels/${novelId}/planning-decisions/${decisionId}`)
}

export function chooseDecision(novelId: number, decisionId: number, data: ChooseDecisionRequest): Promise<DecisionResolution> {
  return client.put(`/novels/${novelId}/planning-decisions/${decisionId}/choose`, data)
}

export function applyDraftRevision(novelId: number, revisionId: number): Promise<DraftRevision> {
  return client.put(`/novels/${novelId}/draft-revisions/${revisionId}/apply`)
}
