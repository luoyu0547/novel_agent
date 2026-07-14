import client from './client'
import type {
  DraftVersion,
  DraftRevision,
  ReviewIssue,
  RepairOption,
  RevisionMutationResponse,
  CreateDraftVersionRequest,
  RestoreVersionRequest,
  ManualRevisionRequest,
  CreateRevisionRequest,
  IgnoreIssueRequest,
  ApplyRevisionRequest,
} from '@/types/revision'

export function listDraftVersions(novelId: number, runId: number): Promise<DraftVersion[]> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}/draft-versions`)
}

export function getDraftVersion(novelId: number, versionId: number): Promise<DraftVersion> {
  return client.get(`/novels/${novelId}/draft-versions/${versionId}`)
}

export function createDraftVersion(
  novelId: number,
  runId: number,
  payload: CreateDraftVersionRequest,
): Promise<DraftVersion> {
  return client.post(`/novels/${novelId}/writing-runs/${runId}/draft-versions`, payload)
}

export function restoreVersion(
  novelId: number,
  versionId: number,
  payload: RestoreVersionRequest,
): Promise<RevisionMutationResponse> {
  return client.post(`/novels/${novelId}/draft-versions/${versionId}/restore`, payload)
}

export function saveManualRevision(
  novelId: number,
  runId: number,
  payload: ManualRevisionRequest,
): Promise<RevisionMutationResponse> {
  return client.post(`/novels/${novelId}/writing-runs/${runId}/manual-revision`, payload)
}

export function listReviewIssues(novelId: number, runId: number): Promise<ReviewIssue[]> {
  return client.get(`/novels/${novelId}/writing-runs/${runId}/review-issues`)
}

export function generateRepairOptions(novelId: number, issueId: number): Promise<RepairOption[]> {
  return client.post(`/novels/${novelId}/review-issues/${issueId}/repair-options`)
}

export function createRevisionCandidate(
  novelId: number,
  issueId: number,
  payload: CreateRevisionRequest,
): Promise<DraftRevision> {
  return client.post(`/novels/${novelId}/review-issues/${issueId}/revisions`, payload)
}

export function applyRevision(
  novelId: number,
  revisionId: number,
  confirmExpandedScope: boolean,
): Promise<RevisionMutationResponse> {
  const payload: ApplyRevisionRequest = { confirm_expanded_scope: confirmExpandedScope }
  return client.put(`/novels/${novelId}/draft-revisions/${revisionId}/apply`, payload)
}

export function rejectRevision(novelId: number, revisionId: number): Promise<DraftRevision> {
  return client.put(`/novels/${novelId}/draft-revisions/${revisionId}/reject`)
}

export function ignoreIssue(
  novelId: number,
  issueId: number,
  payload: IgnoreIssueRequest,
): Promise<ReviewIssue> {
  return client.put(`/novels/${novelId}/review-issues/${issueId}/ignore`, payload)
}

export function listDraftRevisions(novelId: number, versionId: number): Promise<DraftRevision[]> {
  return client.get(`/novels/${novelId}/draft-versions/${versionId}/revisions`)
}
