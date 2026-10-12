import { useEffect, useRef } from 'react'
import { notification } from 'antd'
import type { Run } from '../types'

// 检测 run 从「运行中」跃迁到 完成/失败,弹一次非阻塞通知。
// 为什么用 notification 而非 Modal:评测是后台任务,用户发起后通常去干别的,
// 模态框会阻塞操作;角标提示不打断,想看去点一下即可。
export function useRunCompletionNotice(
  runs: (Pick<Run, 'id' | 'status'> | undefined)[],
  onView?: (id: number) => void,
) {
  const prev = useRef<Record<number, string>>({})

  useEffect(() => {
    for (const r of runs) {
      if (!r) continue
      const before = prev.current[r.id]
      // 只在「运行中 → 终态」这一次跃迁时通知;首次加载时已在跑的 run 记下状态,完成时照样通知
      if (before === 'running' && r.status !== 'running') {
        const common = { placement: 'bottomRight' as const, duration: 6 }
        if (r.status === 'done') {
          notification.success({
            message: `评测 #${r.id} 已完成`,
            description: onView ? '点击查看结果' : undefined,
            onClick: onView ? () => onView(r.id) : undefined,
            ...common,
          })
        } else {
          notification.error({ message: `评测 #${r.id} 失败`, ...common })
        }
      }
      prev.current[r.id] = r.status
    }
  }, [runs, onView])
}
