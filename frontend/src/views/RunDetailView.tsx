import { useParams } from 'react-router-dom'
import { Button, Card, Result, Skeleton, Table, Tag } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import MetricCard from '../components/MetricCard'
import BucketChart from '../components/BucketChart'

const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(4))

// 指标 key → 中文标签(后端只认 key,展示文案放前端)
const METRIC_LABELS: Record<string, string> = {
  recall: '召回(机械)',
  context_precision: '上下文精度',
  context_recall: '上下文召回',
  faithfulness: '忠实度',
  answer_relevance: '答案相关性',
  answer_correctness: '答案正确性',
  rejection: '拒答率',
}

export default function RunDetailView() {
  const { runId } = useParams()
  const id = Number(runId)
  const { data: run, loading, error, reload } = useRequest((s) => api.getRun(id, s), [id])
  const { data: traces } = useRequest((s) => api.listTraces(id, s), [id])

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />
  if (error)
    return (
      <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
    )
  if (!run) return null

  const metricKeys = Object.keys(run.scores)
  // 柱状图默认画「召回(机械)」,没有则画第一个出现的指标;一个都没有则空态
  const chartMetric = metricKeys.includes('recall') ? 'recall' : metricKeys[0]
  const bucketData = Object.entries(run.by_bucket).map(([name, s]) => ({
    name,
    recall: chartMetric ? (s[chartMetric] ?? null) : null,
  }))
  const bucketRows = Object.entries(run.by_bucket).map(([name, s]) => ({ name, ...s }))

  return (
    <div>
      <h2>
        Run #{run.id} <Tag color="blue">{run.status}</Tag>
      </h2>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          {metricKeys.map((k) => (
            <MetricCard key={k} label={METRIC_LABELS[k] ?? k} value={run.scores[k]} />
          ))}
        </div>
      </Card>
      <Card title="分桶聚合" style={{ marginBottom: 16 }}>
        <BucketChart data={bucketData} />
        <Table
          rowKey="name"
          size="small"
          pagination={false}
          dataSource={bucketRows}
          columns={[
            { title: '分桶', dataIndex: 'name' },
            { title: '样本数', dataIndex: 'count' },
            ...metricKeys.map((k) => ({
              title: METRIC_LABELS[k] ?? k,
              dataIndex: k,
              render: fmt,
            })),
          ]}
        />
      </Card>
      <Card title="逐条明细">
        <Table
          rowKey="trace_id"
          dataSource={traces ?? []}
          columns={[
            { title: '问题', dataIndex: 'input' },
            { title: '回答', dataIndex: 'output' },
            {
              title: '证据',
              dataIndex: 'retrieval_hits',
              render: (hits?: { text: string; score: number; rank: number }[]) =>
                hits?.length
                  ? hits.map((h) => (
                      <div key={h.rank}>
                        <Tag color="blue">#{h.rank} 相似度 {h.score}</Tag> {h.text}
                      </div>
                    ))
                  : '—',
            },
            { title: '耗时', dataIndex: 'latency_ms', render: (v: number) => `${v}ms` },
            {
              title: '分数',
              dataIndex: 'scores',
              render: (scs: { name: string; value: number | null }[]) =>
                scs.map((s) => `${METRIC_LABELS[s.name] ?? s.name}=${s.value ?? '—'}`).join(' '),
            },
          ]}
        />
      </Card>
    </div>
  )
}
