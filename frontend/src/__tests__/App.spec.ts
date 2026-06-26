import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '../App.vue'

describe('App', () => {
  it('mounts the router outlet', () => {
    const wrapper = mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: ['router-view'],
      },
    })

    expect(wrapper.exists()).toBe(true)
  })
})
