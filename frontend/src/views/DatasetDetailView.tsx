import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Empty, Input, Result, Select, Skeleton, Space, Table, message } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'

export default function DatasetDetailView() {
  const { datasetId } = useParams()
  const id = Number(datasetId)
  const nav = useNavigate()
  const { data: ds, loading, error, reload } = useRequest((s) => api.getDataset(id, s), [id])
  const { data: items, reload: reloadItems } = useRequest((s) => api.listItems(id, s), [id])
  const [item, setItem] = useState({ input: '', expected_output: '', bucket: '' })

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

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Button onClick={() => nav('/datasets')}>← 返回评测集</Button>
      <h2>{ds?.name ?? `评测集 #${id}`}</h2>
      <Space>
        <Input
          placeholder="问题"
          value={item.input}
          onChange={(e) => setItem({ ...item, input: e.target.value })}
        />
        <Input
          placeholder="期望要点(用/分隔)"
          value={item.expected_output}
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
          ]}
        />
      )}
    </Space>
  )
}
