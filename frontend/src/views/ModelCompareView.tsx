import { Button, Card, Empty, Result, Skeleton, Table } from 'antd'
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import { METRIC_LABELS } from '../utils/metrics'


const fmt = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(4))

export default function ModelCompareView() {
  const { data, loading, error, reload } = useRequest((s) => api.getModelComparison(s), [])

  if (loading) return <Skeleton active paragraph={{ rows: 6 }} />
  if (error)
    return <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />

  const models = data?.models ?? []
  const metricKeys: string[] = []
  for (const m of models) for (const k of Object.keys(m.avg_scores)) if (!metricKeys.includes(k)) metricKeys.push(k)

  // 散点 y 用 faithfulness(没有则第一个指标)
  const yMetric = metricKeys.includes('faithfulness') ? 'faithfulness' : metricKeys[0]
  const scatter = models.map((m) => ({
    name: m.model,
    x: m.avg_cost_per_item,
    y: m.avg_scores[yMetric] ?? 0,
    runs: m.run_count,
  }))

  return (
    <div>
      <h2>模型性价比对比</h2>
      {!models.length ? (
        <Empty description="还没有已完成的评测(run)" style={{ marginTop: 40 }} />
      ) : (
        <>
          <Card title="分数 × 成本" style={{ marginBottom: 16 }}>
            <Table
              rowKey="model"
              size="small"
              dataSource={models}
              columns={[
                { title: '模型', dataIndex: 'model' },
                { title: 'Run 数', dataIndex: 'run_count' },
                ...metricKeys.map((k) => ({
                  title: METRIC_LABELS[k] ?? k,
                  dataIndex: ['avg_scores', k],
                  render: fmt,
                })),
                { title: '平均成本(元/run)', dataIndex: 'avg_cost', render: (v: number) => v.toFixed(6) },
                { title: '单条成本(元)', dataIndex: 'avg_cost_per_item', render: (v: number) => v.toFixed(6) },
              ]}
            />
          </Card>
          <Card title={`散点:单条成本 × ${METRIC_LABELS[yMetric] ?? yMetric}`}>
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart margin={{ top: 24, right: 24, bottom: 24, left: 24 }}>
                <CartesianGrid />
                <XAxis
                  type="number"
                  dataKey="x"
                  name="单条成本"
                  tickFormatter={(v: number) => v.toFixed(5)}
                />
                <YAxis type="number" dataKey="y" domain={[0, 1]} name={METRIC_LABELS[yMetric] ?? yMetric} />
                {/* 不给每个点常显标签(点多会糊成一团),名字放 tooltip 悬停才看 */}
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const m = payload[0].payload as { name: string; x: number; y: number; runs: number }
                    return (
                      <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 6, padding: 8, fontSize: 12 }}>
                        <div style={{ fontWeight: 600 }}>{m.name}</div>
                        <div>Run 数: {m.runs}</div>
                        <div>单条成本: {m.x.toFixed(6)} 元</div>
                        <div>
                          {METRIC_LABELS[yMetric] ?? yMetric}: {m.y.toFixed(4)}
                        </div>
                      </div>
                    )
                  }}
                />
                <Scatter data={scatter} fill="#3b82f6" />
              </ScatterChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}
    </div>
  )
}
