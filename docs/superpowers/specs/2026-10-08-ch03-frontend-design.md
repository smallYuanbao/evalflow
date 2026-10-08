# EvalFlow Ch03 设计:前端(评测平台可视化)

## 目标

Ch03 把 Ch02 的评测能力做成可视化平台:浏览器里建评测集、发起 run、看三层指标(recall/faithfulness/rejection)与分桶聚合、下钻到逐条 trace。前端按真实工程标准做:路由、组件库、测试、兜底、loading、骨架屏。这是「平台」的最后一环,补上后整个 RAG 评测平台闭环。

验收标准:
1. 前端能列出/创建评测集,能给评测集加样本(input / expected_output / bucket)。
2. 前端能对某评测集发起 run,页面轮询直到状态变 done / failed。
3. run 详情页展示:三层指标卡片 + 分桶聚合(表 + 条形图) + 逐条 trace 明细。
4. 路由:`/datasets`、`/runs`、`/runs/:id` URL 直达,刷新不丢状态。
5. 兜底:加载有骨架屏,请求失败有错误态 + 重试,渲染异常有 ErrorBoundary,空数据有空态。
6. 前端测试:Vitest + Testing Library 覆盖核心视图,`npm test` 全绿。
7. 前后端打通(dev 用 CORS),后端一条命令 + 前端一条命令即可本地跑起来。

## 技术栈(定死,不可自行更换)

- 前端:React 18 + Vite + TypeScript(react-ts 模板),标准 SPA。
- 路由:react-router-dom(`/datasets`、`/runs`、`/runs/:id`)。
- 组件库:antd v5(Table/Form/Modal/Statistic/Tag/Skeleton/Result/Empty/message 等)。
- 图表:recharts(分桶条形图)——antd 不内置图表,recharts 生态最大、与 antd 常见搭配。
- 测试:Vitest + Testing Library(@testing-library/react + jest-dom + jsdom),mock api 模块。
- 后端:复用 Ch02(FastAPI + SQLite),新增 CORS + 只读接口(含 dataset_name / 评测集详情)+ created_at / updated_at 时间戳。

## 架构与数据流

```
浏览器(React SPA @5173)
   │  react-router 四路由
   │  CORS
   ▼
FastAPI @8000
   ├─ GET  /datasets ─────────── 评测集列表(含 item_count / updated_at,按 updated_at 倒序)
   ├─ POST /datasets ─────────── 建评测集
   ├─ GET  /datasets/{id} ─────── 评测集详情(名称/描述/样本数,Ch03 新增)
   ├─ POST /datasets/{id}/items  加样本(顺带刷新 updated_at)
   ├─ GET  /datasets/{id}/items  样本列表(Ch03 新增)
   ├─ POST /runs ────────────── 发起评测(后台跑)
   ├─ GET  /runs ────────────── run 列表(Ch03 新增,倒序,含 dataset_name)
   ├─ GET  /runs/{id} ───────── 聚合(三层指标 + 分桶)
   └─ GET  /runs/{id}/traces ── 逐条明细
```

## 后端补齐(Ch03 需要,Ch02 没做)

1. `GET /runs`:run 列表(倒序,含 dataset_id / dataset_name / status / created_at)。dataset_name 用一次 `IN` 查询回填,避免逐条查的 N+1。
2. `GET /datasets/{id}/items`:某评测集的样本列表。
3. `GET /datasets/{id}`:评测集详情(名称/描述/样本数);不存在返回 404(问题3 详情页需要)。
4. `GET /datasets` 补 `item_count` 与 `updated_at`,并按 `updated_at DESC` 排序(问题1:按修改时间先后)。
5. `updated_at` 时间戳:Dataset 新增 `updated_at`,加样本时刷新(视为「修改」);SQLite 的 `create_all` 不会给已存在的表加列,`db.py` 加轻量迁移(ALTER + 回填 created_at)。
6. CORS 中间件放行 `http://localhost:5173`。
7. `created_at` 补默认时间戳(现为 NULL,列表要显示先后)。
8. LLM 调用加超时(`config.chat_timeout` 默认 60s):防 DeepSeek 卡住导致 run 永久 running。

