import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button, Card, Descriptions, Result, Select, Skeleton, Table, Tag } from 'antd'
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

// 复现上下文快照(Ch09):config 里系统快照字段的形态
type Snapshot = {
  top_k?: number
  knowledge_version?: string
  knowledge_hash?: string
  prompt_version?: string
  chat_model?: string
  embed_model?: string
  dataset_hash?: string
  item_count?: number
}

export default function RunDetailView() {
  const { runId } = useParams()
  const id = Number(runId)
  const { data: run, loading, error, reload } = useRequest((s) => api.getRun(id, s), [id])
  const { data: traces } = useRequest((s) => api.listTraces(id, s), [id])
  const [chartMetric, setChartMetric] = useState<string | null>(null)

  // 复现上下文:解析 config 快照;老 run 缺字段显示 —
  const cfg = useMemo<Snapshot>(() => {
    try { return JSON.parse(run?.config || '{}') }
    catch { return {} }
  }, [run?.config])
  const short = (v?: string) => (v ? v.slice(0, 8) : '—')

  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />
  if (error)
    return (
      <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
    )
  if (!run) return null

  const metricKeys = Object.keys(run.scores)
  // 柱状图指标:用户选过且当前 run 有 → 尊重选择;否则默认 recall,没有则第一个(与 Ch05 回退一致)
  const effective = chartMetric && metricKeys.includes(chartMetric)
    ? chartMetric
    : metricKeys.includes('recall') ? 'recall' : metricKeys[0]
  const bucketData = Object.entries(run.by_bucket).map(([name, s]) => ({
    name,
    value: effective ? (s[effective] ?? null) : null,
  }))
  const bucketRows = Object.entries(run.by_bucket).map(([name, s]) => ({ name, ...s }))

  return (
    <div>
      <h2>
        Run #{run.id} <Tag color="blue">{run.status}</Tag>
      </h2>
      <Card title="复现上下文" style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="top_k">{cfg.top_k ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="知识库版本">{cfg.knowledge_version ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="知识库哈希">{short(cfg.knowledge_hash)}</Descriptions.Item>
          <Descriptions.Item label="Prompt 版本">{cfg.prompt_version ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="生成模型">{cfg.chat_model || '—'}</Descriptions.Item>
          <Descriptions.Item label="Embedding 模型">{cfg.embed_model || '—'}</Descriptions.Item>
          <Descriptions.Item label="数据集哈希">{short(cfg.dataset_hash)}</Descriptions.Item>
          <Descriptions.Item label="样本数">{cfg.item_count ?? '—'}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          {metricKeys.map((k) => (
            <MetricCard key={k} label={METRIC_LABELS[k] ?? k} value={run.scores[k]} />
          ))}
        </div>
      </Card>
      <Card
        title="分桶聚合"
        extra={
          <Select
            size="small"
            style={{ width: 180 }}
            value={effective}
            onChange={setChartMetric}
            options={metricKeys.map((k) => ({ value: k, label: METRIC_LABELS[k] ?? k }))}
          />
        }
        style={{ marginBottom: 16 }}
      >
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
