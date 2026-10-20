import { test, expect, type Page } from '@playwright/test'

async function ready(page: Page) { await page.goto('/'); await expect(page.getByTestId('stat-n')).toHaveText('5') }
async function continueIfPrompt(page: Page) { const button = page.getByRole('button', { name: '继续', exact: true }); if (await button.isVisible()) await button.click() }

test('home layout and responsive controls render without external requests', async ({ page }) => {
  const errors: string[] = [], external: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => { if (!r.url().startsWith('http://127.0.0.1:8877')) external.push(r.url()) })
  await ready(page)
  await page.screenshot({ path: '../qa/react-home.png', fullPage: true })
  for (const width of [1440, 1280, 1060]) {
    await page.setViewportSize({ width, height: 960 })
    await expect(page.getByRole('button', { name: '计算精度', exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const clipped = await page.locator('button,input,select').evaluateAll(els => els.filter(el => { const r = el.getBoundingClientRect(); const style = getComputedStyle(el); return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && (r.left < -1 || r.right > innerWidth+1) && !el.closest('.sidebar-content') }).map(e => e.textContent))
    expect(clipped).toEqual([])
    if (width === 1060) await page.screenshot({ path: '../qa/react-compact.png', fullPage: true })
  }
  await page.setViewportSize({ width: 1440, height: 1050 })
  await page.getByRole('button', { name: '计算精度', exact: true }).click()
  await expect(page.getByRole('tab', { name: '精度评估' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.solution-summary')).toContainText('设计精度已计算')
  await page.screenshot({ path: '../qa/react-precision.png', fullPage: true })
  expect(errors).toEqual([]); expect(external).toEqual([])
})

test('canvas add, drag, connect, edit, delete and undo keep live statistics consistent', async ({ page }) => {
  await ready(page)
  await page.getByRole('button', { name: '添加控制点', exact: true }).click()
  const canvas = page.getByTestId('network-canvas'), bounds = (await canvas.boundingBox())!
  await page.mouse.click(bounds.x+bounds.width*.7, bounds.y+bounds.height*.65)
  await expect(page.locator('[data-point="P1"]')).toBeVisible()
  await expect(page.getByTestId('stat-parameters')).toHaveText('4')
  await page.getByRole('button', { name: '绘制高差', exact: true }).click()
  await page.getByRole('button', { name: '选择点 A', exact: true }).click()
  await page.getByRole('button', { name: '选择点 P1', exact: true }).click()
  await expect(page.getByTestId('stat-n')).toHaveText('6')
  await expect(page.getByTestId('stat-t')).toHaveText('4')
  await page.getByRole('button', { name: '编辑观测 O6', exact: true }).click()
  await page.getByRole('textbox', { name: '实测值', exact: true }).fill('1.5')
  await page.getByRole('textbox', { name: '标准差', exact: true }).fill('0.002')
  await page.getByRole('button', { name: '保存观测', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.getByRole('button', { name: '选择工具', exact: true }).click()
  const before = await page.locator('[data-point="P1"]').getAttribute('transform')
  const p = (await page.locator('[data-point="P1"]').boundingBox())!
  await page.mouse.move(p.x+p.width/2, p.y+p.height/2); await page.mouse.down(); await page.mouse.move(p.x+p.width/2+40, p.y+p.height/2-20, { steps: 5 }); await page.mouse.up()
  await expect(page.locator('[data-point="P1"]')).not.toHaveAttribute('transform', before!)
  await page.getByRole('button', { name: '删除控制点', exact: true }).click()
  await continueIfPrompt(page)
  await expect(page.getByTestId('stat-n')).toHaveText('5')
  await page.getByRole('button', { name: '撤销', exact: true }).click()
  await expect(page.getByTestId('stat-n')).toHaveText('6')
  await expect(page.locator('[data-point="P1"]')).toBeVisible()
})

test('all seven networks and four methods produce real precision results', async ({ page }) => {
  await ready(page)
  const families = ['水准网', '导线网', 'GNSS网', '测边网', '测角网', '边角网', '坐标观测网']
  const counts = [5, 10, 15, 6, 6, 12, 8]
  const methods = ['condition', 'condition_parameters', 'indirect', 'indirect_constraints']
  for (let i = 0; i < families.length; i++) {
    if (i) { await page.getByLabel('控制网类型', { exact: true }).selectOption(families[i]); await continueIfPrompt(page) }
    await expect(page.getByTestId('stat-n')).toHaveText(String(counts[i]))
    for (const method of methods) {
      await page.getByLabel('平差方法', { exact: true }).selectOption(method)
      const calculate = page.getByRole('button', { name: '计算精度', exact: true })
      await expect(calculate).toBeEnabled(); await calculate.click()
      await expect(page.locator('.solution-summary')).toContainText('设计精度已计算')
      await expect(page.getByRole('alert')).toHaveCount(0)
    }
    if (families[i] === 'GNSS网') { await expect(page.locator('.data-panel')).toContainText('三维 / mm'); await page.screenshot({ path: '../qa/react-gnss.png', fullPage: true }) }
  }
})

test('measured GNSS with covariance validates input and clears stale results', async ({ page }) => {
  await ready(page)
  await page.getByLabel('控制网类型', { exact: true }).selectOption('GNSS网'); await continueIfPrompt(page)
  await page.getByRole('button', { name: '实测平差', exact: true }).click()
  await page.getByRole('button', { name: '计算平差', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('实测值')
  await page.getByRole('button', { name: '示例', exact: true }).click(); await continueIfPrompt(page)
  await page.getByRole('button', { name: '编辑观测 O1', exact: true }).click()
  await expect(page.getByLabel('协方差阵', { exact: true })).not.toHaveValue('')
  await page.getByLabel('协方差阵', { exact: true }).fill('-1 0 0\n0 1 0\n0 0 1')
  await page.getByRole('button', { name: '保存观测', exact: true }).click()
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('正定')
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('button', { name: '计算平差', exact: true }).click()
  await expect(page.locator('.solution-summary')).toContainText('平差已完成')
  await page.getByRole('tab', { name: '观测数据' }).click()
  await page.getByRole('button', { name: '编辑观测 O1', exact: true }).click()
  await page.getByLabel('实测值', { exact: true }).fill('0, 120, 2')
  await page.getByRole('button', { name: '保存观测', exact: true }).click()
  await expect(page.locator('.solution-summary')).toHaveCount(0)
})

test('matrix examples solve, extraction works, and report export contains full results', async ({ page }) => {
  await ready(page)
  for (const name of ['条件平差', '附参条件平差', '间接平差', '附限间接平差']) {
    await page.getByRole('button', { name, exact: true }).click()
    await page.locator('.matrix-submit').getByRole('button', { name: '计算平差', exact: true }).click()
    await expect(page.locator('.result-summary')).toBeVisible()
    await expect(page.getByRole('alert')).toHaveCount(0)
  }
  await expect(page.locator('.matrix-results')).toContainText('101.001')
  await page.getByRole('button', { name: '控制网布设', exact: true }).click()
  await page.getByRole('button', { name: '提取至矩阵工作台' }).click()
  await expect(page.getByLabel('矩阵 B', { exact: true })).not.toHaveValue('')
  await page.locator('.matrix-submit').getByRole('button', { name: '计算平差', exact: true }).click()
  await expect(page.locator('.result-summary')).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'JSON', exact: true }).click()
  expect((await download).suggestedFilename()).toContain('.json')
})

test('old project import and saved export round trip with explicit constraints', async ({ page }) => {
  await ready(page)
  await page.getByRole('button', { name: '限制条件', exact: true }).click()
  await page.getByLabel('限制方程', { exact: true }).fill('B.H:1 C.H:1 = 203.2')
  await page.getByRole('button', { name: '应用限制', exact: true }).click()
  await expect(page.getByTestId('stat-constraints')).toHaveText('1')
  await expect(page.getByTestId('stat-t')).toHaveText('2')
  await page.getByRole('button', { name: '计算精度', exact: true }).click()
  await expect(page.locator('.solution-summary')).toBeVisible()
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: '保存项目', exact: true }).click()
  const download = await downloading, path = await download.path()
  await page.getByLabel('导入项目文件', { exact: true }).setInputFiles(path!)
  await continueIfPrompt(page)
  await expect(page.getByTestId('stat-constraints')).toHaveText('1')
  await page.reload()
  await expect(page.getByTestId('stat-constraints')).toHaveText('1')
})
