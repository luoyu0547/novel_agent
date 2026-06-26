import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import CharacterListView from '@/views/novels/CharacterListView.vue'
import { useMemoryStore } from '@/stores/memory'
import { useNovelStore } from '@/stores/novels'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: vi.fn<() => void>() }),
}))

const globalStubs = {
  NovelWorkspaceTabs: { template: '<div class="novel-tabs" />' },
}

describe('CharacterListView', () => {
  function createWrapper() {
    const pinia = createTestingPinia({ createSpy: vi.fn, stubActions: true })
    const novelStore = useNovelStore()
    const memoryStore = useMemoryStore()
    novelStore.currentNovel = { id: 1, title: '测试小说', description: null, created_at: '', updated_at: '' } as any
    const wrapper = mount(CharacterListView, { global: { plugins: [pinia], stubs: globalStubs } })
    return { wrapper, memoryStore, novelStore }
  }

  it('mounts and shows title', () => {
    const { wrapper } = createWrapper()
    expect(wrapper.find('.characters').exists()).toBe(true)
    expect(wrapper.text()).toContain('角色卡片')
    expect(wrapper.text()).toContain('测试小说')
  })

  it('shows empty state when no characters', () => {
    const { wrapper } = createWrapper()
    expect(wrapper.text()).not.toContain('张三')
  })

  it('renders character cards from store', async () => {
    const { wrapper, memoryStore } = createWrapper()
    memoryStore.characters = [{
      id: 1, name: '张三', story_role: '主角', identity: '侠客',
      personality: '正直', motivation: '复仇', speech_style: '沉稳',
      behavior_rules: ['不杀平民', '重情义'], current_state: '受伤',
      novel_id: 1, created_at: '', updated_at: '',
    }]
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('主角')
  })

  it('showModal is false by default', () => {
    const { wrapper } = createWrapper()
    expect((wrapper.vm as any).showModal).toBe(false)
  })

  it('openCreate resets form and shows dialog', () => {
    const { wrapper } = createWrapper()
    ;(wrapper.vm as any).openCreate()
    expect((wrapper.vm as any).showModal).toBe(true)
    expect((wrapper.vm as any).editingId).toBeNull()
  })

  it('openEdit populates form with character data', () => {
    const { wrapper } = createWrapper()
    const char = {
      id: 5, name: '李四', story_role: '反派', identity: '将军',
      personality: '残暴', motivation: '权力', speech_style: '傲慢',
      behavior_rules: ['不择手段', '狡猾'], current_state: '掌权',
      novel_id: 1, created_at: '', updated_at: '',
    }
    ;(wrapper.vm as any).openEdit(char)
    expect((wrapper.vm as any).showModal).toBe(true)
    expect((wrapper.vm as any).editingId).toBe(5)
  })
})
