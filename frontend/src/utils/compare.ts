// 多 run 对比的调色板与数量上限(Ch22)。
// 颜色是柱状图/表格里区分不同 run 的唯一手段,调色板用完就重复、图不可读,
// 所以在「选择端」就按调色板容量拦住,而不是等渲染出来才发现糊成一团。

export const COMPARE_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899']

export const MAX_COMPARE_RUNS = COMPARE_COLORS.length
