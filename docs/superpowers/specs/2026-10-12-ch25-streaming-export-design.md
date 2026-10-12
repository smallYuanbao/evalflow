# EvalFlow Ch25 设计:导出改为流式(两端都不缓冲)

## 定位

不是新功能,是**把「数据规模」这个被忽略的维度补上**。导出 CSV 在样本少时没问题,但原实现**两端都把整份文件堆在内存里**,样本一多就会卡死/爆内存。

## 现状(原实现)

**后端**:
```python
traces = s.query(Trace).filter(...).all()   # ① 全量 ORM 对象(含 output 正文)
buf = io.StringIO()                          # ② 整份 CSV 字符串
return buf.getvalue()
...
content="﻿" + csv_text                  # ③ 再复制一份(加 BOM)
```

**前端**:
```js
const csv = await api.exportRunCsv(id)   // axios 把整个响应读成 JS 字符串
const blob = new Blob([csv], ...)        // 再复制一份
URL.createObjectURL(blob)                // 再持有
```

两端各 2~3 份 → 一份 100MB 的 CSV,前后端合计要吃 400~600MB。

**量化**(单条 ≈ 问题+回答+分数 ≈ 0.6~1KB):

| 样本数 | CSV | 结果 |
|---|---|---|
| 1,000 | ~1 MB | 无压力 |
| 10,000 | ~10 MB | 开始卡顿 |
| 100,000 | ~100 MB | 前端 OOM / 卡死 |

**还有一个体验问题**:全程无流式、无进度——点了按钮页面**卡住没有任何反馈**,像死了一样。`new Blob([巨串])` 还是在主线程上跑,直接冻结 UI。

## 决策

### 决策 1:后端 `StreamingResponse` + `yield_per`,内存 O(1)

- 分数是小标量(`trace_id/name/value`),一次取走不心疼;
- **真正占内存的是 trace 正文**(input/output),用 `yield_per(500)` 分批取,一次只驻留一批;
- 逐行 `yield`,边生成边发。

**依据**:SQLAlchemy 的 `yield_per` 是「流式消费大结果集」的标准做法——把内存从 O(全部) 降到 O(批次)。

**顺带删掉**了非流式的 `run_export_csv`(只剩测试在用),避免两份实现漂移。

### 决策 2:前端交给「浏览器原生下载」,不碰 JS 内存

```js
const a = document.createElement('a')
a.href = exportRunCsvUrl(id)   // 响应带 Content-Disposition: attachment
a.click()
```

浏览器**原生流式落盘**:不经过 JS 内存、自带进度条和取消按钮、磁盘多大就能下多大。

**为什么可行**:后端**早就设了** `Content-Disposition: attachment`,但原前端没用它、自己搞了一套 Blob 下载——这个 header 本来就是为「让浏览器自己处理」准备的。

**代价(要记着)**:导航请求**带不上 `Authorization` 头**,所以已设密钥时改用 `?token=` 查询参数,**只有导出这一个只读端点开这个口子**。

> token 落在 URL 里会进访问日志/浏览器历史——demo 单密钥可接受;**生产应换成一次性下载令牌**(短时效、一次性、绑用户)。

## 验收

- [x] 响应 `transfer-encoding: chunked`(实测确认是流式,不是缓冲)。
- [x] 前端点击直接触发浏览器下载,不再在 JS 里拼 Blob。
- [x] 带密钥时 `?token=` 可通过鉴权。
- [x] 不存在的 run 仍返回 404。
- [x] 后端 87 / 前端 33 / build / e2e 全绿。

## 本章不做

- 后台任务生成 + 对象存储 + 下载链接(几百 MB 以上才需要,引入新基础设施)。
- 一次性下载令牌(生产该做,demo 先用 `?token=`)。
