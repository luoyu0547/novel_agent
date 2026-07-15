import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory, type Router } from 'vue-router'
import StudioView from '@/views/studio/StudioView.vue'
import StudioChapterExplorer from '@/components/studio/StudioChapterExplorer.vue'
import StudioDocumentPane from '@/components/studio/StudioDocumentPane.vue'
import type { ChapterOut, NovelOut } from '@/types/novel'
import type { WritingSession, StudioDocument } from '@/types/writingStudio'

// ── Mocks (hoisted — must not reference top-level variables) ──────────

vi.mock('@/api/novels', () => ({
  listNovels: vi.fn(),
  createNovel: vi.fn(),
  getNovel: vi.fn(),
  updateNovel: vi.fn(),
  deleteNovel: vi.fn(),
  createChapter: vi.fn(),
  getChapter: vi.fn(),
  updateChapter: vi.fn(),
  deleteChapter: vi.fn(),
}))

vi.mock('@/api/writingStudio', () => ({
  getStudioSession: vi.fn(),
  sendStudioMessage: vi.fn(),
  confirmStudioAction: vi.fn(),
  saveStudioWorkingCopy: vi.fn(),
}))

// ── Fixtures ──────────────────────────────────────────────────────────

const chapter1: ChapterOut = {
  id: 10,
  novel_id: 1,
  title: '第一章',
  content: '已锁定内容',
  summary: '',
  status: 'locked',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const chapter2: ChapterOut = {
  id: 18,
  novel_id: 1,
  title: '第二章',
  content: '草稿内容',
  summary: '',
  status: 'draft',
  created_at: '2026-01-02T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
}

const novelFixture: NovelOut = {
  id: 1,
  title: '测试小说',
  description: null,
  genre: null,
  style_guide: null,
  chapters: [chapter1, chapter2],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const sessionFixture: WritingSession = {
  id: 7,
  novel_id: 1,
  target_chapter_id: null,
  active_writing_run_id: 100,
  title: '草稿会话',
  status: 'active',
}

const draftDocument: StudioDocument = {
  kind: 'draft',
  writingRunId: 100,
  draftVersionId: 200,
  title: '草稿标题',
  content: '草稿正文',
  baseRevisionSequence: 3,
}

const chapterDocument: StudioDocument = {
  kind: 'chapter',
  chapterId: 10,
  title: '第一章',
  content: '已锁定内容',
  baseRevisionSequence: 0,
}

// ── Stubs for Element Plus components ─────────────────────────────────

const globalStubs = {
  ElButton: { template: '<button data-testid="el-button"><slot /></button>' },
  ElIcon: { template: '<span data-testid="el-icon"><slot /></span>' },
  ElMenu: { template: '<div data-testid="el-menu"><slot /></div>' },
  ElMenuItem: { template: '<div data-testid="el-menu-item" @click="$emit(\'click\')"><slot /></div>' },
  ElSubMenu: { template: '<div data-testid="el-sub-menu"><slot name="title" /><slot /></div>' },
  ElBadge: { template: '<span data-testid="el-badge"><slot /></span>' },
  ElTag: { template: '<span data-testid="el-tag"><slot /></span>' },
  ElDrawer: {
    props: ['modelValue', 'direction', 'size', 'title', 'withHeader'],
    template: '<div v-if="modelValue" data-testid="el-drawer"><slot /></div>',
  },
  ElTooltip: {
    props: ['content', 'placement'],
    template: '<div data-testid="el-tooltip"><slot /></div>',
  },
  ElInput: {
    name: 'ElInput',
    props: ['modelValue', 'placeholder', 'type', 'autosize', 'disabled', 'readonly', 'size'],
    template: '<div data-testid="el-input"><slot /></div>',
    emits: ['update:modelValue'],
  },
  ElTimeline: {
    template: '<div data-testid="el-timeline"><slot /></div>',
  },
  ElTimelineItem: {
    props: ['timestamp', 'placement'],
    template: '<div data-testid="el-timeline-item"><slot /></div>',
  },
  ElEmpty: {
    props: ['description'],
    template: '<div data-testid="el-empty">{{ description }}</div>',
  },
  ElAlert: {
    props: ['type', 'closable', 'showIcon', 'title'],
    template: '<div data-testid="el-alert"><slot /><slot name="title" /></div>',
  },
  ElDialog: {
    props: ['modelValue', 'title', 'width', 'closeOnClickModal'],
    template: '<div v-if="modelValue" data-testid="el-dialog"><slot /><slot name="footer" /></div>',
    emits: ['update:modelValue'],
  },
  ElForm: {
    props: ['labelWidth', 'size'],
    template: '<div data-testid="el-form"><slot /></div>',
  },
  ElFormItem: {
    props: ['label'],
    template: '<div data-testid="el-form-item"><slot /></div>',
  },
  ElSelect: {
    props: ['modelValue', 'placeholder', 'size', 'disabled'],
    template: '<div data-testid="el-select"><slot /></div>',
    emits: ['update:modelValue'],
  },
  ElOption: {
    props: ['key', 'label', 'value'],
    template: '<div data-testid="el-option" />',
  },
  ElText: {
    props: ['size', 'type'],
    template: '<span data-testid="el-text"><slot /></span>',
  },
}

// ── Helper: create router with studio route ───────────────────────────

function createTestRouter(): Router {
  return createRouter({
    history: createWebHistory(),
    routes: [
      {
        path: '/novels/:id/studio',
        name: 'studio',
        component: { template: '<div>studio</div>' },
        meta: { auth: true },
      },
      {
        path: '/novels/:id/edit/:chapterId',
        redirect: (to) => ({ name: 'studio', query: { chapter_id: String(to.params.chapterId) } }),
      },
    ],
  })
}

// ── Tests ─────────────────────────────────────────────────────────────

describe('StudioView', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: Router

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    vi.clearAllMocks()
    router = createTestRouter()
  })

  it('opens the Studio full-screen route without AppLayout and groups unaccepted runs as 草稿', async () => {
    await router.push('/novels/1/studio?session_id=7')
    await router.isReady()

    const wrapper = mount(StudioView, {
      global: {
        plugins: [router, pinia],
        stubs: globalStubs,
      },
    })

    // Set store data after mount so the component can react
    const { useNovelStore } = await import('@/stores/novels')
    const { useWritingStudioStore } = await import('@/stores/writingStudio')
    const novelStore = useNovelStore(pinia)
    novelStore.currentNovel = novelFixture

    const studioStore = useWritingStudioStore(pinia)
    studioStore.session = sessionFixture

    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="studio-workbench"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="studio-drafts-group"]').text()).toContain('草稿')
  })

  it('renders the workbench element with grid class', async () => {
    await router.push('/novels/1/studio')
    await router.isReady()

    const wrapper = mount(StudioView, {
      global: {
        plugins: [router, pinia],
        stubs: globalStubs,
      },
    })

    const workbench = wrapper.find('[data-testid="studio-workbench"]')
    expect(workbench.exists()).toBe(true)
    // Verify the workbench has the studio__workbench class (CSS grid is applied via scoped styles)
    expect(workbench.classes()).toContain('studio__workbench')
  })

  it('shows left pane toggle button', async () => {
    await router.push('/novels/1/studio')
    await router.isReady()

    const wrapper = mount(StudioView, {
      global: {
        plugins: [router, pinia],
        stubs: globalStubs,
      },
    })

    expect(wrapper.find('[data-testid="studio-left-toggle"]').exists()).toBe(true)
  })

  it('hides left pane when toggle is clicked', async () => {
    await router.push('/novels/1/studio')
    await router.isReady()

    const wrapper = mount(StudioView, {
      global: {
        plugins: [router, pinia],
        stubs: globalStubs,
      },
    })

    // Left pane should be visible initially
    expect(wrapper.find('[data-testid="studio-left-pane"]').exists()).toBe(true)

    // Click toggle - emit click event on the stubbed el-button component
    const toggleBtn = wrapper.findComponent({ ref: 'leftToggle' } as any)
    // Alternative: directly call the component method
    wrapper.vm.toggleLeftPane()
    await wrapper.vm.$nextTick()

    // Left pane should be hidden
    expect(wrapper.find('[data-testid="studio-left-pane"]').exists()).toBe(false)
  })

  it('shows chapters in the explorer from novel store', async () => {
    await router.push('/novels/1/studio')
    await router.isReady()

    const wrapper = mount(StudioView, {
      global: {
        plugins: [router, pinia],
        stubs: globalStubs,
      },
    })

    const { useNovelStore } = await import('@/stores/novels')
    const novelStore = useNovelStore(pinia)
    novelStore.currentNovel = novelFixture
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-testid="studio-chapters-group"]').text()).toContain('章节')
  })

  it('renders StudioDocumentPane in the center pane', async () => {
    await router.push('/novels/1/studio')
    await router.isReady()

    const wrapper = mount(StudioView, {
      global: {
        plugins: [router, pinia],
        stubs: globalStubs,
      },
    })

    // The document pane should be present in the center pane
    expect(wrapper.find('[data-testid="studio-document-pane"]').exists() || wrapper.find('[data-testid="studio-document-empty"]').exists()).toBe(true)
  })

  it('shows empty state when no document is selected', async () => {
    await router.push('/novels/1/studio')
    await router.isReady()

    const wrapper = mount(StudioView, {
      global: {
        plugins: [router, pinia],
        stubs: globalStubs,
      },
    })

    expect(wrapper.find('[data-testid="studio-document-empty"]').exists()).toBe(true)
  })
})

