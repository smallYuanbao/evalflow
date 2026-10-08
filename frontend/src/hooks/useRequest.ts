import { useCallback, useEffect, useRef, useState } from 'react'

// fn 接收 AbortSignal;deps 变化或组件卸载会自动打断上次调用(防 stale 覆盖)
export function useRequest<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const run = useCallback(() => {
    abortRef.current?.abort() // 打断上一次未完成的调用
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    fn(controller.signal)
      .then(setData)
      .catch((e) => {
        if (controller.signal.aborted) return // 主动取消不算错误
        setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    run()
    return () => abortRef.current?.abort() // 组件卸载时打断
  }, [run])

  return { data, loading, error, reload: run }
}
