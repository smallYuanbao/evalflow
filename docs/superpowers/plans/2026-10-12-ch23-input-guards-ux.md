# EvalFlow Ch23 实施计划:输入防呆与交互修复

## 背景(对应 spec)

六个修:后端 top_k 钳制、散点悬停内容、中文 locale、加样本两行布局、运行中不判门禁、门禁基线进 URL。

## 任务清单

### Task 1:后端 clamp top_k

- [x] `backend/snapshot.py`:`config_top_k` 钳制到 `[1, MAX_TOP_K]`(=20)。

### Task 2:散点悬停显示内容

- [x] `EmbeddingScatter.tsx`:自定义 Tooltip——chunk 显示「文本 + 类别」,query 显示「问题原文」;不再显示 x/y。

### Task 3:全局中文 locale

- [x] `main.tsx`:`ConfigProvider locale={zhCN}` 包裹。
- [x] 更新 e2e:弹窗确定按钮 `OK` → 中文。

### Task 4:加样本两行布局

- [x] `DatasetDetailView.tsx`:第一行「问题」用 `Input.TextArea` autoSize 占满宽度;第二行「期望要点 + 分桶 + 加样本」。

### Task 5:运行中不判门禁

- [x] `RunDetailView.tsx`:`run.status === 'running'` 时门禁卡显示「评测中…」,不显示 PASS/FAIL。

### Task 6:门禁基线进 URL

- [x] `RunDetailView.tsx`:`baselineId` 改用 `useSearchParams` 读写 `?baseline=`。

### Task 7:测试

- [x] 后端:`config_top_k` 越界钳制测试。
- [x] 前端:加样本布局/门禁运行中/基线 URL 相应用例。
- [x] 全量 + build + e2e 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| top_k 钳制 | Task 1/7 |
| 散点悬停内容 | Task 2 |
| 弹窗中文 | Task 3 |
| 加样本两行 | Task 4/7 |
| 运行中不判门禁 | Task 5/7 |
| 基线进 URL | Task 6/7 |

### Task 8:评审后的追加修复

- [x] 新建弹窗计数与 footer 重叠 → 留底部间距。
- [x] 加样本表单限宽(收进 Card + maxWidth 720)。
- [x] 期望要点加 maxLength(不设必填)。
- [x] 基线默认改为「紧邻的上一次」。
- [x] 知识库 query 补 bucket。
- [x] 密钥按钮去嵌套 Tag + 打开时回填。
