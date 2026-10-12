import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Empty, Input, InputNumber, Modal, Result, Select, Skeleton, Space, Table, Tag, message } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import type { DatasetItem } from '../types'

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

  const add = async () => {
    if (!item.input.trim()) return // 问题为空时不允许提交,避免空白行
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

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Button onClick={() => nav('/datasets')}>← 返回评测集</Button>
      <h2>{ds?.name ?? `评测集 #${id}`}</h2>
      {/* 两行布局(Ch23):问题用多行输入框——单行输入长问题会水平滚动,看不到前面写了什么。
          换行才解决可见性(限长不解决);期望要点/分桶内容短,保持单行避免整块过高。 */}
      <div>
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
        <Space wrap>
          <Input
            placeholder="期望要点(用/分隔)"
            value={item.expected_output}
            style={{ width: 280 }}
            onChange={(e) => setItem({ ...item, expected_output: e.target.value })}
          />
          <Select
            placeholder="分桶"
            value={item.bucket || undefined}
            style={{ width: 120 }}
            options={['护理', '喂养', '睡眠', '库外'].map((b) => ({ value: b, label: b }))}
            onChange={(v) => setItem({ ...item, bucket: v })}
          />
          <Button type="primary" disabled={!item.input.trim()} onClick={add}>
            加样本
          </Button>
        </Space>
      </div>
      {!items?.length ? (
        <Empty description="还没有样本" />
      ) : (
        <Table
          rowKey="id"
          dataSource={items}
          columns={[
            { title: '问题', dataIndex: 'input' },
            { title: '期望要点', dataIndex: 'expected_output' },
            { title: '分桶', dataIndex: 'bucket' },
            {
              title: '金标准',
              dataIndex: 'gold_scores',
              render: (g?: Record<string, number> | null) =>
                g && Object.keys(g).length
                  ? Object.entries(g).map(([k, v]) => (
                      <Tag key={k} color="gold">
                        {GOLD_METRICS.find((m) => m.key === k)?.label ?? k}={v}
                      </Tag>
                    ))
                  : '—',
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
        onOk={saveGold}
        onCancel={() => setGoldItem(null)}
      >
        {GOLD_METRICS.map((m) => (
          <div key={m.key} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ width: 100 }}>{m.label}</span>
            <InputNumber
              min={0}
              max={1}
              step={0.05}
              value={goldScores[m.key]}
              onChange={(v) => setGoldScores((prev) => ({ ...prev, [m.key]: v ?? 0 }))}
              style={{ width: 140 }}
            />
          </div>
        ))}
      </Modal>
    </Space>
  )
}
