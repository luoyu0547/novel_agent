import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/writing'
import type { NovelBlueprint, ChapterPlan, ChapterBrief, ContextPackage, WritingRun, RepairLog, PendingRepair } from '@/types/writing'

export const useWritingStore = defineStore('writing', () => {
  const blueprints = ref<NovelBlueprint[]>([])
  const activeBlueprint = ref<NovelBlueprint | null>(null)
  const latestPlan = ref<ChapterPlan | null>(null)
  const latestBrief = ref<ChapterBrief | null>(null)
  const latestContext = ref<ContextPackage | null>(null)
  const writingRuns = ref<WritingRun[]>([])
  const loading = ref(false)
  const repairLogs = ref<RepairLog[]>([])
  const pendingRepairs = ref<PendingRepair[]>([])

  async function fetchBlueprints(novelId: number) {
    blueprints.value = await api.listBlueprints(novelId)
    activeBlueprint.value = blueprints.value.find(b => b.status === 'active') || null
  }

  async function generateBlueprint(novelId: number, authorInput: string) {
    loading.value = true
    try {
      const bp = await api.generateBlueprint(novelId, authorInput)
      blueprints.value.unshift(bp)
      return bp
    } finally {
      loading.value = false
    }
  }

  async function activateBlueprint(novelId: number, blueprintId: number) {
    const bp = await api.activateBlueprint(novelId, blueprintId)
    activeBlueprint.value = bp
    blueprints.value = blueprints.value.map(b => ({
      ...b,
      status: b.id === blueprintId ? 'active' : 'archived',
    }))
    return bp
  }

  async function updateBlueprint(novelId: number, blueprintId: number, data: Partial<NovelBlueprint>) {
    const bp = await api.updateBlueprint(novelId, blueprintId, data)
    blueprints.value = blueprints.value.map(b => (b.id === blueprintId ? bp : b))
    if (activeBlueprint.value?.id === blueprintId) activeBlueprint.value = bp
    return bp
  }

  async function generateChapterPlan(novelId: number) {
    loading.value = true
    try {
      latestPlan.value = await api.generateChapterPlan(novelId)
      return latestPlan.value
    } finally {
      loading.value = false
    }
  }

  async function generateChapterBrief(novelId: number, planId: number) {
    loading.value = true
    try {
      latestBrief.value = await api.generateChapterBrief(novelId, planId)
      return latestBrief.value
    } finally {
      loading.value = false
    }
  }

  async function generateContextPackage(novelId: number, briefId: number) {
    loading.value = true
    try {
      latestContext.value = await api.generateContextPackage(novelId, briefId)
      return latestContext.value
    } finally {
      loading.value = false
    }
  }

  async function createWritingRun(novelId: number, briefId: number) {
    loading.value = true
    try {
      const run = await api.createWritingRun(novelId, briefId)
      writingRuns.value.unshift(run)
      return run
    } finally {
      loading.value = false
    }
  }

  async function acceptRun(novelId: number, runId: number) {
    const result = await api.acceptWritingRun(novelId, runId)
    writingRuns.value = writingRuns.value.map(r =>
      r.id === runId ? { ...r, status: 'accepted' as const } : r,
    )
    return result
  }

  async function discardRun(novelId: number, runId: number) {
    await api.discardWritingRun(novelId, runId)
    writingRuns.value = writingRuns.value.map(r =>
      r.id === runId ? { ...r, status: 'discarded' as const } : r,
    )
  }

  async function fetchWritingRuns(novelId: number) {
    writingRuns.value = await api.listWritingRuns(novelId)
  }

  async function fetchRepairs(novelId: number, runId: number) {
    const data = await api.getRepairs(novelId, runId)
    repairLogs.value = data.repair_logs
    pendingRepairs.value = data.pending_repairs
  }

  async function resolveRepair(novelId: number, repairId: number, payload: { action: 'apply' | 'dismiss'; choice_index?: number; intent_text?: string }) {
    await api.resolveRepair(novelId, repairId, payload)
    pendingRepairs.value = pendingRepairs.value.map(r =>
      r.id === repairId ? { ...r, status: 'applied' as const } : r,
    )
  }

  return {
    blueprints, activeBlueprint, latestPlan, latestBrief, latestContext,
    writingRuns, loading, repairLogs, pendingRepairs,
    fetchBlueprints, generateBlueprint, activateBlueprint, updateBlueprint,
    generateChapterPlan, generateChapterBrief, generateContextPackage,
    createWritingRun, acceptRun, discardRun, fetchWritingRuns,
    fetchRepairs, resolveRepair,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useWritingStore, import.meta.hot))
}
