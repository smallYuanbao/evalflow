import { Button, Result, Skeleton } from 'antd'
import { api } from '../api'
import { useRequest } from '../hooks/useRequest'
import EmbeddingScatter from '../components/EmbeddingScatter'

export default function KnowledgeMapView() {
  const { data, loading, error, reload } = useRequest((s) => api.getKnowledgeMap(s))
  if (loading) return <Skeleton active paragraph={{ rows: 8 }} />
  if (error)
    return (
      <Result status="error" title="加载失败" subTitle={error} extra={<Button onClick={reload}>重试</Button>} />
    )
  return <EmbeddingScatter chunks={data?.chunks ?? []} queries={data?.queries ?? []} />
}
