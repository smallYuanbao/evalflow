import { Card, Statistic, Tooltip } from 'antd'

// Ch31:覆盖率低于这个比例就标黄 —— 与后端 gate.MIN_COVERAGE 保持一致
const MIN_COVERAGE = 0.8

/**
 * 指标卡。
 *
 * desc(Ch24):指标名光看名字分不清(「召回(机械)」vs「上下文召回」),悬停给一句人话解释。
 * coverage(Ch31):**均值基于几条算出来的**。20 条里挂了 17 条 judge 时,
 * 均值只由剩下 3 条算出——那是个看起来正常的数字,却基于 15% 的样本。
 * 不显示 n 的话,用户会把它当成「整批样本的表现」。
 */
export default function MetricCard({
  label,
  value,
  desc,
  coverage,
}: {
  label: string
  value: number | null
  desc?: string
  coverage?: { scored: number; attempted: number } | null
}) {
  const title = desc ? (
    <Tooltip title={desc}>
      <span style={{ cursor: 'help', borderBottom: '1px dashed #d9d9d9' }}>{label}</span>
    </Tooltip>
  ) : (
    label
  )
  const low = !!coverage && coverage.attempted > 0 && coverage.scored / coverage.attempted < MIN_COVERAGE
  return (
    <Card size="small" style={{ minWidth: 140 }}>
      <Statistic title={title} value={value === null ? '—' : value} precision={value === null ? undefined : 4} />
      {coverage && coverage.attempted > 0 && (
        <Tooltip title={`该指标在 ${coverage.attempted} 条样本里评上了 ${coverage.scored} 条;均值只基于评上的这些`}>
          <div style={{ fontSize: 12, marginTop: 4, cursor: 'help', color: low ? '#d48806' : '#999' }}>
            {low ? '⚠ ' : ''}采样 {coverage.scored}/{coverage.attempted}
          </div>
        </Tooltip>
      )}
    </Card>
  )
}
