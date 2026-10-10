import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, InputNumber, Result, Select, Skeleton, Space, Table, Tag } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import type { Run } from '../types'

const STATUS: Record<string, { color: string; text: string }> = {
  running: { color: 'gold', text: '运行中' },
  done: { color: 'green', text: '完成' },
  failed: { color: 'red', text: '失败' },
}

// 配置快照 → 一行可读标签(只有 top_k 值得回看时才有值)
function configLabel(config?: string): string {
  if (!config) return '—'
  try {
    const cfg = JSON.parse(config)
    return cfg.top_k != null ? `top_k=${cfg.top_k}` : '—'
  } catch {
    return config
  }
}

export default function RunsView() {
  const nav = useNavigate()
  const [kw, setKw] = useState('')
  const { data: datasets } = useRequest((s) => api.listDatasets({ page: 1, page_size: 20, search: kw }, s), [kw])
  const { data: runs, loading, error, reload } = useRequest((s) => api.listRuns(s))
  const [sel, setSel] = useState<number | null>(null)
  const [topK, setTopK] = useState(2)
  const [selected, setSelected] = useState<number[]>([])

  useEffect(() => {
    const hasRunning = runs?.some((r) => r.status === 'running')
    if (!hasRunning) return
    const t = setInterval(reload, 1500)
    return () => clearInterval(t)
  }, [runs, reload])

  if (loading) return <Skeleton active paragraph={{ rows: 6 }} />
  if (error)
    return (
      <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
    )

  const start = async () => {
    if (sel === null) return
    await api.createRun(sel, { top_k: topK })
    reload()
  }

  const compare = () => nav(`/compare?ids=${selected.join(',')}`)

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space wrap>
        <Select
          showSearch
          onSearch={setKw}
          filterOption={false} // 交给后端按名称模糊过滤,不用前端 filterOption
          placeholder="选评测集"
          style={{ width: 240 }}
          value={sel ?? undefined}
          options={(datasets?.items ?? []).map((d) => ({
            value: d.id,
            label: (d.item_count ?? 0) === 0 ? `${d.name}(空)` : d.name,
            disabled: (d.item_count ?? 0) === 0, // 空评测集发起评测没意义,置灰
          }))}
          onChange={setSel}
        />
        <InputNumber min={1} max={10} value={topK} onChange={(v) => setTopK(v ?? 2)} addonBefore="top_k" />
        <Button type="primary" disabled={sel === null} onClick={start}>
          发起评测
        </Button>
        <Button disabled={selected.length < 2} onClick={compare}>
          对比({selected.length})
        </Button>
      </Space>
      <Table
        rowKey="id"
        dataSource={runs ?? []}
        rowSelection={{ selectedRowKeys: selected, onChange: (keys) => setSelected(keys as number[]) }}
        columns={[
          { title: 'ID', dataIndex: 'id' },
          { title: '评测集', dataIndex: 'dataset_name' },
          { title: '配置', dataIndex: 'config', render: configLabel },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s: string, r: Run) => (
              <Space size={4}>
                <Tag color={STATUS[s]?.color}>{STATUS[s]?.text ?? s}</Tag>
                {s === 'running' && r.progress != null && <span>已完成 {r.progress} 条</span>}
              </Space>
            ),
          },
          { title: '时间', dataIndex: 'created_at' },
          {
            title: '操作',
            key: 'action',
            render: (_: unknown, r: Run) => (
              <Button type="link" size="small" onClick={() => nav(`/runs/${r.id}`)}>
                查看
              </Button>
            ),
          },
        ]}
      />
    </Space>
  )
}
