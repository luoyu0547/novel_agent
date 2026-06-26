import { test, expect } from '@playwright/test'

test('shows login page for unauthenticated users', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: /Novel Agent/ })).toBeVisible()
})