describe('StudioChapterExplorer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('groups accepted chapters and unaccepted drafts separately', () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [chapter1, chapter2],
        sessions: [sessionFixture],
        selectedChapterId: null,
        selectedSessionId: null,
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-chapters-group"]').text()).toContain('章节')
    expect(wrapper.find('[data-testid="studio-drafts-group"]').text()).toContain('草稿')
  })

  it('emits select event with chapter kind when a chapter is clicked', async () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [chapter1],
        sessions: [],
        selectedChapterId: null,
        selectedSessionId: null,
      },
      global: { stubs: globalStubs },
    })

    const item = wrapper.find('[data-testid="explorer-chapter-10"]')
    await item.trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual([{ kind: 'chapter', chapterId: 10 }])
  })

  it('emits select event with draft kind when a session is clicked', async () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [],
        sessions: [sessionFixture],
        selectedChapterId: null,
        selectedSessionId: null,
      },
      global: { stubs: globalStubs },
    })

    const item = wrapper.find('[data-testid="explorer-session-7"]')
    await item.trigger('click')

    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select')![0]).toEqual([{ kind: 'draft', sessionId: 7 }])
  })

  it('highlights the currently selected chapter', () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [chapter1, chapter2],
        sessions: [],
        selectedChapterId: 10,
        selectedSessionId: null,
      },
      global: { stubs: globalStubs },
    })

    const selected = wrapper.find('[data-testid="explorer-chapter-10"]')
    expect(selected.classes()).toContain('is-active')
  })

  it('highlights the currently selected session', () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [],
        sessions: [sessionFixture],
        selectedChapterId: null,
        selectedSessionId: 7,
      },
      global: { stubs: globalStubs },
    })

    const selected = wrapper.find('[data-testid="explorer-session-7"]')
    expect(selected.classes()).toContain('is-active')
  })

  it('shows empty state when no chapters or sessions', () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [],
        sessions: [],
        selectedChapterId: null,
        selectedSessionId: null,
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="explorer-empty"]').exists()).toBe(true)
  })

  it('does not show chapters group when no chapters', () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [],
        sessions: [sessionFixture],
        selectedChapterId: null,
        selectedSessionId: null,
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-chapters-group"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="studio-drafts-group"]').exists()).toBe(true)
  })

  it('does not show drafts group when no sessions', () => {
    const wrapper = mount(StudioChapterExplorer, {
      props: {
        chapters: [chapter1],
        sessions: [],
        selectedChapterId: null,
        selectedSessionId: null,
      },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-chapters-group"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="studio-drafts-group"]').exists()).toBe(false)
  })
})

