# EvalFlow Ch23 设计:输入防呆与交互修复

## 定位

一批「用起来才发现」的问题,分两类:

- **真 bug**(逻辑错误):后端 top_k 无上限、运行中误判门禁不通过。
- **交互缺失**(能用但难用):知识库散点悬停显示无意义的坐标、弹窗按钮是英文、加样本单行输入看不到长问题、门禁基线选择刷新即丢。

## 现状(代码位置)

| 问题 | 位置 | 现状 |
|---|---|---|
| ① top_k 无上限 | [snapshot.py](../../backend/snapshot.py) `config_top_k` | `int(...)` 直接返回,`99999`/`-5` 原样通过 |
| ② 散点悬停无意义 | [EmbeddingScatter.tsx](../../frontend/src/components/EmbeddingScatter.tsx) | recharts 默认 Tooltip 只显示 x/y(而 x/y 无绝对意义) |
| ③ 弹窗按钮英文 | 全局 | 未配 antd `ConfigProvider locale` → `OK`/`Cancel` |
| ④ 加样本看不到长问题 | [DatasetDetailView.tsx](../../frontend/src/views/DatasetDetailView.tsx) | 单行 `Input` 水平滚动,长问题看不到开头 |
| ⑤ 运行中误判门禁 | [RunDetailView.tsx](../../frontend/src/views/RunDetailView.tsx) | `running` 时 scores 为空 → 全判「未评」→ FAIL |
| ⑥ 门禁基线不进 URL | [RunDetailView.tsx](../../frontend/src/views/RunDetailView.tsx) | `baselineId` 是本地 state,刷新/分享即丢 |

## 决策

### 决策 1:后端 clamp top_k(**不信任客户端**)

`config_top_k` 返回值钳制到 `[1, MAX_TOP_K]`(MAX_TOP_K=20,给前端 max=10 留余量)。

**理由**:前端 `InputNumber` 的 `min/max` 只在**失焦时**钳制,输入过程中能打任意数字;而且 API 可直接调用,根本不经过前端。校验必须放在服务端。

### 决策 2:散点悬停显示实际内容

自定义 Tooltip:知识块点显示 `文本 + 类别`,query 点显示 `问题原文`。x/y 坐标不再展示(无意义)。

**理由**:悬停是「想细看这个点是什么」的入口,展示无意义的坐标等于浪费交互。

### 决策 3:全局配 antd 中文 locale

入口 `main.tsx` 套 `ConfigProvider locale={zhCN}`,一次性把所有弹窗/分页/空态的文案变中文。

**理由**:逐個弹窗写 `okText` 是打补丁;locale 是根因修复,且顺带修了分页器、Table 空态等其它英文。

### 决策 4:加样本改「两行布局」

第一行:**问题**(`Input.TextArea` autoSize,占满宽度);第二行:**期望要点 + 分桶 + 加样本按钮**。

**理由**:「看不到前面」的根因是**单行输入的水平滚动**,不是缺长度上限——**换行才解决,限长不解决**。问题内容长必须换行;期望要点/分桶内容短,保持单行让整体不至于过高(否则一屏放不下几条样本)。保留内联 = 保留「连续快速加多条」的速度。

### 决策 5:运行中不展示门禁结论

`run.status === 'running'` 时,门禁卡显示「评测中…」而非 PASS/FAIL。

**理由**:评测没跑完,证据不全,此时判「不通过」是**错的**(实测 `evaluate_gate({})` → `passed=False`)。结论只在有完整数据时才有意义。

### 决策 6:门禁基线进 URL

`baselineId` 用 `useSearchParams` 读写 URL(`/runs/5?baseline=3`)。

**理由**:刷新不丢、链接可分享——「把这次对比发给别人看」是评测平台的常见需求。

## 验收

- [x] 后端 `config_top_k` 对越界值钳制(87 后端测试)。
- [x] 散点悬停显示文本/问题原文。
- [x] 所有弹窗按钮为中文。
- [x] 加样本长问题可换行看到全文。
- [x] 运行中的 run 不显示 FAIL。
- [x] 门禁基线刷新后保留。

## 本章不做

- 批量添加金标准(用户决定暂缓)。
- 加样本改弹窗(两行内联已解决可见性,且保留连续添加速度)。

## 追加修复(评审 Ch23 产出时发现)

第一轮改完后逐页复查,又发现 6 处:

| # | 问题 | 根因 | 修法 |
|---|---|---|---|
| 1 | 新建弹窗「31 / 200」压到按钮 | antd `showCount` 把计数 `position:absolute; bottom:-22px` 挂在文本框**下方**,footer 只差 13px | 描述块留 26px 底部间距(实测计数 bottom=331 vs footer top=322) |
| 2 | 加样本 TextArea 撑满 1280px | 表单没限宽,和下方表格比例失衡 | 收进 `Card` + 内容 `maxWidth: 720` |
| 3 | 期望要点无长度限制 | —— | 加 `maxLength={200}`(**不能设必填**:库外题的期望要点本来就是空) |
| 4 | 看 run#1 时基线自动选了最新的 #5 | `runList` 按 id 倒序,`find` 拿到的是**最新**那个 | 改成找 `id < 当前` 里最大的 = **紧邻的上一次**;自己是最老的就不设 |
| 5 | 知识库 query 只有内容 | 接口只返回 `input` | 补 `bucket`——正是「看库外题是否聚在边缘」的用法 |
| 6 | 密钥按钮丑 + 不回填 | Button 里嵌了 Tag;保存后清空 `val` | 去掉嵌套 Tag 改用按钮样式表达状态;打开时回填 `getApiKey()` |

**#4 的原理**:`find` 返回的是**遍历顺序**里的第一个,不是「最接近」的那个。列表按 id 倒序时,`find(r => r.id !== id)` 拿到的是最大 id(最新),而不是紧邻的上一个。想让「默认值」符合直觉,得把筛选条件写成**相对当前项**的(`id < 当前`),而不是「不等于自己」。
