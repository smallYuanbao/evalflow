import { Card, Statistic } from 'antd'

export default function MetricCard({ label, value }: { label: string; value: number | null }) {
  return (
    <Card size="small" style={{ minWidth: 140 }}>
      <Statistic title={label} value={value === null ? '—' : value} precision={value === null ? undefined : 4} />
    </Card>
  )
}