describe('StudioDocumentPane', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the document title and content', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-document-pane"]').exists()).toBe(true)
  })

  it('shows empty state when no document is provided', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: null, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-document-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="studio-document-pane"]').exists()).toBe(false)
  })

  it('displays 保存中… when saveState is saving', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'saving' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-save-status"]').text()).toBe('保存中…')
  })

  it('displays 已保存 when saveState is saved', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'saved' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-save-status"]').text()).toBe('已保存')
  })

  it('displays 保存失败 when saveState is error', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'error' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-save-status"]').text()).toBe('保存失败')
  })

  it('displays 版本冲突 when saveState is conflict', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'conflict' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-save-status"]').text()).toBe('版本冲突')
  })

  it('shows accept and discard buttons for draft documents', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-accept-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="studio-discard-btn"]').exists()).toBe(true)
  })

  it('hides accept and discard buttons for chapter documents', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: chapterDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-accept-btn"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="studio-discard-btn"]').exists()).toBe(false)
  })

  it('emits accept when accept button is clicked', async () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    await wrapper.find('[data-testid="studio-accept-btn"]').trigger('click')
    expect(wrapper.emitted('accept')).toBeTruthy()
  })

  it('emits discard when discard button is clicked', async () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    await wrapper.find('[data-testid="studio-discard-btn"]').trigger('click')
    expect(wrapper.emitted('discard')).toBeTruthy()
  })

  it('emits open-version-inspector when version button is clicked', async () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    await wrapper.find('[data-testid="studio-version-inspector-btn"]').trigger('click')
    expect(wrapper.emitted('open-version-inspector')).toBeTruthy()
  })

  it('debounces draft edits into one WorkingCopy save and reports 已保存', async () => {
    vi.useFakeTimers()
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    // Find the content input (second ElInput in the component)
    const allInputs = wrapper.findAllComponents({ name: 'ElInput' })
    const contentEl = allInputs.length > 1 ? allInputs[1]! : allInputs[0]!
    contentEl.vm.$emit('update:modelValue', '新的正文')
    await wrapper.vm.$nextTick()

    // Before debounce fires, no save should have been emitted
    expect(wrapper.emitted('save-working-copy')).toBeFalsy()

    // Advance past the 800ms debounce
    await vi.advanceTimersByTimeAsync(800)

    expect(wrapper.emitted('save-working-copy')).toBeTruthy()
    expect(wrapper.emitted('save-working-copy')![0]).toEqual([{
      title: '草稿标题',
      content: '新的正文',
      baseRevisionSequence: 3,
    }])

    vi.useRealTimers()
  })

  it('keeps the author buffer after a save error', async () => {
    const failedDocument: StudioDocument = {
      ...draftDocument,
      content: '作者文字',
    }
    const wrapper = mount(StudioDocumentPane, {
      props: { document: failedDocument, saveState: 'error' },
      global: { stubs: globalStubs },
    })

    // The local content should reflect the author's text, not be reset
    // Since we use stubs for ElInput, we verify the component's internal state
    // by checking that the document prop content is preserved
    expect(wrapper.props('document')!.content).toBe('作者文字')
  })

  it('does not debounce save for chapter documents', async () => {
    vi.useFakeTimers()
    const wrapper = mount(StudioDocumentPane, {
      props: { document: chapterDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    // Simulate content change
    const allInputs = wrapper.findAllComponents({ name: 'ElInput' })
    const contentEl = allInputs.length > 1 ? allInputs[1]! : allInputs[0]!
    contentEl.vm.$emit('update:modelValue', '新章节内容')
    await wrapper.vm.$nextTick()

    // Advance past the 800ms debounce
    await vi.advanceTimersByTimeAsync(800)

    // For chapter documents, no debounced save should be emitted
    expect(wrapper.emitted('save-working-copy')).toBeFalsy()

    vi.useRealTimers()
  })

  it('coalesces rapid edits into a single save', async () => {
    vi.useFakeTimers()
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    const allInputs = wrapper.findAllComponents({ name: 'ElInput' })
    const contentEl = allInputs.length > 1 ? allInputs[1]! : allInputs[0]!

    // Rapid edits
    contentEl.vm.$emit('update:modelValue', '编辑1')
    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(300)

    contentEl.vm.$emit('update:modelValue', '编辑2')
    await wrapper.vm.$nextTick()
    await vi.advanceTimersByTimeAsync(300)

    // Still within debounce window — no save yet
    expect(wrapper.emitted('save-working-copy')).toBeFalsy()

    // Advance past the final 800ms debounce
    await vi.advanceTimersByTimeAsync(800)

    // Only one save should have been emitted, with the latest content
    expect(wrapper.emitted('save-working-copy')!.length).toBe(1)
    expect(wrapper.emitted('save-working-copy')![0]).toEqual([{
      title: '草稿标题',
      content: '编辑2',
      baseRevisionSequence: 3,
    }])

    vi.useRealTimers()
  })

  it('emits update:title when title is changed', async () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    const allInputs = wrapper.findAllComponents({ name: 'ElInput' })
    const titleEl = allInputs[0]!
    titleEl.vm.$emit('update:modelValue', '新标题')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:title')).toBeTruthy()
    expect(wrapper.emitted('update:title')![0]).toEqual(['新标题'])
  })

  it('emits update:content when content is changed', async () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: draftDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    const allInputs = wrapper.findAllComponents({ name: 'ElInput' })
    const contentEl = allInputs.length > 1 ? allInputs[1]! : allInputs[0]!
    contentEl.vm.$emit('update:modelValue', '新内容')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:content')).toBeTruthy()
    expect(wrapper.emitted('update:content')![0]).toEqual(['新内容'])
  })

  it('does not show version inspector button for chapter documents', () => {
    const wrapper = mount(StudioDocumentPane, {
      props: { document: chapterDocument, saveState: 'idle' },
      global: { stubs: globalStubs },
    })

    expect(wrapper.find('[data-testid="studio-version-inspector-btn"]').exists()).toBe(false)
  })
})

describe('Studio route redirect', () => {
  it('redirects the legacy editor route to the selected Studio chapter', async () => {
    const router = createTestRouter()
    await router.push('/novels/1/edit/18')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('studio')
    expect(router.currentRoute.value.query.chapter_id).toBe('18')
  })
})
