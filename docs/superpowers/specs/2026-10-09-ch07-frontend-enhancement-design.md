# EvalFlow Ch07 设计:前端体验增强

## 目标

Ch06 之后平台功能完整。Ch07 回填前端工程化与体验——当前有三个明显短板:

1. **bundle 1.3MB**(超 500KB 警告),所有页面打进一个包,首屏加载重。
2. **分桶图只能看 recall 一个指标**,Ch05 已有 6 个指标却切不了。
3. 加载/空/错态还有统一打磨空间。

Ch07 做三件事:

1. **代码分割 + 路由懒加载**:按路由拆包,首屏只加载当前页。
2. **分桶图指标切换**:RunDetailView 的分桶图可下拉切换 6 个指标。
3. **体验细节打磨**:统一 Suspense 兜底、复查各页 loading/空/错态。

验收标准:

1. 懒加载后构建产物从单 chunk 拆成路由级多 chunk,首屏体积明显下降。
2. 分桶图能下拉切换指标,柱状图随之变化,默认 recall。
3. 各页加载/空/错态一致、无闪屏;路由切换有 Suspense 兜底。

## 设计

### 1. 代码分割 + 路由懒加载

- `App.tsx` 里 4~5 个路由视图(DatasetsView / DatasetDetailView / RunsView / RunDetailView / CompareView)改用 `React.lazy(() => import(...))` + `<Suspense fallback={<Skeleton/>}>` 包裹。
- 好处:每个视图独立 chunk,vite 自动按动态 import 拆包,首屏只加载入口 + 当前路由。

### 2. 分桶图指标切换

- `RunDetailView` 加一个指标 `Select`(选项 = 当前 run 的 `metricKeys` + 中文标签),选中即重画分桶柱状图。
- 默认 `recall`(没有 recall 则第一个指标,与 Ch05 现有逻辑一致)。
- 把「柱状图画哪个指标」从写死的 `recall` 改成受控状态 `chartMetric`。

### 3. 体验细节

- Suspense fallback 统一用 antd `Skeleton`。
- 复查 `useRequest` 的三态:loading 骨架屏、error 重试、empty 空态在 5 个视图是否一致。

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 懒加载 | `React.lazy` + `Suspense` | 第三方分包工具:项目规模小,lazy 是标准做法,零依赖 |
| 状态管理 | 不引 zustand/redux,保持 useRequest + useState | 引状态库:当前数据流简单,引库是过度设计;对比页也是局部状态,不需要全局 |
| 指标切换 | RunDetailView 内 Select 局部状态 | 全局/路由参数:单页局部交互,局部状态够,不污染 URL |
| 指标默认值 | 默认 recall,缺失回退第一个 | 硬编码 recall:库外-only 的 run 没有 recall,需回退兜底 |

## 本章不做

- 引入状态管理库。
- SSR / 服务端渲染。
- 组件库主题定制 / 深色模式。
- 图表的高级交互(缩放/联动)—— recharts 原生够用即可。
