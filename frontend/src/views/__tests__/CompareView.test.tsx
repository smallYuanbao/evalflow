import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import CompareView from '../CompareView'

vi.mock('../../api', () => ({
  api: { getRun: vi.fn(), getRunDiff: vi.fn().mockResolvedValue(null) },
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
  // 表头与图例统一用同一套标签,所以各出现两次 → getAllByText
  expect(screen.getAllByText('Run #1(top_k=2)').length).toBeGreaterThan(0)
  expect(screen.getAllByText('Run #2(top_k=5)').length).toBeGreaterThan(0)
  expect(screen.getByText('召回(机械)')).toBeInTheDocument() // 指标行
})

test('选 2 个 run 展示逐条 diff(delta 高亮)', async () => {
  vi.mocked(api.getRun)
    .mockResolvedValueOnce(runDetail(1, { faithfulness: 0.7 }))
    .mockResolvedValueOnce(runDetail(2, { faithfulness: 0.85 }))
  vi.mocked(api.getRunDiff).mockResolvedValue({
    run_a_id: 1,
    run_b_id: 2,
    different_datasets: false,
    pairs: [
      {
        item_id: 1,
        input: '宝宝发烧怎么办',
        a: { trace_id: 1, output: 'o', retrieved_context: '证据A', scores: { faithfulness: 0.7 } },
        b: { trace_id: 2, output: 'o', retrieved_context: '证据B', scores: { faithfulness: 0.85 } },
        deltas: { faithfulness: 0.15 },
      },
    ],
  })
  render(
    <MemoryRouter initialEntries={['/compare?ids=1,2']}>
      <Routes>
        <Route path="/compare" element={<CompareView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('逐条 Diff')).toBeInTheDocument())
  expect(screen.getByText('宝宝发烧怎么办')).toBeInTheDocument()
  expect(screen.getByText('证据A')).toBeInTheDocument()
  expect(screen.getByText('证据B')).toBeInTheDocument()
  expect(screen.getByText(/忠实度 \+0\.1500/)).toBeInTheDocument() // delta 绿标
})
