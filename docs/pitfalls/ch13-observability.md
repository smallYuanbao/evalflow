# Ch13 踩坑:可观测性(结构化日志 + 指标趋势 + CSV 导出)

> 这一章给平台加「结构化日志 + 历史趋势折线图 + 明细导出」。坑主要在「路由顺序」「DetachedInstanceError 复发」「CSV 编码」「日志幂等」。

## 坑 1:`/runs/trend` 要注册在 `/runs/{run_id}` 之前,否则 422

**现象**:前端请求趋势接口 `/runs/trend` 返回 422(参数校验失败),而不是趋势数据。

**根因**:FastAPI 按**注册顺序**匹配路由。`/runs/{run_id}` 里 `run_id: int`,如果它先注册,`/runs/trend` 的 `"trend"` 会被当成 `run_id` 去解析,`int("trend")` 失败 → 422。路径参数路由是「贪心」的,静态段和动态段重名时,谁先注册谁先匹配。

**修法**:`/runs/trend`(和 `/runs/{run_id}/export` 这种更具体的路由)注册在 `/runs/{run_id}` **之前**。测试里专门写 `test_runs_trend_route` 断言 `/runs/trend` 返回 200 而非 422,把「顺序」这个易碎的约束固化成回归测试。

**原理**:框架按声明顺序建路由表。静态路径段没有「优先级更高」这回事,全靠手排;这种坑靠测试守住,别靠记忆。

## 坑 2:DetachedInstanceError 会复发——commit 之后「才想起来」要记录/断言

**现象**:这一章 3 个测试同时挂,报 `DetachedInstanceError: Instance <Trace at ...> is not bound to a Session`。一处是 `_process_item` 末尾新加的 `logger.info(..., extra={"trace_id": tr.id})`,另两处是测试里 `assert row[0] == str(t1.id)`、`by_id[r1.id]`。

**根因**:还是 Ch10 坑 2 那条铁律——`s.commit()` 让 ORM 对象 `expire`,之后 `s.close()` 让它 detached,再访问属性(包括主键)就抛。但这次的复发点更隐蔽:**日志和断言是在「commit 已经写完」之后才想起来加的**,加的位置正好在 `commit()/close()` 之后,顺手就引用了 ORM 对象。

**修法**:分两层——
- 生产代码:`trace_id = tr.id` 在 `s.flush()` 之后、`s.commit()` 之前取出,日志用普通变量。
- 测试代码:`r1_id, r2_id = r1.id, r2.id`、`t1_id = t1.id` 在种子数据 `s.commit()` 之前取出,断言用普通变量。

**原理**:commit 是「分水岭」——之前的 ORM 对象还能用(会话还开着,访问会回库刷新),之后就必须当它是「过期身份证」。凡是 commit 之后再写的代码(日志、断言、返回值),一律只准碰普通 Python 值。这个坑不是记一次就好,它会在每次「事后补代码」时复发,养成「commit 之前先取字段」的条件反射。

## 坑 3:CSV 导出要加 BOM,否则 Excel 打开中文乱码

**现象**:导出的 CSV 里中文(问题、回答、指标名)在 Excel 里显示成乱码,用文本编辑器看却是好的。

**根因**:CSV 没有元信息告诉程序它是 UTF-8。Excel 默认用本地编码(中文 Windows 是 GBK)猜,UTF-8 的中文就被解错。UTF-8 BOM(`﻿`,三个字节 `EF BB BF`)是约定好的「我是 UTF-8」标记,Excel 看到它就走 UTF-8 解码。

**修法**:返回内容前面拼 `"﻿" + csv_text`,`Content-Type` 写 `text/csv; charset=utf-8`。宁可让 Excel 正确,多三个字节无副作用(文本编辑器也能识别)。

**原理**:编码问题本质是「字节流缺了字符集标签」。有标准能带标签就带(BOM),别赌对方的默认编码。

## 坑 4:setup_logging 要幂等,否则主进程/worker 都调会重复打日志

**现象**:把 `setup_logging()` 同时接进 main 的 lifespan 和 celery worker 的 `run_task`,如果不加防重,同一个进程里被调两次会打印两行相同的日志。

**根因**:`logging.getLogger("backend").addHandler(...)` 是「叠加」不是「覆盖」。每次调用都新挂一个 handler,日志会同时被所有 handler 各打一遍。而 main 和 worker 都可能 import 到 `run_service`,触发路径有重叠。

**修法**:`setup_logging()` 开头加 `if logger.handlers: return` 幂等保护,只挂一次。`logger.propagate = False` 防止再冒泡到 root logger 二次输出。

**原理**:全局单例(logger、限流器、连接池)的初始化函数都要幂等——被调多次不产生副作用。这和 Ch12 坑 5「import 时固化配置」是一体两面:一个讲「别重复初始化」,一个讲「初始化时读一次」。

## 小结

这一章收敛成一句:**「事后补的代码」最容易踩「事先定的铁律」**——趋势路由要抢在动态路由前面、commit 之后别碰 ORM、导出要显式带编码、初始化要幂等。日志/趋势/导出都是「旁路能力」,做对的前提是别破坏主流程里已经成立的那些边界(路由顺序、会话生命周期、进程初始化)。
