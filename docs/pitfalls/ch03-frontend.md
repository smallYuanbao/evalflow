# Ch03 踩坑:前端可视化平台

> 这一章搭 React + Vite + antd + recharts 前端,并给后端补只读接口。坑最多,前后端都有。

## 坑 1:Node 版本太旧 + 依赖没 pin 版本

**现象**:本机默认 Node 是 v14,Vite 8 要求 Node 18+,直接 `npm install` 就挂;用 `@latest` 装依赖会装成 React 19 + antd 6,和 spec 的 React 18 + antd v5 不符。

**根因**:全局默认 Node 版本落后;`@latest` 不锁定大版本。

**修法**:先 `nvm use 20`(或把 `~/.nvm/versions/node/v20.x/bin` 加进 PATH),依赖**显式 pin 到 spec 版本**:

```bash
npm install react@^18 react-dom@^18 antd@^5 react-router-dom@^6 recharts@^2 axios
```

**原理**:前端生态大版本之间破坏性变更多(React 19、antd 6),**用 `@latest` 是给自己埋雷**,要么 pin 版本、要么用 lockfile 锁死。

## 坑 2:jsdom 测试下 antd / recharts 缺浏览器 API

**现象**:跑 Vitest + Testing Library 测 antd 组件时,`window.matchMedia` 未定义;recharts 的 `ResponsiveContainer` 依赖 `ResizeObserver`,jsdom 也没有。

**根因**:`jsdom` 只模拟 DOM,不模拟 `matchMedia`、`ResizeObserver` 这些浏览器 API,而 antd/recharts 内部会用到。

**修法**:在 `vitest.setup.ts` 里补 stub:

```ts
Object.defineProperty(window, "matchMedia", { writable: true, value: (q) => ({ matches: false, media: q, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) });
class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
```

**原理**:这是「在 jsdom 测 UI 库」的必备 gotcha——UI 库假设浏览器环境,测试环境要补最小实现。**用哪个 UI 库,先查它依赖哪些浏览器 API**。

## 坑 3:N+1 查询

**现象**:评测集列表 N 行,每行都要 `item_count`(样本数);run 列表每行都要 `dataset_name`(评测集名)。如果逐行查,列表 N 行就 N+1 次 SQL。

**根因**:ORM 循环里逐条发查询,把「1 次查主表 + N 次查关联」放大成 N+1。

**修法**:批量聚合一次查完:

```python
# item_count:一次 GROUP BY
counts = dict(
    s.query(DatasetItem.dataset_id, func.count(DatasetItem.id))
     .filter(DatasetItem.dataset_id.in_([d.id for d in ds]))
     .group_by(DatasetItem.dataset_id).all())
# dataset_name:一次 IN 回填
names = dict(s.query(Dataset.id, Dataset.name).filter(Dataset.id.in_({r.dataset_id for r in runs})))
```

**原理**:N+1 是 ORM 最经典的性能坑。**列表接口先想清楚「每行要多显示什么」,再决定用 JOIN/GROUP BY/IN 一次性取**,别在渲染循环里查。

## 坑 4:LLM 调用要加超时

**现象**:LLM 卡住时,run 永远停在 running,前端一直轮询干等。

**根因**:`OpenAI` 客户端默认可能无限等响应。

**修法**:

```python
# config.py
chat_timeout: float = 60.0
# llm.py
_client = OpenAI(api_key=..., base_url=..., timeout=settings.chat_timeout)
```

**原理**:**所有外部 IO 都要有超时**,否则一个慢请求拖垮整个流程。超时后的行为要分层:生成超时 → run failed;judge 超时 → 该条记 NULL(不拖垮 run)。

## 坑 5:SQLite 迁移——`create_all` 不会 ALTER

**现象**:给老表加 `updated_at` 列,`create_all` 之后老库的表还是没这列,查询直接报 `no such column`。

**根因**:SQLAlchemy `create_all` 只「建不存在的表」,**不会给已存在的表加列**。

**修法**:手写一个轻量 `_migrate()`:启动时 `inspect` 检查列,缺了 `ALTER TABLE ... ADD COLUMN`,再 `UPDATE` 回填默认值。

**原理**:SQLite 的 ALTER 能力有限(加列 OK,改列/删列要重建表),所以项目用一个「启动时检查 + 加列」的最小迁移器。这个机制 Ch10 加 `progress` 列也复用了。

## 坑 6:React StrictMode 双跑 effect

**现象**:开发模式切 tab,Network 面板出现大量 `canceled` 请求。

**根因**:`<StrictMode>` 在**开发模式**会故意双跑 effect(挂载→卸载→再挂载),`useRequest` 每次挂载「发请求→取消→再发」,产生无谓的 canceled 请求。

**修法**:去掉 `<StrictMode>`(生产本就无双跑,去掉更贴近真实行为)。

**原理**:StrictMode 是帮你在开发期暴露 bug 的,但和「自动打断上次请求」的 hook 叠加时会产生干扰。理解它双跑 effect 的行为,就知道什么时候该留、什么时候该去。

## 坑 7:测试文件的 TypeScript 三件套

**现象**:`npm run build`(tsc -b)去 type-check 测试文件直接失败;编辑器里 `test`/`expect` 或 `toBeInTheDocument` 报「不存在」。

**根因** + **修法**(三个独立小坑):

1. **`tsconfig.app.json` 加 `exclude: ["src/**/__tests__"]`**——否则 build 会 type-check 测试文件,而测试的全局类型不在 app tsconfig 里。
2. **测试文件显式 `import { test, expect, vi } from "vitest"`**——不依赖 `globals: true` 的隐式全局,编辑器也能识别。
3. **每个测试文件 `import "@testing-library/jest-dom/vitest"`**——测试文件被 tsc 排除后走 VSCode 的 inferred project,要把 jest-dom 类型增强显式引入该文件作用域(运行时不报错,只是编辑器类型)。

**原理**:`tsc -b`(project references)和 VSCode 的 inferred project 是两套类型解析,测试文件夹在中间容易两边都缺类型。显式 import + exclude 是标准解法。

## 坑 8:recharts 空数据时 hover 高亮溢出

**现象**:分桶图数据全为 NULL 时,recharts 的 hover 高亮区会溢出坐标系,图很难看。

**根因**:recharts 在无数据点时的 hover 行为异常。

**修法**:渲染前判断「有没有可绘制的值」,没有就直接显示空态,不渲染图表:

```tsx
if (!data.some((d) => d.recall !== null)) {
  return <Empty description="暂无分桶数据" />;
}
```

**原理**:图表库对边界数据(全空、全 0、单点)常有渲染 bug,**先做数据检查再决定画不画**,比调图参数省事。
