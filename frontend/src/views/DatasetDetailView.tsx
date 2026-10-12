import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Card, Empty, Input, InputNumber, Modal, Result, Select, Skeleton, Space, Table, Tag, Tooltip, message } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import type { DatasetItem } from '../types'

// 分桶释义(Ch24):「库外」不只是分组标签——它决定这条样本评「拒答」还是评 recall+judge
const BUCKET_DESC: Record<string, string> = {
  护理: '知识库里有答案的常规护理题',
  喂养: '知识库里有答案的喂养题',
  睡眠: '知识库里有答案的睡眠题',
  库外: '知识库里没有答案——正确行为是拒答,只评「拒答率」不评 recall/judge',
}

// 可标金标准的 5 个 judge 指标(Ch18 校准)
const GOLD_METRICS: { key: string; label: string }[] = [
  { key: 'context_precision', label: '上下文精度' },
  { key: 'context_recall', label: '上下文召回' },
  { key: 'faithfulness', label: '忠实度' },
  { key: 'answer_relevance', label: '答案相关性' },
  { key: 'answer_correctness', label: '答案正确性' },
]

export default function DatasetDetailView() {
  const { datasetId } = useParams()
  const id = Number(datasetId)
  const nav = useNavigate()
  const { data: ds, loading, error, reload } = useRequest((s) => api.getDataset(id, s), [id])
  const { data: items, reload: reloadItems } = useRequest((s) => api.listItems(id, s), [id])
  const [item, setItem] = useState({ input: '', expected_output: '', bucket: '' })
  const [goldItem, setGoldItem] = useState<DatasetItem | null>(null)
  const [goldScores, setGoldScores] = useState<Record<string, number>>({})

  if (loading) return <Skeleton active paragraph={{ rows: 6 }} />
  if (error)
    return (
      <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
    )

  // 问题必填、分桶必选:分桶为空会被当成「库内题」用 recall+judge 评,
  // 而库外题的正确行为是评「拒答」——分桶影响打分语义,不是可选的分组标签(Ch24)
  const canAdd = !!item.input.trim() && !!item.bucket

  const add = async () => {
    if (!canAdd) return
    await api.addItem(id, { ...item, input: item.input.trim() })
    setItem({ input: '', expected_output: '', bucket: '' })
    message.success('已添加')
    reloadItems()
  }

  const openGold = (it: DatasetItem) => {
    setGoldItem(it)
    setGoldScores(it.gold_scores ?? {})
  }

  const saveGold = async () => {
    if (!goldItem) return
    await api.setItemGold(id, goldItem.id, goldScores)
    setGoldItem(null)
    message.success('已标金标准')
    reloadItems()
  }

  // 清空金标准:写空对象即可(后端存的是 JSON,空对象 = 没有金标准)。Ch24 补,之前只能改不能删。
  const clearGold = async () => {
    if (!goldItem) return
    await api.setItemGold(id, goldItem.id, {})
    setGoldItem(null)
    setGoldScores({})
    message.success('已清空金标准')
    reloadItems()
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Button onClick={() => nav('/datasets')}>← 返回评测集</Button>
      <h2>{ds?.name ?? `评测集 #${id}`}</h2>
      {/* 两行布局(Ch23):问题用多行输入框——单行输入长问题会水平滚动,看不到前面写了什么。
          换行才解决可见性(限长不解决);期望要点/分桶内容短,保持单行避免整块过高。
          收进 Card + 限宽:表单填满 1280px 会和下方表格的比例严重失衡。 */}
      <Card title="加样本" size="small">
        <div style={{ maxWidth: 720 }}>
          <label htmlFor="item-input" style={{ display: 'block', marginBottom: 6, color: '#666' }}>
            问题 <span style={{ color: '#ff4d4f' }}>*</span>
          </label>
          <Input.TextArea
            id="item-input"
            placeholder="如:宝宝发烧38度怎么办"
            value={item.input}
            maxLength={200}
            showCount
            autoSize={{ minRows: 2, maxRows: 5 }}
            onChange={(e) => setItem({ ...item, input: e.target.value })}
            style={{ marginBottom: 12 }}
          />
          {/* 期望要点也用多行:单行输入内容一长就水平滚动,看不到前面写了什么(Ch24) */}
          <label htmlFor="item-expected" style={{ display: 'block', marginBottom: 6, color: '#666' }}>
            期望要点(用 / 分隔)
          </label>
          <Input.TextArea
            id="item-expected"
            placeholder="如:物理降温/就医/用药"
            value={item.expected_output}
            maxLength={200}
            showCount
            autoSize={{ minRows: 1, maxRows: 3 }}
            onChange={(e) => setItem({ ...item, expected_output: e.target.value })}
            style={{ marginBottom: 26 }} // showCount 的计数挂在框下方 22px,留位避免压到下一行
          />
          <Space wrap>
            <Select
              placeholder="分桶(必选)"
              status={item.bucket ? undefined : 'warning'}
              value={item.bucket || undefined}
              style={{ width: 160 }}
              options={['护理', '喂养', '睡眠', '库外'].map((b) => ({ value: b, label: b }))}
              onChange={(v) => setItem({ ...item, bucket: v })}
            />
            <Button type="primary" disabled={!canAdd} onClick={add}>
              加样本
            </Button>
            {!item.bucket && item.input.trim() && (
              <span style={{ color: '#d48806', fontSize: 12 }}>请选择分桶(影响打分方式)</span>
            )}
          </Space>
        </div>
      </Card>
      {!items?.length ? (
        <Empty description="还没有样本" />
      ) : (
        <Table
          rowKey="id"
          dataSource={items}
          columns={[
            { title: '问题', dataIndex: 'input' },
            { title: '期望要点', dataIndex: 'expected_output' },
            {
              title: '分桶',
              dataIndex: 'bucket',
              render: (b: string) => (
                <Tooltip title={BUCKET_DESC[b] ?? '用于分组归因'}>
                  <span style={{ cursor: 'help', borderBottom: '1px dashed #d9d9d9' }}>{b || '未分桶'}</span>
                </Tooltip>
              ),
            },
            {
              title: '金标准',
              dataIndex: 'gold_scores',
              render: (g?: Record<string, number> | null) =>
                g && Object.keys(g).length ? (
                  <Tooltip title="人工判断的分数,用于校验 LLM 裁判准不准(见 Run 详情页的「Judge 校准」)">
                    <span>
                      {Object.entries(g).map(([k, v]) => (
                        <Tag key={k} color="gold">
                          {GOLD_METRICS.find((m) => m.key === k)?.label ?? k}={v}
                        </Tag>
                      ))}
                    </span>
                  </Tooltip>
                ) : (
                  '—'
                ),
            },
            {
              title: '操作',
              key: 'action',
              render: (_: unknown, it: DatasetItem) => (
                <Button type="link" size="small" onClick={() => openGold(it)}>
                  标金标准
                </Button>
              ),
            },
          ]}
        />
      )}
      <Modal
        open={goldItem != null}
        title={`标金标准 — ${goldItem?.input ?? ''}`}
        onCancel={() => setGoldItem(null)}
        footer={[
          <Button
            key="clear"
            danger
            disabled={!Object.keys(goldScores).length}
            onClick={clearGold}
          >
            清空金标准
          </Button>,
          <Button key="cancel" onClick={() => setGoldItem(null)}>
            取消
          </Button>,
          <Button key="save" type="primary" onClick={saveGold}>
            保存
          </Button>,
        ]}
      >
        <p style={{ color: '#888', marginTop: 0 }}>
          填人工判断的分数(0~1),用来校验 LLM 裁判准不准。留空的指标视为「没标」。
        </p>
        {GOLD_METRICS.map((m) => (
          <div key={m.key} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ width: 100 }}>{m.label}</span>
            <InputNumber
              min={0}
              max={1}
              step={0.05}
              value={goldScores[m.key]}
              // 清空单个输入框 = 移除该指标的金标准(之前会写成 0,等于「人工判它零分」,语义不同)
              onChange={(v) =>
                setGoldScores((prev) => {
                  const next = { ...prev }
                  if (v == null) delete next[m.key]
                  else next[m.key] = v
                  return next
                })
              }
              style={{ width: 140 }}
            />
          </div>
        ))}
      </Modal>
    </Space>
  )
}
