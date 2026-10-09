import { useSearchParams } from 'react-router-dom'
import { Button, Empty, Result, Skeleton, Table } from 'antd'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import type { RunDetail } from '../types'

// 指标 key → 中文标签(与 RunDetailView 一致)
const METRIC_LABELS: Record<string, string> = {
  recall: '召回(机械)',
  context_precision: '上下文精度',
  context_recall: '上下文召回',
  faithfulness: '忠实度',
  answer_relevance: '答案相关性',
  answer_correctness: '答案正确性',
  rejection: '拒答率',
}

const COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899']

const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(4))

function topKOf(run: RunDetail): string {
  try {
    const cfg = JSON.parse(run.config || '{}')
    return cfg.top_k != null ? `top_k=${cfg.top_k}` : ''
  } catch {
    return ''
  }
}

export default function CompareView() {
  const [params] = useSearchParams()
  const idsStr = params.get('ids') ?? ''
  const ids = idsStr.split(',').map(Number).filter((n) => Number.isFinite(n) && n > 0)

  // 复用 GET /runs/{id} 并发拉取,不新增批量接口(run 数量少,并发拉够快)
  const { data: runs, loading, error, reload } = useRequest(
    (s) => Promise.all(ids.map((id) => api.getRun(id, s))),
    [idsStr],
  )

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />
  if (error)
    return <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
  if (!ids.length)
    return <Empty description="未选择要对比的 run(请回评测记录勾选 2 个以上)" style={{ marginTop: 40 }} />
  if (!runs?.length) return null

  // 指标集合 = 各 run scores key 的并集(保序)
  const metricKeys: string[] = []
  for (const r of runs) for (const k of Object.keys(r.scores)) if (!metricKeys.includes(k)) metricKeys.push(k)

  const rows = metricKeys.map((k) => {
    const row: Record<string, string | number | null> = { metric: METRIC_LABELS[k] ?? k }
    for (const r of runs) row[`run_${r.id}`] = r.scores[k] ?? null
    return row
  })

  const chartData = metricKeys.map((k) => {
    const d: Record<string, string | number | null> = { metric: METRIC_LABELS[k] ?? k }
    for (const r of runs) d[`run_${r.id}`] = r.scores[k] ?? null
    return d
  })

  const hasValue = chartData.some((d) => runs.some((r) => d[`run_${r.id}`] != null))

  return (
    <div>
      <h2>多 run 对比</h2>
      <Table
        rowKey="metric"
        size="small"
        style={{ marginBottom: 16 }}
        dataSource={rows}
        columns={[
          { title: '指标', dataIndex: 'metric' },
          ...runs.map((r) => {
            const cfg = topKOf(r)
            return {
              title: cfg ? `Run #${r.id}(${cfg})` : `Run #${r.id}`,
              dataIndex: `run_${r.id}`,
              render: fmt,
            }
          }),
        ]}
      />
      {hasValue ? (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="metric" />
            <YAxis domain={[0, 1]} />
            <Tooltip />
            <Legend />
            {runs.map((r, i) => (
              <Bar key={r.id} dataKey={`run_${r.id}`} name={`Run #${r.id}`} fill={COLORS[i % COLORS.length]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <Empty description="暂无对比数据" />
      )}
    </div>
  )
}
