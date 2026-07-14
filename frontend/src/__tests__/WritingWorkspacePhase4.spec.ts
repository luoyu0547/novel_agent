import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useRevisionsStore } from '@/stores/revisions'
import * as revisionApi from '@/api/revisions'
import type {
  DraftVersion,
  DraftRevision,
  ReviewIssue,
  RepairOption,
  RevisionMutationResponse,
} from '@/types/revision'

// ── Fixtures ──────────────────────────────────────────────────────────

const versionV1: DraftVersion = {
  id: 10,
  novel_id: 1,
  chapter_id: null,
  writing_run_id: 100,
  based_on_version_id: null,
  version: 1,
  title: 'Draft v1',
  content: 'Original content',
  word_count: 100,
  change_reason: 'initial',
  status: 'draft',
  revision_sequence: 0,
  acceptance_override_reason: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const versionV2: DraftVersion = {
  ...versionV1,
  id: 11,
  based_on_version_id: 10,
  version: 2,
  title: 'Draft v2',
  content: 'Revised content',
  word_count: 120,
  change_reason: 'applied revision',
  status: 'draft',
  revision_sequence: 1,
}

const revisionCandidate: DraftRevision = {
  id: 20,
  novel_id: 1,
  writing_run_id: 100,
  draft_version_id: 10,
  parent_revision_id: null,
  decision_id: null,
  sequence: 1,
  source_type: 'review_issue',
  source_id: 30,
  base_revision_sequence: 0,
  base_content_hash: 'abc',
  base_content: 'Original content',
  candidate_content: 'Fixed content',
  patches_json: [],
  scope_json: {},
  diff_json: {},
  reason: 'fix continuity',
  expanded_scope: false,
  expanded_scope_reason: null,
  status: 'candidate',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const revisionApplied: DraftRevision = {
  ...revisionCandidate,
  status: 'applied',
}

const issueBlocking: ReviewIssue = {
  id: 30,
  novel_id: 1,
  chapter_id: null,
  writing_run_id: 100,
  issue_type: 'continuity',
  severity: 'blocking',
  resolution_mode: 'needs_intent',
  location: 'paragraph 2',
  description: 'Character name mismatch',
  related_memory: null,
  suggestion: 'Fix the name',
  repair_options_json: null,
  resolved_by_revision_id: null,
  ignored_reason: null,
  acceptance_blocking: true,
  status: 'open',
  created_at: '2026-01-01T00:00:00Z',
}

const repairOptions: RepairOption[] = [
  {
    label: 'Fix name',
    summary: 'Replace wrong name with correct one',
    action: 'replace',
    expected_effect: 'Name consistency restored',
    estimated_scope: { paragraphs: 1 },
    recommended: true,
    recommendation_reason: 'Minimal change',
  },
]

// ── Mocks ─────────────────────────────────────────────────────────────

vi.mock('@/api/revisions')

// ── Tests ─────────────────────────────────────────────────────────────

describe('RevisionsStore contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loadWorkspace loads versions, selects current draft, then loads revisions and issues', async () => {
    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([])

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)

    expect(revisionApi.listDraftVersions).toHaveBeenCalledWith(1, 100)
    expect(revisionApi.listDraftRevisions).toHaveBeenCalledWith(1, versionV1.id)
    expect(revisionApi.listReviewIssues).toHaveBeenCalledWith(1, 100)
    expect(store.currentVersion).toEqual(versionV1)
    expect(store.versions).toEqual([versionV1])
  })

  it('generating options updates only the selected issue', async () => {
    const issueWithOptions: ReviewIssue = {
      ...issueBlocking,
      repair_options_json: repairOptions,
    }

    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([issueBlocking])
    vi.mocked(revisionApi.generateRepairOptions).mockResolvedValue(repairOptions)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)
    store.selectedIssueId = issueBlocking.id

    await store.generateOptions(1, issueBlocking.id)

    expect(revisionApi.generateRepairOptions).toHaveBeenCalledWith(1, issueBlocking.id)
    // The issue in reviewIssues should now have repair_options_json populated
    const updated = store.reviewIssues.find(i => i.id === issueBlocking.id)
    expect(updated?.repair_options_json).toEqual(repairOptions)
  })

  it('generating a candidate does not change currentVersion.content', async () => {
    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([issueBlocking])
    vi.mocked(revisionApi.createRevisionCandidate).mockResolvedValue(revisionCandidate)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)
    store.selectedIssueId = issueBlocking.id
    store.selectedOptionIndex = 0

    const contentBefore = store.currentVersion!.content
    await store.createCandidate(1, issueBlocking.id)

    expect(store.currentVersion!.content).toBe(contentBefore)
    expect(store.candidate).toEqual(revisionCandidate)
  })

  it('apply replaces the current version from server and refreshes issues/revisions', async () => {
    const mutationResponse: RevisionMutationResponse = {
      version: versionV2,
      revision: revisionApplied,
    }

    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([issueBlocking])
    vi.mocked(revisionApi.applyRevision).mockResolvedValue(mutationResponse)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)
    store.candidate = revisionCandidate

    await store.applyRevision(1, revisionCandidate.id, false)

    expect(revisionApi.applyRevision).toHaveBeenCalledWith(1, revisionCandidate.id, false)
    expect(store.currentVersion).toEqual(versionV2)
    expect(store.candidate).toBeNull()
    // Should refresh issues and revisions after apply
    expect(revisionApi.listReviewIssues).toHaveBeenCalledTimes(2) // loadWorkspace + refresh
    expect(revisionApi.listDraftRevisions).toHaveBeenCalledTimes(2) // loadWorkspace + refresh
  })

  it('reject leaves content unchanged and refreshes revision status', async () => {
    const rejectedRevision: DraftRevision = {
      ...revisionCandidate,
      status: 'rejected',
    }

    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([issueBlocking])
    vi.mocked(revisionApi.rejectRevision).mockResolvedValue(rejectedRevision)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)
    store.candidate = revisionCandidate

    const contentBefore = store.currentVersion!.content
    await store.rejectRevision(1, revisionCandidate.id)

    expect(store.currentVersion!.content).toBe(contentBefore)
    expect(store.candidate).toBeNull()
    expect(revisionApi.rejectRevision).toHaveBeenCalledWith(1, revisionCandidate.id)
  })

  it('createVersion is the only action that makes currentVersion.version increase', async () => {
    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([])
    vi.mocked(revisionApi.createDraftVersion).mockResolvedValue(versionV2)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)

    expect(store.currentVersion!.version).toBe(1)

    await store.createVersion(1, 100, { based_on_version_id: versionV1.id, change_reason: 'new version' })

    expect(store.currentVersion!.version).toBe(2)
    expect(revisionApi.createDraftVersion).toHaveBeenCalledWith(1, 100, {
      based_on_version_id: versionV1.id,
      change_reason: 'new version',
    })
  })

  it('manual save keeps the same version number', async () => {
    const manualRevision: DraftRevision = {
      ...revisionCandidate,
      source_type: 'manual_edit',
      status: 'applied',
    }
    const mutationResponse: RevisionMutationResponse = {
      version: { ...versionV1, content: 'Manually edited', word_count: 110 },
      revision: manualRevision,
    }

    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([])
    vi.mocked(revisionApi.saveManualRevision).mockResolvedValue(mutationResponse)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)

    const versionBefore = store.currentVersion!.version
    await store.saveManualRevision(1, 100, {
      content: 'Manually edited',
      change_reason: 'author edit',
      base_revision_sequence: 0,
    })

    expect(store.currentVersion!.version).toBe(versionBefore)
    expect(store.currentVersion!.content).toBe('Manually edited')
  })

  it('restore keeps the same version number', async () => {
    const restoredRevision: DraftRevision = {
      ...revisionCandidate,
      source_type: 'restore',
      status: 'applied',
    }
    const mutationResponse: RevisionMutationResponse = {
      version: { ...versionV1, content: 'Restored content' },
      revision: restoredRevision,
    }

    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([])
    vi.mocked(revisionApi.restoreVersion).mockResolvedValue(mutationResponse)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)

    const versionBefore = store.currentVersion!.version
    await store.restoreVersion(1, versionV1.id, {
      base_revision_sequence: 0,
      change_reason: 'restore',
    })

    expect(store.currentVersion!.version).toBe(versionBefore)
    expect(store.currentVersion!.content).toBe('Restored content')
  })

  it('failed requests preserve candidate, option selection, custom intent, and editor content', async () => {
    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([issueBlocking])
    vi.mocked(revisionApi.applyRevision).mockRejectedValue(new Error('Network error'))

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)

    // Set up local state
    store.candidate = revisionCandidate
    store.selectedOptionIndex = 0
    store.customIntent = 'fix the name'
    const contentBefore = store.currentVersion!.content

    // Attempt apply that fails
    await expect(store.applyRevision(1, revisionCandidate.id, false)).rejects.toThrow('Network error')

    // All local state should be preserved
    expect(store.candidate).toEqual(revisionCandidate)
    expect(store.selectedOptionIndex).toBe(0)
    expect(store.customIntent).toBe('fix the name')
    expect(store.currentVersion!.content).toBe(contentBefore)
    expect(store.loading).toBe(false)
  })

  it('ignoreIssue updates the issue status from server', async () => {
    const ignoredIssue: ReviewIssue = {
      ...issueBlocking,
      status: 'ignored',
      ignored_reason: 'Not relevant',
    }

    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([issueBlocking])
    vi.mocked(revisionApi.ignoreIssue).mockResolvedValue(ignoredIssue)

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)
    store.selectedIssueId = issueBlocking.id

    await store.ignoreIssue(1, issueBlocking.id, { reason: 'Not relevant' })

    expect(revisionApi.ignoreIssue).toHaveBeenCalledWith(1, issueBlocking.id, { reason: 'Not relevant' })
    const updated = store.reviewIssues.find(i => i.id === issueBlocking.id)
    expect(updated?.status).toBe('ignored')
  })

  it('clearWorkspace resets all state', async () => {
    vi.mocked(revisionApi.listDraftVersions).mockResolvedValue([versionV1])
    vi.mocked(revisionApi.listDraftRevisions).mockResolvedValue([])
    vi.mocked(revisionApi.listReviewIssues).mockResolvedValue([issueBlocking])

    const store = useRevisionsStore()
    await store.loadWorkspace(1, 100)
    store.selectedIssueId = 30
    store.selectedOptionIndex = 0
    store.customIntent = 'test'
    store.candidate = revisionCandidate

    store.clearWorkspace()

    expect(store.versions).toEqual([])
    expect(store.currentVersion).toBeNull()
    expect(store.revisions).toEqual([])
    expect(store.reviewIssues).toEqual([])
    expect(store.selectedIssueId).toBeNull()
    expect(store.selectedOptionIndex).toBeNull()
    expect(store.customIntent).toBe('')
    expect(store.candidate).toBeNull()
  })
})
