import { test, expect } from '@playwright/test'

const workspaceFixture = {
  code: 0,
  message: 'ok',
  data: {
    session: { id: 7, novel_id: 1, target_chapter_id: 18, active_writing_run_id: 21, title: '第十八章', status: 'active' },
    messages: [],
    working_copy: { writing_run_id: 21, draft_version_id: 31, title: '第十八章', content: '雨夜正文', base_revision_sequence: 0 },
  },
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('token', 'studio-e2e-token'))
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/writing-sessions/7')) {
      await route.fulfill({ json: workspaceFixture })
      return
    }
    if (url.pathname.endsWith('/novels/1')) {
      await route.fulfill({ json: { code: 0, message: 'ok', data: { id: 1, title: '测试小说', chapters: [] } } })
      return
    }
    await route.fulfill({ json: { code: 0, message: 'ok', data: [] } })
  })
})

test('legacy writing link enters Studio and preserves a selected chapter', async ({ page }) => {
  await page.goto('/novels/1/edit/18')
  await expect(page).toHaveURL(/\/novels\/1\/studio\?chapter_id=18/)
  await expect(page.getByTestId('studio-workbench')).toBeVisible()
})

test('Studio route renders the workbench', async ({ page }) => {
  await page.goto('/novels/1/studio?session_id=7')
  await expect(page.getByTestId('studio-workbench')).toBeVisible()
})

test('legacy writing workspace redirects to Studio', async ({ page }) => {
  await page.goto('/novels/1/writing')
  await expect(page).toHaveURL(/\/novels\/1\/studio/)
})