## 目录结构(新增/改动)

```
frontend/
  index.html
  package.json
  vite.config.ts          # 含 vitest 测试配置(jsdom)
  vitest.setup.ts         # jest-dom + antd matchMedia stub
  src/
    main.tsx              # BrowserRouter 挂载 + antd reset.css
    App.tsx               # antd Layout + Menu + 路由表 + ErrorBoundary
    api/
      client.ts           # 统一请求层(onRequest 参数注入 / onResponse 错误码兼容)
      index.ts            # 类型化接口方法
    types.ts              # Dataset / DatasetItem / Run / RunDetail / Trace 类型
    hooks/
      useRequest.ts       # 统一 loading / error / retry(兜底基座)
    components/
      ErrorBoundary.tsx   # 渲染异常兜底(antd Result + 重试)
      MetricCard.tsx      # 单指标卡片(antd Statistic)
      BucketChart.tsx     # 分桶条形图(recharts)
    views/
      DatasetsView.tsx        # 列表 + 新建(Modal),「操作」列点「查看」跳详情页
      DatasetDetailView.tsx   # 评测集详情:返回 + 加样本表单 + 样本列表
      RunsView.tsx            # 发起 + 列表(轮询 + 状态 Tag + dataset_name + 空集置灰)
      RunDetailView.tsx       # 指标 + 分桶 + traces(antd Table)
      __tests__/              # Vitest + RTL
backend/
  main.py                 # 补只读接口 + CORS + updated_at 排序 + dataset_name
  models.py               # created_at / updated_at 补默认时间戳
  db.py                   # 轻量迁移:老 datasets 表补 updated_at 列
```

## 请求层封装(统一)

所有接口走 `api/client.ts` 的 `request<T>()`,内置两个钩子:

- **请求「前」钩子 `onRequest`**:统一参数注入(公共 header 等;鉴权 token / 请求 id 以后都在这加),各接口方法不再手写 header。
- **请求「后」钩子 `onResponse`**:异常错误码兼容——`ok` 直接放行;非 `ok` 优先解析 FastAPI 的 `{"detail": "..."}`,再映射错误码(400/401/403/404/422/500)到友好文案,抛 `ApiError(status, message)`;网络层失败(断网/CORS/后端没起)抛 `ApiError(0, "网络异常")`。

- **请求取消**:`request` 透传 `AbortSignal`;`useRequest` 每次发起新请求前 abort 上一次(deps 变化 / 卸载),防慢响应覆盖新响应(stale response)。

好处:参数注入和错误处理只写一次;上层 `useRequest` 拿到带状态码的 `ApiError`,视图展示 `error.message` 即可,将来也可按 `status` 分支(如 401 跳登录)。

## 接口契约(前端视角)

### GET /datasets
`[{id, name, description, item_count, updated_at}]`,按 `updated_at` 倒序(最近修改在前)。

### GET /datasets/{id}
`{id, name, description, item_count}`;不存在 404 `{"detail": "评测集不存在"}`。

### GET /datasets/{id}/items
`[{id, input, expected_output, bucket}]`

### POST /runs
请求 `{dataset_id, config?}` → `{id, status: "running"}`

### GET /runs
`[{id, dataset_id, dataset_name, status, created_at}]`,倒序。

### GET /runs/{id}
`{id, dataset_id, status, config, item_count, scores: {recall_avg, faithfulness_avg, rejection_rate}, by_bucket: {bucket: {count, recall_avg, faithfulness_avg, rejection_rate}}}`

### GET /runs/{id}/traces
`[{trace_id, input, output, retrieved_context, latency_ms, scores: [{name, value}]}]`

## 前端交互细节(兜底四件套)

