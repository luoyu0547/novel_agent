import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WritingWorkspaceView from '@/views/novels/WritingWorkspaceView.vue'
import { usePlotPlanningStore } from '@/stores/plotPlanning'
import * as writingApi from '@/api/writing'
import * as planningApi from '@/api/planning'
import DecisionCard from '@/components/writing/DecisionCard.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({
    back: vi.fn<() => void>(),
    push: vi.fn<(...args: unknown[]) => unknown>(),
  }),
  useRoute: () => ({
    params: { id: '1' },
    query: {},
    path: '/novels/1/writing',
    fullPath: '/novels/1/writing',
    name: 'WritingWorkspace',
    hash: '',
    matched: [],
    meta: {},
    redirectedFrom: undefined,
  }),
}))

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn<(...args: unknown[]) => unknown>(),
    post: vi.fn<(...args: unknown[]) => unknown>(),
    put: vi.fn<(...args: unknown[]) => unknown>(),
    delete: vi.fn<(...args: unknown[]) => unknown>(),
  },
}))

vi.mock('@/api/writing')
vi.mock('@/api/planning')

const stubs = {
  NovelWorkspaceTabs: true,
  ElInput: { template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
  ElInputNumber: { template: '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />' },
  ElSelect: { template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
  ElOption: { template: '<option :value="value"><slot /></option>' },
  ElButton: { template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>' },
  ElText: { template: '<span><slot /></span>' },
  ElDivider: false,
  ElCard: { template: '<div><slot name="header" /><slot /></div>' },
  ElAlert: { template: '<div><slot /><slot name="title" /></div>' },
  ElTag: { template: '<span><slot /></span>' },
  ElForm: { template: '<form><slot /></form>' },
  ElFormItem: { template: '<div><slot /></div>' },
  ElCollapse: false,
  ElCollapseItem: false,
  ElCollapseTransition: false,
  ElTextarea: { template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
}

const foundationFixture = {
  id: 1,
  novel_id: 1,
  outline: '测试大纲',
  current_intent: '测试意图',
  stage_goal: '测试目标',
  constraints_json: {},
  version: 1,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const plotUnitFixture = {
  id: 1,
  novel_id: 1,
  title: '第一卷：边城旧案',
  scope_type: 'volume',
  start_position: 1,
  end_position: 5,
  author_goal: '查清旧案',
  start_state: '主角抵达边城',
  end_state: '主角确认旧案与密令相连',
  foundation_revision_id: 1,
  status: 'active',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const planFixture = {
  id: 1,
  novel_id: 1,
  plot_unit_id: 1,
  foundation_revision_id: 1,
  based_on_published_chapter_id: null,
  version: 1,
  plan_json: { core_conflict: '调查触动守城势力' },
  change_reason: 'initial',
  status: 'draft' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const decisionFixture = {
  id: 1,
  novel_id: 1,
  plot_unit_id: 1,
  plot_plan_revision_id: 1,
  chapter_brief_id: null,
  writing_run_id: 1,
  source: 'during_generation' as const,
  status: 'pending' as const,
  conflict_summary: '核心冲突：主角应该复仇还是放下仇恨？',
  evidence_json: {},
  options_json: [
    { label: '补充因果', action: 'supplement', consequence: '保留已发布事实' },
    { label: '改写未来', action: 'rewrite_future', consequence: '延后揭示' },
  ],
  recommended_index: 0,
  recommendation_reason: '最小影响',
  impact_scope_json: { type: 'scene' },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const decisionFixture2 = {
  id: 2,
  novel_id: 1,
  plot_unit_id: 1,
  plot_plan_revision_id: 1,
  chapter_brief_id: null,
  writing_run_id: 2,
  source: 'during_generation' as const,
  status: 'pending' as const,
  conflict_summary: '另一个冲突：如何处理叛徒？',
  evidence_json: {},
  options_json: [
    { label: '收买', action: 'bribe', consequence: '保留线人' },
    { label: '除掉', action: 'kill', consequence: '失去情报' },
  ],
  recommended_index: 1,
  recommendation_reason: '推荐收买',
  impact_scope_json: { type: 'scene' },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function setupCommonMocks() {
  vi.mocked(planningApi.getFoundation).mockResolvedValue(foundationFixture)
  vi.mocked(planningApi.listPlotUnits).mockResolvedValue([])
  vi.mocked(planningApi.listDecisions).mockResolvedValue([])
  vi.mocked(writingApi.listBlueprints).mockResolvedValue([])
  vi.mocked(writingApi.listWritingRuns).mockResolvedValue([])
}

describe('WritingWorkspace Phase 3 flow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders foundation panel and wires save button', async () => {
    setupCommonMocks()
    vi.mocked(planningApi.updateFoundation).mockResolvedValue(foundationFixture)

    const wrapper = mount(WritingWorkspaceView, {
      global: { plugins: [createPinia()], stubs },
    })

    await new Promise(r => setTimeout(r, 50))

    const btn = wrapper.find('[data-testid="save-foundation"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    expect(planningApi.updateFoundation).toHaveBeenCalled()
  })

  it('selects a plot unit and generates a plan', async () => {
    setupCommonMocks()
    vi.mocked(planningApi.listPlotUnits).mockResolvedValue([plotUnitFixture])
    vi.mocked(planningApi.listPlotPlans).mockResolvedValue([planFixture])
    vi.mocked(planningApi.generatePlotPlan).mockResolvedValue(planFixture)

    const wrapper = mount(WritingWorkspaceView, {
      global: { plugins: [createPinia()], stubs },
    })

    await new Promise(r => setTimeout(r, 50))

    const ppStore = usePlotPlanningStore()
    expect(ppStore.plotUnits.length).toBe(1)

    await wrapper.find('.plot-unit-panel__item-header').trigger('click')
    await new Promise(r => setTimeout(r, 50))
    expect(planningApi.listPlotPlans).toHaveBeenCalled()

    const planInput = wrapper.find('input[placeholder="输入创作意图（可选）"]')
    await planInput.setValue('调查主线')

    const generateBtn = wrapper.findAll('button').filter(
      (b) => b.text().includes('生成计划'),
    )[0]
    expect(generateBtn).toBeDefined()
    await generateBtn!.trigger('click')

    expect(planningApi.generatePlotPlan).toHaveBeenCalledWith(1, 1, '调查主线')
  })

  it('confirms a draft plan when activePlan is set and unit is selected', async () => {
    setupCommonMocks()
    vi.mocked(planningApi.listPlotUnits).mockResolvedValue([plotUnitFixture])
    vi.mocked(planningApi.listPlotPlans).mockResolvedValue([planFixture])
    vi.mocked(planningApi.confirmPlotPlan).mockResolvedValue({
      ...planFixture, status: 'active',
    })

    const wrapper = mount(WritingWorkspaceView, {
      global: { plugins: [createPinia()], stubs },
    })

    await new Promise(r => setTimeout(r, 50))

    const ppStore = usePlotPlanningStore()
    ppStore.plotUnits = [plotUnitFixture]

    await wrapper.find('.plot-unit-panel__item-header').trigger('click')
    await new Promise(r => setTimeout(r, 50))

    ppStore.activePlan = planFixture
    await new Promise(r => setTimeout(r, 50))

    const confirmBtn = wrapper.find('[data-testid="confirm-plot-plan"]')
    expect(confirmBtn.exists()).toBe(true)
    await confirmBtn.trigger('click')

    expect(planningApi.confirmPlotPlan).toHaveBeenCalled()
  })

  it('renders two decision cards and resolves the second one', async () => {
    setupCommonMocks()

    const wrapper = mount(WritingWorkspaceView, {
      global: { plugins: [createPinia()], stubs },
    })

    await new Promise(r => setTimeout(r, 50))

    const ppStore = usePlotPlanningStore()
    ppStore.pendingDecisions = [decisionFixture, decisionFixture2]
    await new Promise(r => setTimeout(r, 50))

    vi.mocked(planningApi.chooseDecision).mockResolvedValue({
      decision: { ...decisionFixture2, status: 'resolved' },
      new_plan: null,
      draft_revision: {
        id: 1, novel_id: 1, writing_run_id: 2, parent_revision_id: null,
        decision_id: 2, base_content: '', candidate_content: '',
        scope_json: {}, diff_json: {}, reason: '', status: 'candidate',
        created_at: '', updated_at: '',
      },
    })

    const decisionCards = wrapper.findAllComponents(DecisionCard)
    expect(decisionCards.length).toBe(2)

    const secondCard = decisionCards[1]
    expect(secondCard).toBeDefined()
    const buttons = secondCard!.findAll('button')
    const chooseBtn = buttons.find((b) => b.text().includes('选择此方案'))
    expect(chooseBtn).toBeDefined()
    await chooseBtn!.trigger('click')

    expect(planningApi.chooseDecision).toHaveBeenCalled()
    const callArgs = vi.mocked(planningApi.chooseDecision).mock.calls[0]
    expect(callArgs).toBeDefined()
    expect(callArgs![0]).toBe(1)
    expect(callArgs![1]).toBe(2)
  })
})
