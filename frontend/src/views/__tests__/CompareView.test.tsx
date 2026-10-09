import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import CompareView from '../CompareView'

vi.mock('../../api', () => ({
  api: { getRun: vi.fn() },
}))

function runDetail(id: number, scores: Record<string, number | null>, config = '{}') {
  return { id, dataset_id: 1, status: 'done', config, item_count: 2, scores, by_bucket: {} }
}

test('对比多个 run:并排展示各指标列', async () => {
  vi.mocked(api.getRun)
    .mockResolvedValueOnce(runDetail(1, { recall: 0.7, faithfulness: 0.9 }, '{"top_k": 2}'))
    .mockResolvedValueOnce(runDetail(2, { recall: 0.8, faithfulness: 0.85 }, '{"top_k": 5}'))
  render(
    <MemoryRouter initialEntries={['/compare?ids=1,2']}>
      <Routes>
        <Route path="/compare" element={<CompareView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('多 run 对比')).toBeInTheDocument())
  // 两个 run 各一列,列头带 Run 编号 + top_k(来自各自 config 快照)
  expect(screen.getByText('Run #1(top_k=2)')).toBeInTheDocument()
  expect(screen.getByText('Run #2(top_k=5)')).toBeInTheDocument()
  expect(screen.getByText('召回(机械)')).toBeInTheDocument() // 指标行
})
