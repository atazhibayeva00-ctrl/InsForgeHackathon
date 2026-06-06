import { expect, test } from '@playwright/test'

const BACKEND_URL = process.env.COGYM_HTTP_BASE ?? 'http://127.0.0.1:8010'

test('CoVest demo flow reaches proposal, approval, and dashboard', async ({ page, request }) => {
  test.setTimeout(180_000)

  const health = await request.get(`${BACKEND_URL}/api/health`)
  expect(
    health.ok(),
    `Expected distributed backend to be running at ${BACKEND_URL}. Start Redis and uvicorn before E2E.`,
  ).toBeTruthy()

  await page.goto('/')

  await expect(page.getByText('Stanford Collaborative Gym research paper')).toBeVisible()
  await expect(page.getByRole('link', { name: /view the research/i })).toHaveAttribute(
    'href',
    'https://arxiv.org/abs/2412.15701',
  )

  await page.getByRole('button', { name: /slide to launch/i }).click()
  await expect(page.getByRole('heading', { name: /covest/i })).toBeVisible()

  await page.getByRole('button', { name: /load complex demo/i }).click()
  await expect(page.getByRole('button', { name: /approve plan/i })).toBeVisible({
    timeout: 150_000,
  })

  await page.getByRole('button', { name: /approve plan/i }).click()
  await expect(page.getByRole('heading', { name: /collaboration score/i })).toBeVisible({
    timeout: 60_000,
  })
  await expect(page.getByRole('button', { name: /start next review/i })).toBeVisible()

  await page.getByRole('button', { name: /dashboard/i }).click()
  await expect(page.getByRole('heading', { name: /collaboration score by cycle/i })).toBeVisible()
  await expect(page.getByRole('heading', { name: /expected portfolio value/i })).toBeVisible()
})
