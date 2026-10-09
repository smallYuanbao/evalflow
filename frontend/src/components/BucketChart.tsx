import { Empty } from 'antd'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// 通用分桶柱状图:value 是「当前选中的指标」在该分桶的均值(Ch07 起不再写死 recall)
export default function BucketChart({ data }: { data: { name: string; value: number | null }[] }) {
  // 没有任何可绘制的值(空桶 / 全是 NULL)时不渲染图表,否则 hover 会画出越界的深色区域
  if (!data.some((d) => d.value !== null)) {
    return <Empty description="暂无分桶数据" style={{ margin: '0 auto' }} />
  }
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis domain={[0, 1]} />
        <Tooltip />
        <Bar dataKey="value" fill="#3b82f6" />
      </BarChart>
    </ResponsiveContainer>
  )
}
