import { expect, test } from '@playwright/test'

// Ch14 验收:造评测集 → 发评测 → 看结果 全链路。
// 后端以 E2E_MOCK=1 起,LLM/judge 是确定性假实现、同步执行,不烧钱也不依赖外部服务。
test('主流程:造评测集 → 发评测 → 看结果', async ({ page }) => {
  const dsName = `e2e-${Date.now()}`

  // 1. 新建评测集
  await page.goto('/datasets')
  await page.getByRole('button', { name: '新建评测集' }).click()
  await page.getByPlaceholder('名称').fill(dsName)
  await page.getByPlaceholder('描述').fill('端到端测试')
  await page.getByRole('button', { name: 'OK' }).click()
  await expect(page.locator('tr', { hasText: dsName })).toBeVisible()

  // 2. 进详情加一个样本
  await page.locator('tr', { hasText: dsName }).getByRole('button', { name: '查看' }).click()
  await expect(page).toHaveURL(/\/datasets\/\d+/)
  await page.getByPlaceholder('问题').fill('宝宝发烧怎么办?')
  await page.getByPlaceholder('期望要点(用/分隔)').fill('物理降温/就医')
  await page.getByRole('button', { name: '加样本' }).click()
  await expect(page.getByText('已添加')).toBeVisible()

  // 3. 发起评测(同步执行,发完即 done)
  await page.goto('/runs')
  // antd Select 的 placeholder 是 span 不是 input 属性,getByPlaceholder 匹配不到,改点 combobox;
  // 工具栏现有「选评测集」「检索方式」两个 Select,first() 取第一个(选评测集)
  await page.getByRole('combobox').first().click()
  await page.locator('.ant-select-item-option', { hasText: dsName }).click()
  await page.getByRole('button', { name: '发起评测' }).click()
  await expect(page.locator('tr', { hasText: dsName }).first()).toBeVisible()

  // 4. 看结果:状态 done + 费用/指标卡都渲染出来了
  await page.locator('tr', { hasText: dsName }).getByRole('button', { name: '查看' }).click()
  await expect(page).toHaveURL(/\/runs\/\d+/)
  await expect(page.getByText('费用统计')).toBeVisible()
  // 状态「done」限到 header 里的 Tag:门禁卡基线选择器标签也含 (done),getByText 会撞
  await expect(page.locator('h2').getByText('done')).toBeVisible()
  // 「忠实度」出现在指标卡标题/表格表头/单元格多处,精确定位到指标卡标题
  await expect(page.locator('.ant-statistic-title', { hasText: '忠实度' })).toBeVisible()
})
