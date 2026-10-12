import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card, Descriptions, Result, Select, Skeleton, Space, Table, Tag, message } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import { useRunCompletionNotice } from '../hooks/useRunCompletionNotice'
import type { BucketAttribution, GateCheck, TraceRow } from '../types'
import MetricCard from '../components/MetricCard'
import BucketChart from '../components/BucketChart'

const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(4))

// 指标 key → 中文标签(后端只认 key,展示文案放前端)
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

// 复现上下文快照(Ch09):config 里系统快照字段的形态
type Snapshot = {
  top_k?: number
  retrieval?: string  // Ch16:dense | hybrid
  knowledge_version?: string
  knowledge_hash?: string
  pipeline_prompt_version?: string  // Ch19:生成 prompt 版本
  judge_prompt_version?: string     // Ch19:judge prompt 版本
  chat_model?: string
  embed_model?: string
  dataset_hash?: string
  item_count?: number
}

export default function RunDetailView() {
  const { runId } = useParams()
  const id = Number(runId)
  const nav = useNavigate()
  const { data: run, loading, error, reload } = useRequest((s) => api.getRun(id, s), [id])
  const { data: traces, reload: reloadTraces } = useRequest((s) => api.listTraces(id, s), [id])
  const [chartMetric, setChartMetric] = useState<string | null>(null)

  // 回归门禁(Ch15):基线选择 + 门禁结果;默认基线 = 最近一个非本 run 的 done run
  const [baselineId, setBaselineId] = useState<number | null>(null)
  const baselineInit = useRef(false)
  const { data: runList } = useRequest((s) => api.listRuns(s), [])
  const { data: gate, loading: gateLoading } = useRequest(
    (s) => api.getRunGate(id, baselineId ?? undefined, s),
    [id, baselineId],
  )
  const { data: calibration } = useRequest((s) => api.getRunCalibration(id, s), [id])
  const { data: bucketAttr } = useRequest(
    (s) => (baselineId != null ? api.getBucketAttribution(id, baselineId, s) : Promise.resolve(null)),
    [id, baselineId],
  )

  useEffect(() => {
    if (baselineInit.current || !runList?.length) return
    const prev = runList.find((r) => r.status === 'done' && r.id !== id)
    if (prev) setBaselineId(prev.id)
    baselineInit.current = true // 只自动选一次,之后尊重用户手动改
  }, [runList, id])

  // 运行中轮询(与列表页一致):进度/状态/逐条明细实时刷新,run 变 done/failed 自动停
  useEffect(() => {
    if (run?.status !== 'running') return
    const t = setInterval(() => {
      reload()
      reloadTraces()
    }, 1500)
    return () => clearInterval(t)
  }, [run?.status, reload, reloadTraces])

  // 本 run 完成/失败时飘一条通知(详情页停留在页面上也能感知)
  useRunCompletionNotice(run ? [run] : [])

  // 导出 CSV(Ch13):带鉴权头走 axios 拉文本,再 Blob 触发浏览器下载
  const exportCsv = async () => {
    try {
      const csv = await api.exportRunCsv(id)
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `run_${id}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '导出失败')
    }
  }

  // 复现上下文:解析 config 快照;老 run 缺字段显示 —
  const cfg = useMemo<Snapshot>(() => {
    try { return JSON.parse(run?.config || '{}') }
    catch { return {} }
  }, [run?.config])
  const short = (v?: string) => (v ? v.slice(0, 8) : '—')

  // 只在「首次加载、还没有数据」时显示骨架:否则轮询每次刷新都会整页闪成骨架屏
  if (loading && !run) return <Skeleton active paragraph={{ rows: 8 }} />
  if (error)
    return (
      <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
    )
  if (!run) return null

  // 一键复跑(Ch20):按快照的 top_k + retrieval 重新发起同配置 run
  const rerun = async () => {
    try {
      const res = await api.createRun(run.dataset_id, {
        top_k: cfg.top_k ?? 2,
        retrieval: cfg.retrieval === 'dense' ? 'dense' : 'hybrid',
      })
      message.success(`已发起复跑 Run #${res.id}`)
      nav(`/runs/${res.id}`)
    } catch (e) {
      message.error(e instanceof Error ? e.message : '复跑失败')
    }
  }

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>
          Run #{run.id} <Tag color="blue">{run.status}</Tag>
          {run.status === 'running' && (
            <span style={{ fontSize: 14, marginLeft: 8 }}>
              进度 {run.progress ?? 0}/{cfg.item_count ?? '—'}
            </span>
          )}
        </h2>
        <Space>
          <Button onClick={rerun}>一键复跑</Button>
          <Button onClick={exportCsv}>导出 CSV</Button>
        </Space>
      </div>
      <Card
        title="回归门禁"
        extra={
          <Select
            size="small"
            style={{ width: 240 }}
            value={baselineId ?? undefined}
            placeholder="选择基线 run"
            allowClear
            onChange={(v) => setBaselineId(v ?? null)}
            options={(runList ?? []).map((r) => ({
              value: r.id,
              label: `Run #${r.id} (${r.status})${r.dataset_name ? ' · ' + r.dataset_name : ''}`,
            }))}
          />
        }
        style={{ marginBottom: 16 }}
      >
        {gateLoading && !gate ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : gate ? (
          <>
            <div style={{ marginBottom: 12 }}>
              <Tag color={gate.passed ? 'green' : 'red'} style={{ fontSize: 14, padding: '2px 10px' }}>
                {gate.passed ? 'PASS 通过' : 'FAIL 不通过'}
              </Tag>
              {gate.baseline_run_id != null && (
                <span style={{ marginLeft: 8, color: '#888' }}>对比基线 Run #{gate.baseline_run_id}</span>
              )}
            </div>
            <Table<GateCheck>
              rowKey="metric"
              size="small"
              pagination={false}
              dataSource={gate.checks}
              columns={[
                { title: '指标', dataIndex: 'metric', render: (m: string) => METRIC_LABELS[m] ?? m },
                { title: '当前值', dataIndex: 'value', render: fmt },
                { title: '阈值(≥)', dataIndex: 'threshold' },
                { title: '基线值', dataIndex: 'baseline_value', render: (v: number | null) => (v == null ? '—' : v.toFixed(4)) },
                { title: '变化', dataIndex: 'delta', render: (d: number | null) => (d == null ? '—' : (d >= 0 ? '+' : '') + d.toFixed(4)) },
                {
                  title: '判定',
                  dataIndex: 'passed',
                  render: (p: boolean, rec: GateCheck) => (
                    <Tag color={p ? 'green' : 'red'}>{p ? '通过' : rec.note ?? '不通过'}</Tag>
                  ),
                },
              ]}
            />
          </>
        ) : null}
      </Card>
      {bucketAttr && bucketAttr.buckets.length > 0 && (
        <Card title={`分桶归因(相对基线 Run #${bucketAttr.baseline_run_id})`} style={{ marginBottom: 16 }}>
          <Table
            rowKey="bucket"
            size="small"
            pagination={false}
            dataSource={bucketAttr.buckets}
            columns={[
              { title: '分桶', dataIndex: 'bucket' },
              { title: '样本数', dataIndex: 'count' },
              ...metricKeys.map((m) => ({
                title: METRIC_LABELS[m] ?? m,
                key: m,
                render: (_: unknown, rec: BucketAttribution) => {
                  const d = rec.deltas[m]
                  return d == null ? '—' : <Tag color={d >= 0 ? 'green' : 'red'}>{(d >= 0 ? '+' : '') + d.toFixed(4)}</Tag>
                },
              })),
            ]}
          />
        </Card>
      )}
      <Card title="费用统计" style={{ marginBottom: 16 }}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="输入 Token">{run.input_tokens ?? 0}</Descriptions.Item>
          <Descriptions.Item label="输出 Token">{run.output_tokens ?? 0}</Descriptions.Item>
          <Descriptions.Item label="总费用(元)">
            {run.cost === undefined ? '—' : run.cost.toFixed(6)}
          </Descriptions.Item>
          <Descriptions.Item label="单条平均成本(元)">
            {run.cost === undefined || !run.item_count ? '—' : (run.cost / run.item_count).toFixed(6)}
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="复现上下文" style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="top_k">{cfg.top_k ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="检索方式">
            {cfg.retrieval === 'hybrid' ? '混合检索(dense+BM25)' : cfg.retrieval === 'dense' ? '纯向量' : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="知识库版本">{cfg.knowledge_version ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="知识库哈希">{short(cfg.knowledge_hash)}</Descriptions.Item>
          <Descriptions.Item label="Pipeline Prompt 版本">{cfg.pipeline_prompt_version ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="Judge Prompt 版本">{cfg.judge_prompt_version ?? '—'}</Descriptions.Item>
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
      {calibration && Object.keys(calibration.metrics).length > 0 && (
        <Card title="Judge 校准(judge vs 金标准)" style={{ marginBottom: 16 }}>
          <Table
            rowKey="metric"
            size="small"
            pagination={false}
            dataSource={Object.entries(calibration.metrics).map(([m, v]) => ({ metric: m, ...v }))}
            columns={[
              { title: '指标', dataIndex: 'metric', render: (m: string) => METRIC_LABELS[m] ?? m },
              {
                title: 'Bias(偏松/偏严)',
                dataIndex: 'bias',
                render: (v: number | null) => (v == null ? '—' : (v > 0 ? '+' : '') + v.toFixed(4)),
              },
              { title: 'MAE', dataIndex: 'mae', render: (v: number | null) => (v == null ? '—' : v.toFixed(4)) },
              { title: 'Pearson', dataIndex: 'corr', render: (v: number | null) => (v == null ? '—' : v.toFixed(4)) },
              { title: '样本数', dataIndex: 'n' },
            ]}
          />
        </Card>
      )}
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
          expandable={{
            // Ch18:展开行看完整链路——证据上下文 + 各 Judge 的 score/reason(可解释性)
            expandedRowRender: (rec: TraceRow) => (
              <div style={{ padding: '8px 16px', background: '#fafafa' }}>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ fontWeight: 600 }}>证据上下文：</span>
                  <span style={{ color: '#444' }}>{rec.retrieved_context || '—'}</span>
                </div>
                <div>
                  <span style={{ fontWeight: 600 }}>Judge 打分：</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 4 }}>
                    {rec.scores.map((s) => (
                      <div
                        key={s.name}
                        style={{ minWidth: 220, flex: 1, border: '1px solid #eee', borderRadius: 6, padding: 8 }}
                      >
                        <div>
                          <Tag color="blue">{METRIC_LABELS[s.name] ?? s.name}</Tag>
                          <span style={{ fontWeight: 600 }}>{s.value ?? '—'}</span>
                          {s.variance != null && (
                            <span style={{ color: '#999', fontSize: 12, marginLeft: 6 }}>
                              方差 {s.variance.toFixed(6)}
                            </span>
                          )}
                        </div>
                        {s.comment ? (
                          <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>{s.comment}</div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ),
          }}
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
                        <Tag color="blue">#{h.rank} 融合分 {h.score}</Tag> {h.text}
                      </div>
                    ))
                  : '—',
            },
            { title: '耗时', dataIndex: 'latency_ms', render: (v: number) => `${v}ms` },
            {
              title: '分数',
              dataIndex: 'scores',
              render: (scs: { name: string; value: number | null; comment?: string }[]) =>
                scs.map((s) => `${METRIC_LABELS[s.name] ?? s.name}=${s.value ?? '—'}`).join(' '),
            },
          ]}
        />
      </Card>
    </div>
  )
}
