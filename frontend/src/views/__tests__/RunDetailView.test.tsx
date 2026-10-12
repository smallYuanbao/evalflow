import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    getRunCalibration: vi.fn().mockResolvedValue({ run_id: 1, metrics: {} }),
    getBucketAttribution: vi.fn().mockResolvedValue(null),
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

test('运行中的 run 详情页会启动 1.5s 轮询', async () => {
  const spy = vi.spyOn(globalThis, 'setInterval')
  vi.mocked(api.getRun).mockResolvedValue({
    id: 6,
    dataset_id: 1,
    status: 'running',
    config: '{}',
    item_count: 10,
    progress: 3,
    scores: { recall: 0.75 },
    by_bucket: { 护理: { count: 1, recall: 0.75 } },
  })
  render(
    <MemoryRouter initialEntries={['/runs/6']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText(/进度/)).toBeInTheDocument())
  expect(spy).toHaveBeenCalledWith(expect.any(Function), 1500) // running → 启动 1.5s 轮询
  spy.mockRestore()
})

test('逐条明细展开行能看到 Judge reason(Ch18)', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 7,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 1,
    scores: { faithfulness: 0.8 },
    by_bucket: { 护理: { count: 1, faithfulness: 0.8 } },
  })
  vi.mocked(api.listTraces).mockResolvedValue([
    {
      trace_id: 1,
      input: '宝宝发烧怎么办',
      output: '物理降温',
      retrieved_context: '物理降温 观察体温',
      retrieval_hits: [{ text: '物理降温', score: 0.9, rank: 1 }],
      latency_ms: 10,
      scores: [{ name: 'faithfulness', value: 0.8, comment: '回答忠于证据' }],
    },
  ])
  const { container } = render(
    <MemoryRouter initialEntries={['/runs/7']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('宝宝发烧怎么办')).toBeInTheDocument())
  const btn = container.querySelector('.ant-table-row-expand-icon')
  expect(btn).toBeTruthy()
  fireEvent.click(btn!)
  await waitFor(() => expect(screen.getByText('回答忠于证据')).toBeInTheDocument())
  expect(screen.getByText(/证据上下文/)).toBeInTheDocument()
})

test('展示 Judge 校准卡(Ch18)', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 8,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 1,
    scores: { faithfulness: 0.8 },
    by_bucket: { 护理: { count: 1, faithfulness: 0.8 } },
  })
  vi.mocked(api.getRunCalibration).mockResolvedValue({
    run_id: 8,
    metrics: { faithfulness: { bias: -0.1, mae: 0.1, corr: null, n: 1 } },
  })
  render(
    <MemoryRouter initialEntries={['/runs/8']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText(/Judge 校准/)).toBeInTheDocument())
  expect(screen.getByText('Bias(偏松/偏严)')).toBeInTheDocument()
  expect(screen.getByText(/-0\.1000/)).toBeInTheDocument()
})

test('展示分桶归因(Ch19)', async () => {
  vi.mocked(api.getRun).mockResolvedValue({
    id: 9,
    dataset_id: 1,
    status: 'done',
    config: '{}',
    item_count: 2,
    scores: { faithfulness: 0.8 },
    by_bucket: { 护理: { count: 2, faithfulness: 0.8 } },
  })
  vi.mocked(api.listRuns).mockResolvedValue([{ id: 1, dataset_id: 1, status: 'done', config: '{}' }])
  vi.mocked(api.getBucketAttribution).mockResolvedValue({
    run_id: 9,
    baseline_run_id: 1,
    buckets: [{ bucket: '护理', count: 2, deltas: { faithfulness: 0.1 } }],
  })
  render(
    <MemoryRouter initialEntries={['/runs/9']}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText(/分桶归因/)).toBeInTheDocument())
  expect(screen.getAllByText('护理').length).toBeGreaterThan(0) // 分桶聚合表 + 归因表都有
  expect(screen.getByText(/\+0\.1000/)).toBeInTheDocument() // 归因 delta 绿标
})
