import { Empty } from 'antd'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function BucketChart({ data }: { data: { name: string; recall: number | null }[] }) {
  // 没有任何可绘制的值(空桶 / 全是 NULL)时不渲染图表,否则 hover 会画出越界的深色区域
  if (!data.some((d) => d.recall !== null)) {
    return <Empty description="暂无分桶数据" style={{ margin: '0 auto' }} />
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis domain={[0, 1]} />
        <Tooltip />
        <Bar dataKey="recall" fill="#3b82f6" />
      </BarChart>
    </ResponsiveContainer>
  )
}
