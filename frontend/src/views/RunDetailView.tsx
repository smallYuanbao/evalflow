import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Alert, Button, Card, Descriptions, Result, Select, Skeleton, Space, Table, Tag, Tooltip, message } from 'antd'
import { api } from '../api'
import { exportRunCsvUrl } from '../api/client'
import { useRequest } from '../hooks/useRequest'
import { useRunCompletionNotice } from '../hooks/useRunCompletionNotice'
import type { BucketAttribution, GateCheck, TraceRow } from '../types'
import MetricCard from '../components/MetricCard'
import BucketChart from '../components/BucketChart'
import { metricDesc, metricLabel, METRIC_LABELS } from '../utils/metrics'

const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(4))


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
  // Ch26:被测系统(外部)的状态
  external?: {
    target: string
    base_url?: string
    meta?: {
      service?: string
      commit?: string | null
      model?: string
      embed_model?: string
      query_rewrite?: boolean
      collections?: Record<string, number | null>
    } | null
    meta_error?: string | null
  }
}

export default function RunDetailView() {
  const { runId } = useParams()
  const id = Number(runId)
  const nav = useNavigate()
  const { data: run, loading, error, reload } = useRequest((s) => api.getRun(id, s), [id])
  const { data: traces, reload: reloadTraces } = useRequest((s) => api.listTraces(id, s), [id])
  const [chartMetric, setChartMetric] = useState<string | null>(null)

  // 回归门禁(Ch15):基线选择 + 门禁结果。
  // 区分两个来源(Ch24):URL 里的 = 用户显式选的(可分享);autoBaseline = 自动挑的默认值。
  // 只有显式选择才写 URL——否则光是打开一个 run 页,URL 就被塞上 ?baseline=,用户没选任何东西却看到地址变了。
  const [searchParams, setSearchParams] = useSearchParams()
  const urlBaseline = searchParams.get('baseline')
  const [autoBaseline, setAutoBaseline] = useState<number | null>(null)
  const baselineId = urlBaseline != null ? Number(urlBaseline) : autoBaseline
  const setBaselineId = (bid: number | null) => {
    const next = new URLSearchParams(searchParams)
    if (bid == null) next.delete('baseline')
    else next.set('baseline', String(bid))
    setSearchParams(next, { replace: true })
  }
  // 用户在 select 里动手:以后不再用自动默认,并把选择写进 URL
  const chooseBaseline = (bid: number | null) => {
    setAutoBaseline(null)
    setBaselineId(bid)
  }
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
    baselineInit.current = true // 只自动选一次,之后尊重用户手动改
    if (urlBaseline != null) return // URL 里已经指定(分享链接),不覆盖
    // 默认基线 = 「紧邻的上一次」(id 比当前小里最大的那个):
    // 语义是「这次比上次改得怎么样」。取最新那个是错的——看最老的 run 会拿最新的当基线。
    // runList 本身按 id 倒序,find 第一个满足 id<当前 的就是紧邻的上一次;没有(自己是最老的)就不设。
    const prev = runList.find((r) => r.status === 'done' && r.id < id)
    if (prev) setAutoBaseline(prev.id) // 只设内存默认,不碰 URL
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  // 导出 CSV(Ch25):交给浏览器原生下载——流式落盘、自带进度条和取消,全程不占 JS 内存。
  // 之前是「axios 拉完整字符串 → new Blob → createObjectURL」,整份文件要在 JS 里存 2~3 份,
  // 样本上万就会卡死/爆内存。后端也同步改成了 StreamingResponse,两端都不再缓冲整份文件。
  const exportCsv = () => {
    const a = document.createElement('a')
    a.href = exportRunCsvUrl(id) // 响应带 Content-Disposition: attachment,不会跳走页面
    a.click()
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
          <Tooltip title="用本次 run 的快照配置(top_k / 检索方式 / 数据集)重新发起一次评测,用来复现这次的跑法">
            <Button onClick={rerun}>一键复跑</Button>
          </Tooltip>
          <Tooltip
            title={
              <div>
                导出这次评测的<b>逐条明细</b>为 CSV(每行一条样本):
                <div style={{ marginTop: 4 }}>问题、回答、耗时(ms)、各指标分数</div>
                <div style={{ marginTop: 4, color: '#ddd' }}>适合丢进 Excel / Python 做外部分析</div>
              </div>
            }
          >
            <Button onClick={exportCsv}>导出 CSV</Button>
          </Tooltip>
        </Space>
      </div>
      <Card
        title="回归门禁"
        extra={
          // 必须有标签(Ch24):只显示一个「Run #4」会让人以为它是「当前查看的 run」,
          // 其实它是「拿谁当对比基准」——和当前页的 Run #5 是两回事。
          <Space size={6}>
            <span style={{ color: '#666' }}>对比基线</span>
            <Tooltip title="以哪个 run 作为基准来算「回归」。默认取紧邻的上一次;留空则只做绝对阈值判定。">
              <Select
                size="small"
                style={{ width: 220 }}
                value={baselineId ?? undefined}
                placeholder="不设基线"
                allowClear
                onChange={(v) => chooseBaseline(v ?? null)}
                options={(runList ?? []).map((r) => ({
                  value: r.id,
                  label: `Run #${r.id} (${r.status})${r.dataset_name ? ' · ' + r.dataset_name : ''}`,
                }))}
              />
            </Tooltip>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        {run.status === 'running' ? (
          // 评测没跑完时证据不全,判「不通过」是错的(实测空 scores → 全「未评」→ FAIL)。
          // 结论只在有完整数据时才有意义(Ch23)。
          <div style={{ color: '#888' }}>评测中…完成后给出门禁结论</div>
        ) : gateLoading && !gate ? (
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
                { title: '指标', dataIndex: 'metric', render: (m: string) => <Tooltip title={metricDesc(m)}><span style={{ cursor: 'help', borderBottom: '1px dashed #d9d9d9' }}>{metricLabel(m)}</span></Tooltip> },
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
      {/* 被测系统(Ch26):评外部系统时,复现性有一半在对方那边——这里记下它的状态,
          让「这次比上次好」有据可依。meta 拿不到时显式警示,而不是假装可复现。 */}
      {cfg.external && cfg.external.target !== 'local' && (
        <Card title="被测系统" style={{ marginBottom: 16 }}>
          {cfg.external.meta_error ? (
            <Alert
              type="warning"
              showIcon
              message="被测系统状态未知"
              description={`${cfg.external.meta_error}——本次结果**不可**与历史 run 对比。`}
            />
          ) : (
            <Descriptions column={2} size="small">
              <Descriptions.Item label="目标">{cfg.external.meta?.service ?? cfg.external.target}</Descriptions.Item>
              <Descriptions.Item label="地址">{cfg.external.base_url ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="代码版本">{cfg.external.meta?.commit ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="生成模型">{cfg.external.meta?.model ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="嵌入模型">{cfg.external.meta?.embed_model ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="查询改写">
                {cfg.external.meta?.query_rewrite == null ? '—' : cfg.external.meta.query_rewrite ? '开' : '关'}
              </Descriptions.Item>
              <Descriptions.Item label="知识库" span={2}>
                {cfg.external.meta?.collections
                  ? Object.entries(cfg.external.meta.collections)
                      .map(([k, v]) => `${k}=${v ?? '不存在'}`)
                      .join('  ')
                  : '—'}
              </Descriptions.Item>
            </Descriptions>
          )}
        </Card>
      )}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          {metricKeys.map((k) => (
            <MetricCard key={k} label={metricLabel(k)} value={run.scores[k]} desc={metricDesc(k)} />
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
              { title: '指标', dataIndex: 'metric', render: (m: string) => <Tooltip title={metricDesc(m)}><span style={{ cursor: 'help', borderBottom: '1px dashed #d9d9d9' }}>{metricLabel(m)}</span></Tooltip> },
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
                          <Tooltip title={metricDesc(s.name)}>
                            <Tag color="blue">{metricLabel(s.name)}</Tag>
                          </Tooltip>
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
