import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/revisions'
import type {
  DraftVersion,
  DraftRevision,
  ReviewIssue,
  RepairOption,
  CreateDraftVersionRequest,
  RestoreVersionRequest,
  ManualRevisionRequest,
  CreateRevisionRequest,
  IgnoreIssueRequest,
} from '@/types/revision'

export const useRevisionsStore = defineStore('revisions', () => {
  const versions = ref<DraftVersion[]>([])
  const currentVersion = ref<DraftVersion | null>(null)
  const revisions = ref<DraftRevision[]>([])
  const reviewIssues = ref<ReviewIssue[]>([])
  const selectedIssueId = ref<number | null>(null)
  const selectedOptionIndex = ref<number | null>(null)
  const customIntent = ref('')
  const candidate = ref<DraftRevision | null>(null)
  const loading = ref(false)

  async function loadWorkspace(novelId: number, runId: number) {
    loading.value = true
    try {
      versions.value = await api.listDraftVersions(novelId, runId)
      // Select the current draft version (latest draft-status version)
      currentVersion.value = versions.value.find(v => v.status === 'draft') || versions.value[0] || null

      if (currentVersion.value) {
        revisions.value = await api.listDraftRevisions(novelId, currentVersion.value.id)
      } else {
        revisions.value = []
      }

      reviewIssues.value = await api.listReviewIssues(novelId, runId)
    } finally {
      loading.value = false
    }
  }

  async function generateOptions(novelId: number, issueId: number) {
    loading.value = true
    try {
      const options: RepairOption[] = await api.generateRepairOptions(novelId, issueId)
      // Update only the selected issue with the new options
      reviewIssues.value = reviewIssues.value.map(issue =>
        issue.id === issueId ? { ...issue, repair_options_json: options } : issue,
      )
    } finally {
      loading.value = false
    }
  }

  async function createCandidate(novelId: number, issueId: number) {
    loading.value = true
    try {
      const payload: CreateRevisionRequest = {}
      if (selectedOptionIndex.value !== null) payload.option_index = selectedOptionIndex.value
      if (customIntent.value) payload.custom_intent = customIntent.value

      const revision = await api.createRevisionCandidate(novelId, issueId, payload)
      // Set candidate but do NOT mutate currentVersion.content
      candidate.value = revision
    } finally {
      loading.value = false
    }
  }

  async function applyRevision(novelId: number, revisionId: number, confirmExpandedScope: boolean) {
    loading.value = true
    try {
      const response = await api.applyRevision(novelId, revisionId, confirmExpandedScope)
      // Replace currentVersion with server-returned version
      currentVersion.value = response.version
      candidate.value = null
      // Refresh issues and revisions from server
      await refreshAfterMutation(novelId)
    } catch (error) {
      loading.value = false
      throw error
    }
    loading.value = false
  }

  async function rejectRevision(novelId: number, revisionId: number) {
    loading.value = true
    try {
      await api.rejectRevision(novelId, revisionId)
      candidate.value = null
      // Refresh revisions list from server
      if (currentVersion.value) {
        revisions.value = await api.listDraftRevisions(novelId, currentVersion.value.id)
      }
    } catch (error) {
      loading.value = false
      throw error
    }
    loading.value = false
  }

  async function createVersion(novelId: number, runId: number, payload: CreateDraftVersionRequest) {
    loading.value = true
    try {
      const version = await api.createDraftVersion(novelId, runId, payload)
      versions.value.push(version)
      currentVersion.value = version
      // Load revisions for the new version
      revisions.value = await api.listDraftRevisions(novelId, version.id)
    } finally {
      loading.value = false
    }
  }

  async function saveManualRevision(novelId: number, runId: number, payload: ManualRevisionRequest) {
    loading.value = true
    try {
      const response = await api.saveManualRevision(novelId, runId, payload)
      // Use server-returned version (same version number, updated content)
      currentVersion.value = response.version
      await refreshAfterMutation(novelId)
    } catch (error) {
      loading.value = false
      throw error
    }
    loading.value = false
  }

  async function restoreVersion(novelId: number, versionId: number, payload: RestoreVersionRequest) {
    loading.value = true
    try {
      const response = await api.restoreVersion(novelId, versionId, payload)
      // Use server-returned version (same version number, restored content)
      currentVersion.value = response.version
      await refreshAfterMutation(novelId)
    } catch (error) {
      loading.value = false
      throw error
    }
    loading.value = false
  }

  async function ignoreIssue(novelId: number, issueId: number, payload: IgnoreIssueRequest) {
    loading.value = true
    try {
      const updated = await api.ignoreIssue(novelId, issueId, payload)
      // Replace the issue with server-returned object
      reviewIssues.value = reviewIssues.value.map(issue =>
        issue.id === issueId ? updated : issue,
      )
    } finally {
      loading.value = false
    }
  }

  function clearWorkspace() {
    versions.value = []
    currentVersion.value = null
    revisions.value = []
    reviewIssues.value = []
    selectedIssueId.value = null
    selectedOptionIndex.value = null
    customIntent.value = ''
    candidate.value = null
  }

  /** Internal helper: refresh issues + revisions after a mutation */
  async function refreshAfterMutation(novelId: number) {
    const runId = currentVersion.value?.writing_run_id
    if (runId) {
      reviewIssues.value = await api.listReviewIssues(novelId, runId)
    }
    if (currentVersion.value) {
      revisions.value = await api.listDraftRevisions(novelId, currentVersion.value.id)
    }
  }

  return {
    versions,
    currentVersion,
    revisions,
    reviewIssues,
    selectedIssueId,
    selectedOptionIndex,
    customIntent,
    candidate,
    loading,
    loadWorkspace,
    generateOptions,
    createCandidate,
    applyRevision,
    rejectRevision,
    createVersion,
    saveManualRevision,
    restoreVersion,
    ignoreIssue,
    clearWorkspace,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useRevisionsStore, import.meta.hot))
}
