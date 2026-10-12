import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import RunsView from '../RunsView'

vi.mock('../../api', () => ({
  api: { listDatasets: vi.fn(), listRuns: vi.fn(), createRun: vi.fn() },
}))

test('渲染 run 列表 + top_k 输入 + 对比按钮初始禁用', async () => {
  vi.mocked(api.listDatasets).mockResolvedValue({ items: [{ id: 1, name: '育儿', description: '', item_count: 7 }], total: 1 })
  vi.mocked(api.listRuns).mockResolvedValue([
    { id: 1, dataset_id: 1, status: 'done', dataset_name: '育儿', config: '{"top_k": 3}' },
    { id: 2, dataset_id: 1, status: 'done', dataset_name: '育儿', config: '{}' },
  ])
  render(
    <MemoryRouter>
      <RunsView />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('top_k=3')).toBeInTheDocument())
  expect(screen.getByText('top_k')).toBeInTheDocument() // top_k 输入框的 addon 前缀
  expect(screen.getByRole('button', { name: /对比/ })).toBeDisabled() // 未勾选时禁用
})

test('最多只能勾选 MAX_COMPARE_RUNS 个(Ch22)', async () => {
  const runs = Array.from({ length: 7 }, (_, i) => ({
    id: i + 1, dataset_id: 1, status: 'done', dataset_name: 't', config: '{}',
  }))
  vi.mocked(api.listDatasets).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(api.listRuns).mockResolvedValue(runs)
  render(
    <MemoryRouter>
      <RunsView />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getAllByRole('checkbox').length).toBe(8)) // 全选 + 7 行
  const rowBoxes = screen.getAllByRole('checkbox').slice(1) // 跳过表头「全选」
  for (const box of rowBoxes) fireEvent.click(box) // 全部点一遍(7 个)
  // 第 7 次被拦下,最终只选中 6 个
  await waitFor(() => {
    const checked = screen.getAllByRole('checkbox').filter((c) => (c as HTMLInputElement).checked)
    expect(checked.length).toBe(6)
  })
})

test('支持跨分页勾选:翻页后已选的不丢(Ch22)', async () => {
  const runs = Array.from({ length: 15 }, (_, i) => ({
    id: i + 1, dataset_id: 1, status: 'done', dataset_name: 't', config: '{}',
  }))
  vi.mocked(api.listDatasets).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(api.listRuns).mockResolvedValue(runs)
  render(
    <MemoryRouter>
      <RunsView />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getAllByRole('checkbox').length).toBe(11)) // 全选 + 第 1 页 10 行
  fireEvent.click(screen.getAllByRole('checkbox')[1]) // 第 1 页勾 1 个
  await waitFor(() => expect(screen.getByRole('button', { name: /对比\(1\)/ })).toBeInTheDocument())

  fireEvent.click(screen.getByTitle('2')) // 翻到第 2 页
  await waitFor(() => expect(screen.getAllByRole('checkbox').length).toBe(6)) // 全选 + 第 2 页 5 行
  fireEvent.click(screen.getAllByRole('checkbox')[1]) // 第 2 页再勾 1 个

  // 两页各 1 个 = 2(跨页不丢)
  await waitFor(() => expect(screen.getByRole('button', { name: /对比\(2\)/ })).toBeInTheDocument())
})

test('已选项显示成标签,可单个删除 / 一键清空(Ch22)', async () => {
  vi.mocked(api.listDatasets).mockResolvedValue({ items: [], total: 0 })
  vi.mocked(api.listRuns).mockResolvedValue([
    { id: 1, dataset_id: 1, status: 'done', dataset_name: '育儿', config: '{}' },
    { id: 2, dataset_id: 1, status: 'done', dataset_name: '育儿', config: '{}' },
    { id: 3, dataset_id: 1, status: 'done', dataset_name: '育儿', config: '{}' },
  ])
  const { container } = render(
    <MemoryRouter>
      <RunsView />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getAllByRole('checkbox').length).toBe(4)) // 全选 + 3 行
  for (const b of screen.getAllByRole('checkbox').slice(1)) fireEvent.click(b)

  // 已选标签渲染出来了(看得见选了谁)
  await waitFor(() => expect(screen.getByText('已选:')).toBeInTheDocument())
  expect(screen.getByText('Run #1')).toBeInTheDocument()
  expect(screen.getByText('Run #3')).toBeInTheDocument()

  // 点某个标签的 × → 只删掉那一个
  fireEvent.click(container.querySelector('.ant-tag-close-icon')!)
  await waitFor(() => expect(screen.getByRole('button', { name: /对比\(2\)/ })).toBeInTheDocument())

  // 清空 → 标签整行消失
  fireEvent.click(screen.getByRole('button', { name: /清\s*空/ }))
  await waitFor(() => expect(screen.queryByText('已选:')).not.toBeInTheDocument())
})
