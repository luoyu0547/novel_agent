import { acceptHMRUpdate, defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/planning'
import * as revisionApi from '@/api/revisions'
import type { AuthorFoundation, AuthorFoundationUpdate, PlotUnit, PlotUnitCreate, PlotPlanRevision, PlanningDecision, DraftRevision, ChooseDecisionRequest } from '@/types/plotPlanning'

export const usePlotPlanningStore = defineStore('plotPlanning', () => {
  const foundation = ref<AuthorFoundation | null>(null)
  const plotUnits = ref<PlotUnit[]>([])
  const activePlan = ref<PlotPlanRevision | null>(null)
  const pendingDecisions = ref<PlanningDecision[]>([])
  const currentDraftRevision = ref<DraftRevision | null>(null)
  const selectedPlotUnit = ref<PlotUnit | null>(null)
  const planRevisions = ref<PlotPlanRevision[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchFoundation(novelId: number) {
    try {
      foundation.value = await api.getFoundation(novelId)
    } catch {
      foundation.value = null
    }
  }

  async function updateFoundation(novelId: number, data: AuthorFoundationUpdate) {
    loading.value = true
    try {
      foundation.value = await api.updateFoundation(novelId, data)
      return foundation.value
    } finally {
      loading.value = false
    }
  }

  async function fetchPlotUnits(novelId: number) {
    plotUnits.value = await api.listPlotUnits(novelId)
  }

  async function createPlotUnit(novelId: number, data: PlotUnitCreate) {
    loading.value = true
    try {
      const unit = await api.createPlotUnit(novelId, data)
      plotUnits.value.push(unit)
      return unit
    } finally {
      loading.value = false
    }
  }

  async function generatePlan(novelId: number, plotUnitId: number, authorInput: string) {
    loading.value = true
    try {
      const plan = await api.generatePlotPlan(novelId, plotUnitId, authorInput)
      return plan
    } finally {
      loading.value = false
    }
  }

  async function confirmPlan(novelId: number, plotUnitId: number, revisionId: number) {
    loading.value = true
    try {
      const plan = await api.confirmPlotPlan(novelId, plotUnitId, revisionId)
      // Only update active plan after API success confirmation
      activePlan.value = plan
      return plan
    } finally {
      loading.value = false
    }
  }

  async function fetchPendingDecisions(novelId: number) {
    pendingDecisions.value = await api.listDecisions(novelId, 'pending')
  }

  async function chooseDecision(novelId: number, decisionId: number, data: ChooseDecisionRequest) {
    loading.value = true
    try {
      const resolution = await api.chooseDecision(novelId, decisionId, data)
      // Use server response to replace local decision
      pendingDecisions.value = pendingDecisions.value.filter(d => d.id !== decisionId)
      if (resolution.new_plan) {
        activePlan.value = resolution.new_plan
      }
      currentDraftRevision.value = resolution.draft_revision
      return resolution
    } finally {
      loading.value = false
    }
  }

  async function fetchPlans(novelId: number, plotUnitId: number) {
    const plans = await api.listPlotPlans(novelId, plotUnitId)
    const active = plans.find(p => p.status === 'active')
    if (active) {
      activePlan.value = active
    }
    return plans
  }

  async function selectPlotUnit(novelId: number, unit: PlotUnit) {
    selectedPlotUnit.value = unit
    planRevisions.value = await api.listPlotPlans(novelId, unit.id)
    activePlan.value = planRevisions.value.find(plan => plan.status === 'active') || null
  }

  async function applyDraftRevision(novelId: number, revisionId: number) {
    loading.value = true
    try {
      const response = await revisionApi.applyRevision(novelId, revisionId, false)
      // Only clear local candidate after server success
      currentDraftRevision.value = null
      return response.revision
    } finally {
      loading.value = false
    }
  }

  return {
    foundation,
    plotUnits,
    activePlan,
    pendingDecisions,
    currentDraftRevision,
    selectedPlotUnit,
    planRevisions,
    loading,
    error,
    fetchFoundation,
    updateFoundation,
    fetchPlotUnits,
    createPlotUnit,
    generatePlan,
    confirmPlan,
    fetchPendingDecisions,
    chooseDecision,
    fetchPlans,
    selectPlotUnit,
    applyDraftRevision,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(usePlotPlanningStore, import.meta.hot))
}
