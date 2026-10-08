import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Result, Select, Skeleton, Space, Table, Tag } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import type { Run } from '../types'

const STATUS: Record<string, { color: string; text: string }> = {
  running: { color: 'gold', text: '运行中' },
  done: { color: 'green', text: '完成' },
  failed: { color: 'red', text: '失败' },
}

export default function RunsView() {
  const nav = useNavigate()
  const { data: datasets } = useRequest((s) => api.listDatasets(s))
  const { data: runs, loading, error, reload } = useRequest((s) => api.listRuns(s))
  const [sel, setSel] = useState<number | null>(null)

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
    await api.createRun(sel)
    reload()
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Space>
        <Select
          placeholder="选评测集"
          style={{ width: 240 }}
          value={sel ?? undefined}
          options={(datasets ?? []).map((d) => ({
            value: d.id,
            label: (d.item_count ?? 0) === 0 ? `${d.name}(空)` : d.name,
            disabled: (d.item_count ?? 0) === 0, // 空评测集发起评测没意义,置灰
          }))}
          onChange={setSel}
        />
        <Button type="primary" disabled={sel === null} onClick={start}>
          发起评测
        </Button>
      </Space>
      <Table
        rowKey="id"
        dataSource={runs ?? []}
        columns={[
          { title: 'ID', dataIndex: 'id' },
          { title: '评测集', dataIndex: 'dataset_name' },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s: string) => <Tag color={STATUS[s]?.color}>{STATUS[s]?.text ?? s}</Tag>,
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
