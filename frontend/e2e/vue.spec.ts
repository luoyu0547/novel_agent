import { test, expect } from '@playwright/test'

test('shows login page for unauthenticated users', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByText('登录你的账号')).toBeVisible()
})