- **loading**:首屏用 antd `Skeleton`(骨架屏),按钮操作用 `loading`/`Spin`,更细腻的体验。
- **错误兜底**:请求失败 → antd `Result`(error)+ 重试按钮;渲染异常 → `ErrorBoundary` 兜底。
- **空态**:无数据 → antd `Empty`。
- **轮询**:run 发起后 `running`,前端每 1.5s 轮询 `GET /runs/{id}`,直到 `done`/`failed`。
- **加样本交互**:独立详情页 `/datasets/:datasetId`(问题3:相比「内容出现在表格下方」,跳转新页/弹窗更清晰)。详情页有返回按钮、加样本表单、样本列表。
- **可点击区域可识别**:跳转入口用「操作」列的链接按钮(`查看`),不用整行 hover 点击(问题2:行可点但无视觉提示)。
- **空评测集禁止发起评测**:发起评测下拉里,样本数为 0 的评测集置灰并标注 `(空)`(问题5)。
- **分桶图空态**:所有分桶都没有 recall 数据时不渲染图表,改显示 `Empty`(问题6:无数据时 recharts 的 hover 高亮区会溢出坐标系)。
- **表单校验**:新建评测集名称为空时「确定」禁用;加样本「问题」为空时按钮禁用——否则空值也能提交,产生空白行/空评测集。
- **菜单与路由联动**:顶部 Menu 用 `useLocation` 派生的 `selectedKeys`,浏览器前进/后退也能正确切换 tab。
- 统一基座 `useRequest(fn)`:返回 `{data, loading, error, reload}`,三视图共用,避免重复写 loading/error。

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 前端栈 | React + Vite + TS | 原生 HTML:用户是前端,React 更贴合日常、面试展示更好 |
| 路由 | react-router-dom,3 路由 | state 切换:URL 直达 + 刷新不丢状态是真实项目刚需 |
| 组件库 | antd v5 | 手写:Table/Modal/Statistic/Skeleton 现成,用户日常也用它 |
| 图表 | recharts(非 @ant-design/charts) | antd 不内置图表;recharts 生态最大、成本低,与 antd 常见搭配 |
| 跨域 | FastAPI CORS 放行 5173 | Vite proxy:CORS 更显式,把「前后端分离要开 CORS」讲清楚 |
| 测试 | Vitest + RTL,mock api 模块 | msw:demo 规模 vi.mock 够用,少一层依赖 |
| 兜底 | useRequest 统一 loading/error/retry + ErrorBoundary | 各视图散写:重复且易漏,抽 hook 是标准做法 |
| 后端补接口 | Ch03 顺带补 3 只读接口 + CORS + created_at | 前端硬凑:列表接口本来就该有,补上才是完整平台 |
| 请求封装 | client.ts 统一 onRequest/onResponse 钩子 + ApiError + 错误码映射 | 各接口裸 fetch:参数注入和错误码处理散落重复,统一封装是标准做法 |
| 请求取消 | useRequest 用 AbortController 打断上次请求 | 不取消:慢响应覆盖新响应(stale),卸载后 setState 也是隐患 |
| LLM 超时 | 后端 config.chat_timeout(默认 60s) | 不设超时:DeepSeek 卡住 run 永久 running,前端轮询永远等不到 done |
| 评测集排序 | 按 `updated_at` 倒序,加样本刷新它 | 按 id/创建时间:用户要求按修改时间先后(问题1) |
| 加样本交互 | 独立详情页 `/datasets/:id` | 列表下方内联展开:内容挤在下方、易错,跳转新页更清晰(问题3) |
| 表格跳转入口 | 操作列「查看」链接按钮 | 整行 hover 点击:可点区域无视觉区分(问题2) |
| 空评测集 | 发起评测下拉置灰 + 标 `(空)` | 可点:空集跑评测无意义(问题5) |
| 分桶图空态 | 全空时渲染 antd Empty | recharts 空数据:无数据 hover 高亮区溢出坐标系(问题6) |
| 表单校验 | 关键字段为空时禁用提交按钮(前端校验) | 空值也能提交:产生空白行/空评测集 |
| 菜单高亮 | Menu 用 useLocation 派生的 selectedKeys | defaultSelectedKeys 只认初始路由,后退不联动 |

## 本章不做

- 登录/鉴权(demo 不需要)
- 真实向量检索可视化(Ch04)
- 部署/容器化(只做本地 dev)
- 端到端测试(Playwright/Cypress 后置;单元 + 组件测试已覆盖核心)
