import { Card, Statistic, Tooltip } from 'antd'

// desc(Ch24):指标名光看名字分不清(「召回(机械)」vs「上下文召回」),悬停给一句人话解释
export default function MetricCard({
  label,
  value,
  desc,
}: {
  label: string
  value: number | null
  desc?: string
}) {
  const title = desc ? (
    <Tooltip title={desc}>
      <span style={{ cursor: 'help', borderBottom: '1px dashed #d9d9d9' }}>{label}</span>
    </Tooltip>
  ) : (
    label
  )
  return (
    <Card size="small" style={{ minWidth: 140 }}>
      <Statistic title={title} value={value === null ? '—' : value} precision={value === null ? undefined : 4} />
    </Card>
  )
}
