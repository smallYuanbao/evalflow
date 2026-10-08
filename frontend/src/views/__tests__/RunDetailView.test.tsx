import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import RunDetailView from '../RunDetailView'

vi.mock('../../api', () => ({
  api: { getRun: vi.fn(), listTraces: vi.fn().mockResolvedValue([]) },
}))

test('展示三层指标', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 1,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 7,
    scores: { recall_avg: 0.75, faithfulness_avg: 1.0, rejection_rate: 1.0 },
    by_bucket: { 护理: { count: 2, recall_avg: 0.875, faithfulness_avg: 1.0, rejection_rate: null } },
  })
  render(
    <MemoryRouter initialEntries={['/runs/1']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('分桶聚合')).toBeInTheDocument())
})

test('无 recall 数据时分桶图显示空态(不渲染图表)', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 2,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 1,
    scores: { recall_avg: null, faithfulness_avg: null, rejection_rate: 1.0 },
    by_bucket: { 库外: { count: 1, recall_avg: null, faithfulness_avg: null, rejection_rate: 1.0 } },
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
