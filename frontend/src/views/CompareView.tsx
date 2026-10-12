import { useSearchParams } from 'react-router-dom'
import { Alert, Button, Card, Empty, Result, Skeleton, Table, Tag } from 'antd'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import { COMPARE_COLORS } from '../utils/compare'
import type { RunDetail, RunDiffSide } from '../types'

// 指标 key → 中文标签(与 RunDetailView 一致)
const METRIC_LABELS: Record<string, string> = {
  recall: '召回(机械)',
  hit_at_k: '命中@k',
  mrr: 'MRR',
  context_precision: '上下文精度',
  context_recall: '上下文召回',
  faithfulness: '忠实度',
  answer_relevance: '答案相关性',
  answer_correctness: '答案正确性',
  rejection: '拒答率',
}

const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(4))

function topKOf(run: RunDetail): string {
  try {
    const cfg = JSON.parse(run.config || '{}')
    return cfg.top_k != null ? `top_k=${cfg.top_k}` : ''
  } catch {
    return ''
  }
}

// 表格列头与图例用同一套标签,避免「同一个 run 两种表示」
function runLabel(r: RunDetail): string {
  const cfg = topKOf(r)
  return cfg ? `Run #${r.id}(${cfg})` : `Run #${r.id}`
}

// 逐条 Diff 的一侧(Ch18):证据 + 分数
function DiffSide({ title, side }: { title: string; side: RunDiffSide | null }) {
  if (!side)
    return (
      <div style={{ flex: 1 }}>
        <Tag>{title}</Tag>
        <div style={{ color: '#999', fontSize: 12 }}>—</div>
      </div>
    )
  const scoreText = Object.entries(side.scores)
    .map(([k, v]) => `${METRIC_LABELS[k] ?? k}=${v == null ? '—' : v.toFixed(4)}`)
    .join(' ')
  return (
    <div style={{ flex: 1 }}>
      <Tag color="blue">{title}</Tag>
      <div style={{ fontSize: 12, color: '#666' }}>{side.retrieved_context || '—'}</div>
      <div style={{ fontSize: 12, marginTop: 4 }}>{scoreText || '—'}</div>
    </div>
  )
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
  // 逐条 diff(Ch18):只有正好 2 个 run 才有意义
  const { data: diff } = useRequest(
    (s) => (ids.length === 2 ? api.getRunDiff(ids[0], ids[1], s) : Promise.resolve(null)),
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
        scroll={{ x: 'max-content' }} // 列数随 run 数增长,横向滚动兜底,别撑坏布局
        dataSource={rows}
        columns={[
          { title: '指标', dataIndex: 'metric' },
          ...runs.map((r) => ({
            title: runLabel(r),
            dataIndex: `run_${r.id}`,
            render: fmt,
          })),
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
              <Bar
                key={r.id}
                dataKey={`run_${r.id}`}
                name={runLabel(r)}
                fill={COMPARE_COLORS[i % COMPARE_COLORS.length]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <Empty description="暂无对比数据" />
      )}

      {ids.length === 2 ? (
        <Card title="逐条 Diff" style={{ marginTop: 16 }}>
          {diff?.different_datasets && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="两次 run 不在同一评测集,逐条对比可能无意义"
            />
          )}
          {diff?.pairs.length ? (
            diff.pairs.map((p) => (
              <Card key={p.item_id} size="small" style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>{p.input ?? '(无输入)'}</div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <DiffSide title={`Run #${diff.run_a_id}`} side={p.a} />
                  <DiffSide title={`Run #${diff.run_b_id}`} side={p.b} />
                </div>
                {Object.keys(p.deltas).length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {Object.entries(p.deltas).map(([m, d]) => (
                      <Tag key={m} color={d >= 0 ? 'green' : 'red'}>
                        {METRIC_LABELS[m] ?? m} {d >= 0 ? '+' : ''}
                        {d.toFixed(4)}
                      </Tag>
                    ))}
                  </div>
                )}
              </Card>
            ))
          ) : (
            <Empty description="暂无逐条 diff 数据" />
          )}
        </Card>
      ) : (
        <Card title="逐条 Diff" style={{ marginTop: 16 }}>
          <Empty description="选 2 个 run 才能逐条对比" />
        </Card>
      )}
    </div>
  )
}
