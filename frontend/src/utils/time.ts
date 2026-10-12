// 后端时间戳是 ISO 串(models.py 的 datetime.isoformat(timespec="seconds")),
// 直接渲染成 "2026-10-12T21:49:14" 中间的 T 很难读。统一在这里格式化。

/** ISO 串 → "2026-10-12 21:49:14";空/缺失返回 '—'。 */
export function formatTime(iso?: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ')
}
