# EvalFlow Ch07 实施计划:前端体验增强

## 背景(对应 spec)

功能完整后回填前端工程化与体验。三个短板:

1. **bundle 1.4MB 单 chunk**(超 500KB 警告),所有页面打进一个包,首屏加载重。
2. **分桶图只能看 recall 一个指标**,Ch05 已有 6 个指标却切不了。
3. 加载态兜底不统一(懒加载后必须有 Suspense fallback)。

## 任务清单

### Task 1:路由懒加载(React.lazy + Suspense)

- [x] `App.tsx`:6 个视图改用 `lazy(() => import(...))`,`<Suspense fallback={<Skeleton/>}>` 包裹 `<Routes>`。验收:build 产物从单 chunk 拆成路由级多 chunk。

```tsx
import { lazy, Suspense } from 'react'
import { Skeleton } from 'antd'
const DatasetsView = lazy(() => import('./views/DatasetsView'))
// ...
<Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} />}>
  <Routes>…</Routes>
</Suspense>
```

### Task 2:BucketChart 通用化

- [x] `BucketChart.tsx`:入参从写死的 `recall` 字段改为通用 `value` 字段,`<Bar dataKey="value">`。空态逻辑不变(全 NULL 显示「暂无分桶数据」)。

### Task 3:RunDetailView 分桶图指标切换

- [x] `RunDetailView.tsx`:加 `chartMetric` 状态 + 指标 `Select`(默认 recall,缺失回退第一个);`bucketData` 改传 `value` 字段。

```tsx
const [chartMetric, setChartMetric] = useState<string | null>(null)
const effective = chartMetric && metricKeys.includes(chartMetric)
  ? chartMetric
  : metricKeys.includes('recall') ? 'recall' : metricKeys[0]
// Card extra 放 Select,options = metricKeys → 中文标签
```

### Task 4:前端测试 + 全量验证

- [x] `RunDetailView.test.tsx`:加「指标切换下拉存在、默认召回」断言(现有「暂无分桶数据」空态测试不受影响)。
- [x] 跑 vitest + build,确认拆包 + 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 拆包后首屏体积下降 | Task 1(build 输出多 chunk) |
| 分桶图可切换指标 | Task 2 + 3 + 4 |
| 加载态统一、无闪屏 | Task 1 的 Suspense fallback |
