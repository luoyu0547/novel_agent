import { describe, expect, it, vi, beforeEach } from 'vitest'
import * as writingApi from '@/api/writing'
import * as planningApi from '@/api/planning'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DecisionCard from '@/components/writing/DecisionCard.vue'
import DraftRevisionDiff from '@/components/writing/DraftRevisionDiff.vue'
import PlotUnitPanel from '@/components/writing/PlotUnitPanel.vue'
import AuthorFoundationPanel from '@/components/writing/AuthorFoundationPanel.vue'
import WritingEditor from '@/components/editor/WritingEditor.vue'
import { usePlotPlanningStore } from '@/stores/plotPlanning'

// --- Mock vue-router ---
vi.mock('vue-router', async () => {
  const actual = await vi.importActual<typeof import('vue-router')>('vue-router')
  return {
    ...actual,
    useRouter: () => ({ back: vi.fn<() => void>(), push: vi.fn<() => void>() }),
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
    get: vi.fn<() => void>(),
    post: vi.fn<() => void>(),
    put: vi.fn<() => void>(),
    delete: vi.fn<() => void>(),
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
const plotUnitFixture = {
  id: 1,
  novel_id: 1,
  title: '主角的抉择',
  scope_type: 'chapter',
  start_position: 1,
  end_position: 3,
  author_goal: '让主角面对道德困境',
  start_state: '主角处于安全环境',
  end_state: '主角做出关键选择',
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
  plan_json: {},
  change_reason: '初始计划',
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
  draft_version_id: null,
  parent_revision_id: null,
  decision_id: 1,
  sequence: 1,
  source_type: 'planning_decision' as const,
  source_id: 1,
  base_revision_sequence: 0,
  base_content_hash: 'abc',
  base_content: '这是原始段落。这是保留的段落。这是将被替换的旧内容。',
  candidate_content: '这是原始段落。这是保留的段落。这是全新的内容。',
  patches_json: [],
  scope_json: { start: 1, end: 2 },
  diff_json: {
    unchanged: ['这是原始段落。', '这是保留的段落。'],
    deleted: ['这是将被替换的旧内容。'],
    added: ['这是全新的内容。'],
  },
  reason: '决策选择',
  expanded_scope: false,
  expanded_scope_reason: null,
  status: 'candidate' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
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

// =============================================
// PlotUnitPanel spec
// =============================================
describe('PlotUnitPanel', () => {
  it('selects a plot unit and emits plan actions', async () => {
    const wrapper = mount(PlotUnitPanel, {
      props: { plotUnits: [plotUnitFixture], activePlan: planFixture, loading: false },
      global: { stubs: globalStubs },
    })
    await wrapper.find('.plot-unit-panel__item-header').trigger('click')
    expect(wrapper.emitted('selectUnit')?.[0]).toEqual([plotUnitFixture])
  })
})

// =============================================
// DecisionCard spec
// =============================================
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

  it('emits choose with decisionId and optionIndex when option button clicked', async () => {
    const wrapper = mount(DecisionCard, {
      props: { decision: decisionFixture },
      global: { stubs: globalStubs },
    })
    const buttons = wrapper.findAll('button')
    const chooseBtn = buttons.find(b => b.text().includes('选择此方案'))
    expect(chooseBtn).toBeDefined()
    await chooseBtn!.trigger('click')
    expect(wrapper.emitted('choose')?.[0]).toEqual([{ decisionId: 1, optionIndex: 0 }])
  })

  it('emits choose with decisionId and customIntent when custom intent is submitted', async () => {
    const wrapper = mount(DecisionCard, {
      props: { decision: decisionFixture },
      global: { stubs: globalStubs },
    })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('希望主角原谅')
    const submitBtn = wrapper.findAll('button').find(b => b.text().includes('调整未来目标'))
    await submitBtn!.trigger('click')
    expect(wrapper.emitted('choose')?.[0]).toEqual([{ decisionId: 1, customIntent: '希望主角原谅' }])
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

// =============================================
// DraftRevisionDiff spec
// =============================================
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

  it('keeps apply button disabled until candidate is selected', () => {
    const wrapper = mount(DraftRevisionDiff, {
      props: { revision: draftRevisionFixture, selected: false },
      global: { stubs: globalStubs },
    })
    const applyBtn = wrapper.findAll('button').find(b => b.text().includes('应用'))
    expect(applyBtn?.attributes('disabled')).toBeDefined()
  })

  it('enables apply button when candidate is selected', () => {
    const wrapper = mount(DraftRevisionDiff, {
      props: { revision: draftRevisionFixture, selected: true },
      global: { stubs: globalStubs },
    })
    const applyBtn = wrapper.findAll('button').find(b => b.text().includes('应用'))
    expect(applyBtn?.attributes('disabled')).toBeUndefined()
  })

  it('does not render a replace button', () => {
    const wrapper = mount(DraftRevisionDiff, {
      props: { revision: draftRevisionFixture, selected: true },
      global: { stubs: globalStubs },
    })
    const replaceBtn = wrapper.findAll('button').find(b => b.text().includes('替换'))
    expect(replaceBtn).toBeUndefined()
  })

  it('emits apply with revision id when apply button clicked', async () => {
    const wrapper = mount(DraftRevisionDiff, {
      props: { revision: draftRevisionFixture, selected: true },
      global: { stubs: globalStubs },
    })
    const applyBtn = wrapper.findAll('button').find(b => b.text().includes('应用'))
    await applyBtn!.trigger('click')
    expect(wrapper.emitted('apply')?.[0]).toEqual([1])
  })
})

// =============================================
// AuthorFoundationPanel spec
// =============================================
describe('AuthorFoundationPanel', () => {
  it('renders foundation data and save button', () => {
    const wrapper = mount(AuthorFoundationPanel, {
      props: { foundation: foundationFixture, loading: false },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('[data-testid="save-foundation"]').exists()).toBe(true)
  })

  it('emits save with outline, intent, and stage goal when save button clicked', async () => {
    const wrapper = mount(AuthorFoundationPanel, {
      props: { foundation: foundationFixture, loading: false },
      global: { stubs: globalStubs },
    })
    await wrapper.find('[data-testid="save-foundation"]').trigger('click')
    expect(wrapper.emitted('save')?.[0]).toEqual([
      { outline: '测试大纲', current_intent: '测试意图', stage_goal: '测试目标' },
    ])
  })
})

// =============================================
// WritingEditor spec
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

  it('applies a draft revision through the revisions API', async () => {
    const client = (await import('@/api/client')).default
    vi.mocked(client.put).mockResolvedValueOnce({
      version: { id: 1, novel_id: 1, chapter_id: null, writing_run_id: 1, based_on_version_id: null, version: 1, title: '', content: '', word_count: 0, change_reason: '', status: 'draft', revision_sequence: 0, acceptance_override_reason: null, created_at: '', updated_at: '' },
      revision: { id: 1, novel_id: 1, writing_run_id: 1, draft_version_id: null, parent_revision_id: null, decision_id: null, sequence: 1, source_type: 'planning_decision', source_id: null, base_revision_sequence: 0, base_content_hash: '', base_content: '', candidate_content: '', patches_json: [], scope_json: {}, diff_json: {}, reason: '', expanded_scope: false, expanded_scope_reason: null, status: 'applied', created_at: '', updated_at: '' },
    })
    await planningApi.applyDraftRevision(1, 30)
    expect(client.put).toHaveBeenCalledWith('/novels/1/draft-revisions/30/apply', { confirm_expanded_scope: false })
  })

  it('does not replace currentDraftRevision on API error', async () => {
    const client = (await import('@/api/client')).default
    vi.mocked(client.put).mockRejectedValueOnce(new Error('API error'))

    const store = usePlotPlanningStore()
    store.currentDraftRevision = null

    await expect(store.chooseDecision(1, 1, { option_index: 0 })).rejects.toThrow('API error')
    expect(store.currentDraftRevision).toBeNull()
  })
})
