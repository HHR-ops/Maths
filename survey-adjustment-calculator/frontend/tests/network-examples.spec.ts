import { test, expect } from '@playwright/test'
import path from 'node:path'

test('unmodified examples switch freely but edited projects require replacement confirmation', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('stat-n')).toHaveText('6')
  await page.getByLabel('控制网类型',{exact:true}).selectOption('GNSS网')
  await expect(page.getByTestId('stat-n')).toHaveText('27')
  await expect(page.getByTestId('stat-parameters')).toHaveText('18')
  await expect(page.getByTestId('stat-constraints')).toHaveText('3')
  await expect(page.locator('[data-point="A"]')).toHaveAttribute('data-constrained','true')
  await expect(page.getByTestId('network-example-note')).toContainText('3 项精确限制')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByLabel('控制网类型',{exact:true}).selectOption('测边网')
  await expect(page.getByTestId('stat-t')).toHaveText('5')
  await expect(page.getByTestId('stat-r')).toHaveText('1')
  await expect(page.getByTestId('stat-constraints')).toHaveText('1')
  await page.getByLabel('控制网名称',{exact:true}).fill('我的测边项目')
  await expect(page.getByTestId('network-example-note')).toHaveCount(0)
  await page.getByLabel('控制网类型',{exact:true}).selectOption('坐标观测网')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button',{name:'取消',exact:true}).click()
  await expect(page.getByLabel('控制网名称',{exact:true})).toHaveValue('我的测边项目')
  await expect(page.getByTestId('stat-constraints')).toHaveText('1')
  await page.getByLabel('控制网类型',{exact:true}).selectOption('坐标观测网')
  await page.getByRole('button',{name:'继续',exact:true}).click()
  await expect(page.getByTestId('stat-n')).toHaveText('18')
  await expect(page.getByTestId('stat-constraints')).toHaveText('0')
  await expect(page.locator('[data-point]')).toHaveCount(3)
})

test('a late example response cannot replace the most recent selection', async ({ page }) => {
  let release!:()=>void
  const hold = new Promise<void>(resolve=>{release=resolve})
  let requested = false
  await page.route('**/api',async route=>{
    const data=route.request().postDataJSON()
    if(data.op==='example' && data.payload.family==='GNSS网'){
      const response=await route.fetch()
      requested=true
      await hold
      await route.fulfill({response})
    }else await route.continue()
  })
  await page.goto('/')
  await expect(page.getByTestId('stat-n')).toHaveText('6')
  await page.getByLabel('控制网类型',{exact:true}).selectOption('GNSS网')
  await expect.poll(()=>requested).toBe(true)
  await page.getByLabel('控制网类型',{exact:true}).selectOption('坐标观测网')
  await expect(page.getByTestId('stat-n')).toHaveText('18')
  const reply=page.waitForResponse(r=>r.request().postData()?.includes('"family":"GNSS网"')??false)
  release();await reply
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))
  await expect(page.getByLabel('控制网类型',{exact:true})).toHaveValue('坐标观测网')
  await expect(page.getByTestId('stat-n')).toHaveText('18')
  await expect(page.getByTestId('stat-parameters')).toHaveText('6')
})

test('GNSS Excel template preserves reference station constraints and all five statistics', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('stat-n')).toHaveText('6')
  await page.getByLabel('控制网类型',{exact:true}).selectOption('GNSS网')
  await expect(page.getByTestId('stat-n')).toHaveText('27')
  await page.getByRole('button',{name:'批量导入',exact:true}).click()
  const downloading=page.waitForEvent('download')
  await page.getByRole('button',{name:'Excel 模板',exact:true}).click()
  const file=path.resolve('../qa/v063-gnss-template.xlsx')
  await (await downloading).saveAs(file)
  await page.getByLabel('批量导入方式',{exact:true}).selectOption('replace')
  await page.getByLabel('批量数据文件',{exact:true}).setInputFiles(file)
  await expect(page.locator('.import-table-tabs')).toContainText('限制条件')
  await page.getByRole('button',{name:'检查并预览',exact:true}).click()
  await expect(page.getByTestId('import-validation')).toContainText('数据校验通过')
  await expect(page.getByTestId('import-validation')).toContainText('n=27，t=15，r=12')
  await page.getByRole('button',{name:'替换并导入',exact:true}).click()
  for(const [key,value] of Object.entries({n:27,t:15,r:12,parameters:18,constraints:3})){
    await expect(page.getByTestId('stat-'+key)).toHaveText(String(value))
  }
  await page.getByRole('button',{name:'计算平差',exact:true}).click()
  await expect(page.locator('.solution-summary')).toContainText('平差已完成')
  await expect(page.getByRole('alert')).toHaveCount(0)
})
