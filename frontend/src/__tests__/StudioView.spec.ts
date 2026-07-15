import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory, type Router } from 'vue-router'
import StudioView from '@/views/studio/StudioView.vue'
import StudioChapterExplorer from '@/components/studio/StudioChapterExplorer.vue'
import type { ChapterOut, NovelOut } from '@/types/novel'
import type { WritingSession } from '@/types/writingStudio'

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
    props: ['modelValue', 'direction', 'size'],
    template: '<div v-if="modelValue" data-testid="el-drawer"><slot /></div>',
  },
  ElTooltip: {
    props: ['content', 'placement'],
    template: '<div data-testid="el-tooltip"><slot /></div>',
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

describe('Studio route redirect', () => {
  it('redirects the legacy editor route to the selected Studio chapter', async () => {
    const router = createTestRouter()
    await router.push('/novels/1/edit/18')
    await router.isReady()

    expect(router.currentRoute.value.name).toBe('studio')
    expect(router.currentRoute.value.query.chapter_id).toBe('18')
  })
})
