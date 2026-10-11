import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import RunDetailView from '../RunDetailView'

vi.mock('../../api', () => ({
  api: {
    getRun: vi.fn(),
    listTraces: vi.fn().mockResolvedValue([]),
    listRuns: vi.fn().mockResolvedValue([]), // 门禁卡基线选择器
    getRunGate: vi.fn().mockResolvedValue({ passed: true, checks: [], run_id: 1, baseline_run_id: null }),
  },
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
  expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0) // 分桶图指标切换下拉(Ch07)+ 门禁基线选择器
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

test('展示复现上下文快照(Ch09)', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 3,
    dataset_id: 1,
    status: 'done',
    config: JSON.stringify({
      top_k: 3,
      knowledge_version: 'v1',
      knowledge_hash: 'abcd1234efgh',
      prompt_version: 'v1',
      chat_model: 'deepseek-chat',
      embed_model: 'bge-m3',
      dataset_hash: '9876fedc5432',
      item_count: 7,
    }),
    item_count: 7,
    scores: { recall: 0.75 },
    by_bucket: { 护理: { count: 1, recall: 0.75 } },
  })
  render(
    <MemoryRouter initialEntries={['/runs/3']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('复现上下文')).toBeInTheDocument())
  expect(screen.getByText('知识库版本')).toBeInTheDocument()
  expect(screen.getByText('Prompt 版本')).toBeInTheDocument()
  expect(screen.getByText('deepseek-chat')).toBeInTheDocument()
  expect(screen.getByText('abcd1234')).toBeInTheDocument() // 知识库哈希截断前 8 位
})

test('展示回归门禁(Ch15):FAIL 徽章 + 逐指标判定', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 4,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 1,
    scores: { recall: 0.75, faithfulness: 0.62 },
    by_bucket: { 护理: { count: 1, recall: 0.75, faithfulness: 0.62 } },
  })
  vi.mocked(api.getRunGate).mockResolvedValue({
    passed: false,
    run_id: 4,
    baseline_run_id: null,
    checks: [
      {
        metric: 'faithfulness',
        value: 0.62,
        threshold: 0.7,
        baseline_value: null,
        delta: null,
        passed: false,
        note: '低于阈值',
      },
    ],
  })
  render(
    <MemoryRouter initialEntries={['/runs/4']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('FAIL 不通过')).toBeInTheDocument())
  expect(screen.getByText('低于阈值')).toBeInTheDocument()
})
