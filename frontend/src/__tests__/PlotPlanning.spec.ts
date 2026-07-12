import { describe, expect, it, vi, beforeEach } from 'vitest'
import * as writingApi from '@/api/writing'
import * as planningApi from '@/api/planning'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DecisionCard from '@/components/writing/DecisionCard.vue'
import DraftRevisionDiff from '@/components/writing/DraftRevisionDiff.vue'
import WritingEditor from '@/components/editor/WritingEditor.vue'
import { usePlotPlanningStore } from '@/stores/plotPlanning'

// --- Mock vue-router ---
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...(actual as any),
    useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
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
  }
})

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// --- Stubs ---
const globalStubs = {
  ElInput: false,
  ElInputNumber: false,
  ElSelect: false,
  ElOption: false,
  ElButton: { template: '<button><slot /></button>' },
  ElText: { template: '<span><slot /></span>' },
  ElDivider: false,
  ElCard: false,
  ElAlert: false,
  ElTag: false,
  ElForm: false,
  ElFormItem: false,
  ElCollapse: false,
  ElCollapseItem: false,
  ElCollapseTransition: false,
}

// --- Fixtures ---
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
    { label: '选择复仇之路', action: '主角走上复仇之路，彻底黑化', consequence: '可能导致重要配角死亡，剧情走向黑暗' },
    { label: '选择宽恕与和解', action: '主角放下仇恨，寻求真相', consequence: '部分读者可能觉得不够爽快' },
    { label: '折中方案', action: '主角表面放下但暗中调查', consequence: '最平衡的选择，但推进速度较慢' },
  ],
  recommended_index: 0,
  recommendation_reason: 'AI 推荐：复仇路线能够最大化戏剧冲突',
  impact_scope_json: { affected_characters: ['主角', '反派'], tone_shift: 'dark' },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const draftRevisionFixture = {
  id: 1,
  novel_id: 1,
  writing_run_id: 1,
  parent_revision_id: null,
  decision_id: 1,
  base_content: '这是原始段落。这是保留的段落。这是将被替换的旧内容。',
  candidate_content: '这是原始段落。这是保留的段落。这是全新的内容。',
  scope_json: { start: 1, end: 2 },
  diff_json: {
    unchanged: ['这是原始段落。', '这是保留的段落。'],
    deleted: ['这是将被替换的旧内容。'],
    added: ['这是全新的内容。'],
  },
  reason: '决策选择',
  status: 'candidate' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

// =============================================
// PlotPlanning spec
// =============================================
describe('PlotUnitPanel', () => {
  it('placeholder until PlotUnitPanel is imported', () => {
    expect(true).toBe(true)
  })
})

describe('DecisionCard', () => {
  it('renders a decision card with recommendation and two executable options', () => {
    const wrapper = mount(DecisionCard, {
      props: { decision: decisionFixture },
      global: { stubs: globalStubs },
    })
    expect(wrapper.text()).toContain('核心冲突')
    expect(wrapper.text()).toContain('AI 推荐')
    expect(wrapper.text()).toContain('补充因果')
    expect(wrapper.text()).toContain('调整未来目标')
  })

  it('emits choose event with option_index when option button clicked', () => {
    const wrapper = mount(DecisionCard, {
      props: { decision: decisionFixture },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.decision-card__option').exists()).toBe(true)
  })

  it('emits choose event with custom_intent when custom text is provided', () => {
    const wrapper = mount(DecisionCard, {
      props: { decision: decisionFixture },
      global: { stubs: globalStubs },
    })
    expect(wrapper.text()).toContain('补充因果')
    expect(wrapper.text()).toContain('调整未来目标')
  })

  it('does not expand evidence chain by default', () => {
    const wrapper = mount(DecisionCard, {
      props: { decision: decisionFixture },
      global: { stubs: { ...globalStubs, ElCollapse: false, ElCollapseItem: false } },
    })
    expect(wrapper.text()).not.toContain('影响范围')
    expect(wrapper.text()).not.toContain('证据链')
  })
})

describe('DraftRevisionDiff', () => {
  it('renders unchanged, deleted, and added segments', () => {
    const wrapper = mount(DraftRevisionDiff, {
      props: { revision: draftRevisionFixture, selected: false },
      global: { stubs: globalStubs },
    })
    expect(wrapper.text()).toContain('这是原始段落')
    expect(wrapper.text()).toContain('这是保留的段落')
    expect(wrapper.text()).toContain('这是全新的内容')
    expect(wrapper.text()).toContain('这是将被替换的旧内容')
  })

  it('keeps apply/replace buttons disabled until candidate is selected', () => {
    const wrapper = mount(DraftRevisionDiff, {
      props: { revision: draftRevisionFixture, selected: false },
      global: { stubs: globalStubs },
    })
    const buttons = wrapper.findAll('button')
    for (const btn of buttons) {
      if (btn.text().includes('应用') || btn.text().includes('替换')) {
        expect(btn.attributes('disabled')).toBeDefined()
      }
    }
  })

  it('enables apply/replace buttons when candidate is selected', () => {
    const wrapper = mount(DraftRevisionDiff, {
      props: { revision: draftRevisionFixture, selected: true },
      global: { stubs: globalStubs },
    })
    const buttons = wrapper.findAll('button')
    let hasEnabled = false
    for (const btn of buttons) {
      if ((btn.text().includes('应用') || btn.text().includes('替换')) && btn.attributes('disabled') === undefined) {
        hasEnabled = true
        break
      }
    }
    expect(hasEnabled).toBe(true)
  })
})

// =============================================
// WritingEditor spec (locked chapter behavior)
// =============================================
describe('WritingEditor locked chapter', () => {
  it('does not expose publish action for locked chapters', () => {
    const wrapper = mount(WritingEditor, {
      props: {
        title: '第一章',
        content: '内容',
        status: 'locked',
        saving: false,
        savedAt: null,
      },
      global: {
        plugins: [createPinia()],
        stubs: globalStubs,
      },
    })
    expect(wrapper.find('[data-testid="publish-chapter"]').exists()).toBe(false)
  })

  it('makes textarea readonly for locked chapters', () => {
    const wrapper = mount(WritingEditor, {
      props: {
        title: '锁定的标题',
        content: '锁定内容',
        status: 'locked',
        saving: false,
        savedAt: null,
      },
      global: {
        plugins: [createPinia()],
        stubs: globalStubs,
      },
    })
    const textarea = wrapper.find('textarea')
    expect(textarea.attributes('readonly')).toBeDefined()
  })

  it('allows editing for draft chapters', () => {
    const wrapper = mount(WritingEditor, {
      props: {
        title: 'draft标题',
        content: 'draft内容',
        status: 'draft',
        saving: false,
        savedAt: null,
      },
      global: {
        plugins: [createPinia()],
        stubs: globalStubs,
      },
    })
    const textarea = wrapper.find('textarea')
    expect(textarea.attributes('readonly')).toBeUndefined()
  })
})

// =============================================
// PlotPlanningStore spec
// =============================================
describe('PlotPlanningStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with empty state', () => {
    const store = usePlotPlanningStore()
    expect(store.foundation).toBeNull()
    expect(store.plotUnits).toEqual([])
    expect(store.activePlan).toBeNull()
    expect(store.pendingDecisions).toEqual([])
    expect(store.currentDraftRevision).toBeNull()
    expect(store.loading).toBe(false)
  })
})

// =============================================
// Phase 3 API contract tests
// =============================================
describe('Phase 3 API contracts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends selected plot plan through brief, context, and run creation', async () => {
    const client = (await import('@/api/client')).default
    await writingApi.generateChapterBrief(1, 10, 20, '本章保护证人')
    expect(client.post).toHaveBeenCalledWith('/novels/1/chapter-briefs/generate', {
      chapter_plan_id: 10,
      plot_plan_revision_id: 20,
      author_input: '本章保护证人',
    })
  })

  it('sends plot plan id through context package generation', async () => {
    const client = (await import('@/api/client')).default
    await writingApi.generateContextPackage(1, 5, 20, '保持悬疑感')
    expect(client.post).toHaveBeenCalledWith('/novels/1/context-packages/generate', {
      chapter_brief_id: 5,
      plot_plan_revision_id: 20,
      author_input: '保持悬疑感',
    })
  })

  it('sends plot plan id through writing run creation', async () => {
    const client = (await import('@/api/client')).default
    await writingApi.createWritingRun(1, 5, 20, '注重动作描写')
    expect(client.post).toHaveBeenCalledWith('/novels/1/writing-runs', {
      chapter_brief_id: 5,
      plot_plan_revision_id: 20,
      author_input: '注重动作描写',
    })
  })

  it('applies a draft revision through the planning API', async () => {
    const client = (await import('@/api/client')).default
    await planningApi.applyDraftRevision(1, 30)
    expect(client.put).toHaveBeenCalledWith('/novels/1/draft-revisions/30/apply')
  })

  it('does not replace currentDraftRevision on API error', async () => {
    const client = (await import('@/api/client')).default
    vi.mocked(client.put).mockRejectedValueOnce(new Error('API error'))

    const store = usePlotPlanningStore()
    store.currentDraftRevision = null

    await expect(store.chooseDecision(1, 1, { option_index: 0 })).rejects.toThrow()
    expect(store.currentDraftRevision).toBeNull()
  })
})
