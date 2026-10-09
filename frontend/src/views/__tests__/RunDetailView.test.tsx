import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import RunDetailView from '../RunDetailView'

vi.mock('../../api', () => ({
  api: { getRun: vi.fn(), listTraces: vi.fn().mockResolvedValue([]) },
}))

test('展示多维指标(动态渲染卡片 + 分桶列)', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 1,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 7,
    scores: {
      recall: 0.75,
      context_precision: 0.81,
      context_recall: 0.68,
      faithfulness: 0.95,
      answer_relevance: 0.88,
      answer_correctness: 0.76,
    },
    by_bucket: {
      护理: {
        count: 2,
        recall: 0.875,
        context_precision: 0.9,
        context_recall: 0.7,
        faithfulness: 1.0,
        answer_relevance: 0.9,
        answer_correctness: 0.8,
      },
    },
  })
  render(
    <MemoryRouter initialEntries={['/runs/1']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('分桶聚合')).toBeInTheDocument())
  // 动态渲染:指标卡片 + 分桶表头都出现中文标签(不止一处,用 getAllByText)
  expect(screen.getAllByText('上下文精度').length).toBeGreaterThan(0)
  expect(screen.getAllByText('答案正确性').length).toBeGreaterThan(0)
  expect(screen.queryByText('拒答率')).not.toBeInTheDocument() // 库内 run 没评拒答
  expect(screen.getByRole('combobox')).toBeInTheDocument() // 分桶图指标切换下拉(Ch07)
})

test('指标全 NULL 时分桶图显示空态(不渲染图表)', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 2,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 1,
    scores: { recall: null, faithfulness: null },
    by_bucket: { 护理: { count: 1, recall: null, faithfulness: null } },
  })
  render(
    <MemoryRouter initialEntries={['/runs/2']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('暂无分桶数据')).toBeInTheDocument())
})
