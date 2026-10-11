import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Empty, Input, Modal, Result, Skeleton, Space, Table, message } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import type { Dataset } from '../types'

export default function DatasetsView() {
  const nav = useNavigate()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const { data, loading, error, reload } = useRequest(
    (s) => api.listDatasets({ page, page_size: pageSize }, s),
    [page, pageSize],
  )
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')

  if (error)
    return (
      <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
    )
  if (loading && !data) return <Skeleton active paragraph={{ rows: 6 }} />

  const create = async () => {
    if (!name.trim()) return // 名称为空不允许新建
    await api.createDataset(name.trim(), desc)
    setOpen(false)
    setName('')
    setDesc('')
    message.success('已创建')
    setPage(1) // 新建的 updated_at 最新,排第一页;回第一页能看到
    if (page === 1) reload() // 已在第一页时 setPage 不触发重载,手动刷新
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      {/* 按钮始终渲染:空库时也不能挡住首次「新建评测集」入口(曾因 Empty 提前 return 被隐藏) */}
      <Button type="primary" onClick={() => setOpen(true)}>
        新建评测集
      </Button>
      {!data?.items.length ? (
        <Empty description="还没有评测集" />
      ) : (
        <Table
          rowKey="id"
          loading={loading}
          dataSource={data.items}
          pagination={{
            current: page,
            pageSize,
            total: data.total,
            showSizeChanger: true,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
            },
          }}
          columns={[
            { title: '名称', dataIndex: 'name' },
            { title: '描述', dataIndex: 'description' },
            { title: '样本数', dataIndex: 'item_count' },
            {
              title: '操作',
              key: 'action',
              render: (_: unknown, d: Dataset) => (
                <Button type="link" size="small" onClick={() => nav(`/datasets/${d.id}`)}>
                  查看
                </Button>
              ),
            },
          ]}
        />
      )}
      <Modal
        open={open}
        title="新建评测集"
        onOk={create}
        okButtonProps={{ disabled: !name.trim() }}
        onCancel={() => setOpen(false)}
      >
        <Input placeholder="名称" value={name} onChange={(e) => setName(e.target.value)} style={{ marginBottom: 12 }} />
        <Input.TextArea placeholder="描述" value={desc} onChange={(e) => setDesc(e.target.value)} />
      </Modal>
    </Space>
  )
}
