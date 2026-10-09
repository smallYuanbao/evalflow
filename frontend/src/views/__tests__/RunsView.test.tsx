import { render, screen, waitFor } from '@testing-library/react'
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
