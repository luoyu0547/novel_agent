import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import WritingEditor from '@/components/editor/WritingEditor.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn<() => void>() }),
  useRoute: () => ({ params: { id: '1' } }),
}))

const globalStubs = {
  ElInput: true,
  ElInputNumber: true,
  ElSelect: true,
  ElOption: true,
  ElButton: true,
  ElText: { template: '<span><slot /></span>' },
  ElDivider: true,
}

describe('WritingEditor', () => {
  it('renders title and content props', () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '第一章', content: '正文内容', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    expect(wrapper.findComponent({ name: 'ElInput' })).toBeTruthy()
  })

  it('emits update:title when title input changes', async () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '第一章', content: '', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    const titleInput = wrapper.findAllComponents({ name: 'ElInput' })[0]
    titleInput?.vm.$emit('update:modelValue', '第二章')
    expect(wrapper.emitted('update:title')).toBeTruthy()
    expect(wrapper.emitted('update:title')?.[0]).toEqual(['第二章'])
  })

  it('emits update:content when content changes', async () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '', content: '旧内容', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    const contentTextarea = wrapper.findAllComponents({ name: 'ElInput' })[1]
    contentTextarea?.vm.$emit('update:modelValue', '新内容')
    expect(wrapper.emitted('update:content')?.[0]).toEqual(['新内容'])
  })

  it('emits save when debounce timer fires', async () => {
    vi.useFakeTimers()
    const wrapper = mount(WritingEditor, {
      props: { title: '', content: '内容', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    const contentTextarea = wrapper.findAllComponents({ name: 'ElInput' })[1]
    contentTextarea?.vm.$emit('update:modelValue', '新内容')
    vi.advanceTimersByTime(3000)
    expect(wrapper.emitted('save')).toBeTruthy()
    vi.useRealTimers()
  })

  it('displays word count', () => {
    const wrapper = mount(WritingEditor, {
      props: { title: '', content: 'HelloWorld', status: 'draft', saving: false, savedAt: null },
      global: { plugins: [createPinia()], stubs: globalStubs },
    })
    expect(wrapper.text()).toContain('10')
  })
})
