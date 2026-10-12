import { useMemo, useState } from 'react'
import { Button, Empty, Result, Select, Skeleton } from 'antd'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'

// 指标 key → 中文标签(与 RunDetailView / CompareView 一致)
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

const METRIC_KEYS = Object.keys(METRIC_LABELS)

export default function TrendView() {
  const [metric, setMetric] = useState('faithfulness')
  const [datasetId, setDatasetId] = useState<number | null>(null)
  const { data: trend, loading, error, reload } = useRequest(
    (s) => api.listRunsTrend(datasetId ?? undefined, s),
    [datasetId],
  )
  // 评测集下拉选项:从全部 run 里推出「用过哪些评测集」(不受当前筛选影响)
  const { data: allRuns } = useRequest((s) => api.listRuns(s), [])
  const datasetOptions = useMemo(() => {
    const seen = new Map<number, string>()
    for (const r of allRuns ?? []) {
      if (!seen.has(r.dataset_id)) seen.set(r.dataset_id, r.dataset_name ?? `评测集 #${r.dataset_id}`)
    }
    return [...seen.entries()].map(([id, name]) => ({ value: id, label: name }))
  }, [allRuns])

  // 只画「已完成且评过该指标」的 run,按时间正序(后端已倒序反转)
  const points = useMemo(() => {
    return (trend ?? [])
      .filter((r) => r.status === 'done' && r.scores[metric] != null)
      .map((r) => ({
        name: `Run #${r.id}`,
        value: r.scores[metric] as number,
        dataset: r.dataset_name ?? '',
        time: r.created_at ?? '',
      }))
  }, [trend, metric])

  if (loading) return <Skeleton active paragraph={{ rows: 6 }} />
  if (error)
    return <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />

  return (
    <div>
      <h2>历史指标趋势</h2>
      <Select
        value={metric}
        onChange={setMetric}
        style={{ width: 200, marginBottom: 16 }}
        options={METRIC_KEYS.map((k) => ({ value: k, label: METRIC_LABELS[k] }))}
      />
      <Select
        value={datasetId ?? undefined}
        onChange={(v) => setDatasetId(v ?? null)}
        style={{ width: 200, marginLeft: 8, marginBottom: 16 }}
        placeholder="全部评测集"
        allowClear
        options={datasetOptions}
      />
      {points.length === 0 ? (
        <Empty description={`暂无「${METRIC_LABELS[metric]}」的趋势数据(至少两个完成且评过该指标的 run)`} style={{ marginTop: 40 }} />
      ) : (
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={points} margin={{ top: 8, right: 24, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis domain={[0, 1]} />
            {/* 轴空间有限只放短标签;评测集名(中文)/时间放 tooltip,悬停才看 */}
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const p = payload[0].payload as { name: string; value: number; dataset: string; time: string }
                return (
                  <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 6, padding: 8, fontSize: 12 }}>
                    <div style={{ fontWeight: 600 }}>
                      {p.name}
                      {p.dataset ? ` · ${p.dataset}` : ''}
                    </div>
                    {p.time && <div style={{ color: '#888' }}>{p.time.replace('T', ' ')}</div>}
                    <div>
                      {METRIC_LABELS[metric]}: {p.value.toFixed(4)}
                    </div>
                  </div>
                )
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 4 }}
              name={METRIC_LABELS[metric]}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
