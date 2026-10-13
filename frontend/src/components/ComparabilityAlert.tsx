import { Alert } from 'antd'
import type { Comparability } from '../types'

/**
 * 两次 run 的可比性提示(Ch29)。
 *
 * 门禁 / 分桶归因 / 逐条 Diff 的结论,都建立在「两边测的是同一批题」这个前提上。
 * 前提不成立时**必须显式说出来**——静默给个 PASS/FAIL 比不给更危险:
 * 用户会当成「质量回归」,而它其实是「换了一批题」。
 *
 * comparable: true=可比(不显示) / false=评测集变过 / null=早期 run 没记录,不知道。
 */
export default function ComparabilityAlert({ value }: { value?: Comparability | null }) {
  if (!value || value.comparable === true) return null
  const unknown = value.comparable === null
  return (
    <Alert
      type={unknown ? 'info' : 'warning'}
      showIcon
      style={{ marginBottom: 12 }}
      message={unknown ? '无法确认两次 run 是否可比' : '两次 run 的评测集不是同一批题'}
      description={value.reason}
    />
  )
}
