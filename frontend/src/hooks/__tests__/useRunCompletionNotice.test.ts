import { renderHook } from '@testing-library/react'
import { notification } from 'antd'
import { expect, test, vi } from 'vitest'
import { useRunCompletionNotice } from '../useRunCompletionNotice'

test('运行中 → 完成 时弹一次通知(带可点的「查看结果」按钮)', () => {
  const spy = vi.spyOn(notification, 'success')
  const onView = vi.fn()
  const { rerender } = renderHook(
    ({ runs }) => useRunCompletionNotice(runs, onView),
    { initialProps: { runs: [{ id: 1, status: 'running' }] } },
  )
  expect(spy).not.toHaveBeenCalled() // 还在跑,不通知

  rerender({ runs: [{ id: 1, status: 'done' }] })
  expect(spy).toHaveBeenCalledTimes(1)
  expect(spy.mock.calls[0][0].message).toContain('#1')
  expect(spy.mock.calls[0][0].btn).toBeTruthy() // 有按钮 = 看得出能点

  // 再刷新一次(状态没变)不应重复通知
  rerender({ runs: [{ id: 1, status: 'done' }] })
  expect(spy).toHaveBeenCalledTimes(1)
  spy.mockRestore()
})

test('首次加载就已是 done 的 run 不通知(避免进页面就弹)', () => {
  const spy = vi.spyOn(notification, 'success')
  renderHook(() => useRunCompletionNotice([{ id: 1, status: 'done' }]))
  expect(spy).not.toHaveBeenCalled()
  spy.mockRestore()
})

test('运行中 → 失败 弹 error 通知', () => {
  const spy = vi.spyOn(notification, 'error')
  const { rerender } = renderHook(({ runs }) => useRunCompletionNotice(runs), {
    initialProps: { runs: [{ id: 2, status: 'running' }] },
  })
  rerender({ runs: [{ id: 2, status: 'failed' }] })
  expect(spy).toHaveBeenCalledTimes(1)
  spy.mockRestore()
})
