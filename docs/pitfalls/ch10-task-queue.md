# EvalFlow Ch10 踩坑记录(Celery + Redis 任务队列)

> 这一章把执行模型从「进程内串行 BackgroundTasks」升级到「Celery + Redis + 线程池并发」。踩的坑几乎都围绕一个主题:**并发 + 状态**。前端转后端最容易在这里翻车。每条按「现象 → 根因 → 修法 → 原理」记,以后 Ch11+ 继续追加。

## 坑 1:`database is locked` —— 写锁跨了 LLM 调用(最核心)

**现象**:真机跑 `dataset#1`(7 条样本)并发时,2 条报 `OperationalError: (sqlite3.OperationalError) database is locked`,run 被置 failed、progress=0。但单独跑那 2 条样本都正常。

**根因**:`_process_item` 里先 `s.flush()`(拿到 SQLite 写锁),**紧接着执行 5 个 LLM judge**(每个要调 deepseek 几秒)。写锁被 LLM 调用长期持有;4 个线程并发时,其他线程的 `flush` 等 `busy_timeout=5000` 超时后报 locked。

```python
# 错误写法:写锁(flush)到 commit 之间夹着 LLM 调用
s.add(tr)
s.flush()                       # ← 拿到写锁
judges = [context_precision(...), context_recall(...), ...]  # ← 每个几秒,写锁被占
s.commit()                      # ← 写锁才释放
```

**修法**:把 5 个 LLM judge 计算移到开 session **之前**,写锁只持「add Trace + flush + add Score + commit」的毫秒级事务。

**原理**:SQLite WAL 模式同一时刻**只有一个写事务**。`busy_timeout` 只是让后到的写等一等,但写锁被占用几秒以上时,等待方必然超时。所以铁律是——**DB 事务要短,IO/LLM 调用绝不能放进事务里**。这条不限于 SQLite,MySQL/PostgreSQL 同样适用(长事务会占锁、拖慢别人)。

## 坑 2:`DetachedInstanceError` —— commit 后别碰 ORM 对象

**现象**:`test_execute_run` 里 run 明明该 done,却变成 failed;还报 `KeyError: 'top_k'`、`DetachedInstanceError`。

**根因**:`run.progress = 0; s.commit()` 会让 ORM 对象 `expire`(所有属性标记为需重新加载),`s.close()` 后对象脱离 session(detached)。之后 `pool.submit(... it.id ...)` 再访问 `it.id`,SQLAlchemy 尝试回库加载 → 已 detached → 抛 `DetachedInstanceError`。

**修法**:commit 前把需要跨 session 用的字段取成普通值:

```python
# 错误:把 ORM 对象 it 传给线程池,commit+close 后再访问 it.id 就炸
# 正确:commit 前拍平成普通元组
items = [(it.id, it.input, it.expected_output, it.bucket) for it in rows]
run.progress = 0
s.commit()
s.close()
```

**原理**:SQLAlchemy `Session` 默认 `expire_on_commit=True`,commit 后对象的列属性失效;对象一旦脱离 session,访问这些属性就会 `DetachedInstanceError`。铁律——**跨 session/跨线程只传普通值(Python 基础类型),不传 ORM 对象**。

## 坑 3:uv 建的 venv 没有 pip

**现象**:`.venv/bin/pip` 不存在,`.venv/bin/python -m pip` 报 `No module named pip`。

**根因**:项目 venv 由 **uv** 创建,uv 不走 pip,所以 venv 里没装 pip。

**修法**:用 uv 装依赖,它会自动更新 `pyproject.toml` 并装进 venv:

```bash
~/.local/bin/uv add "celery[redis]>=5.4.0"
```

**原理**:uv 是新一代 Python 包管理器,以 `pyproject.toml` 为唯一来源,不需要 pip。装依赖用 `uv add`,别用 `pip install`。

## 坑 4:Celery worker 不会热重载

**现象**:改完 `run_service.py` 后重新提交 run,跑的还是旧逻辑,修复像没生效。

**根因**:Celery worker 是**独立进程**,启动时把代码加载进内存;改了 `.py` 文件后,正在跑的 worker 不会自动重新加载。

**修法**:改 worker 相关代码后**重启 worker**:

```bash
# 停掉旧 worker,再起新 worker 加载新代码
.venv/bin/celery -A backend.celery_app worker --pool=threads --concurrency=4 --loglevel=info
```

**原理**:worker 是常驻进程,和 uvicorn/FastAPI 类似,改代码不重启不生效。开发期可加 `--autoreload`,但生产要配合重启机制(容器里 `restart: unless-stopped` + 重新 build)。

## 坑 5:`except` 吞掉异常,失败查不到根因

**现象**:run 置 failed 后,worker 日志只有 `Task evalflow.execute_run[...] succeeded`,**没有任何异常信息**,根因无从查起,只能逐条单独复现。

**根因**:`execute_run` 里 `except Exception: _mark("failed")` 把异常吞了。而且异常在函数内部被捕获,Celery 看到的是「任务正常返回」,所以连 Celery 层都不会报错。

**修法**:catch 了就该 log:

```python
except Exception:
    logging.exception("run %s 执行失败", run_id)  # 打印完整 traceback
    _mark("failed")
```

**原理**:`except Exception` 静默吞掉是最常见的排查噩梦。铁律——**凡是 catch 异常,要么 log(`logging.exception` 会带上 traceback),要么向上抛**,别两头都不占。

## 坑 6:复现 bug 要还原真实环境,否则被假根因带偏

**现象**:复现并发失败时,随手用了不存在的 `run_id=97`,结果 7 条全报 `FOREIGN KEY constraint failed`,一度以为根因是「run 不存在」。

**根因**:那是**复现脚本自己的错**——`Trace.run_id` 有外键约束,插了个不存在的 run 当然外键失败,和真实 bug 无关。真实 bug 是坑 1 的写锁竞争。

**教训**:复现 bug 要完整还原真实环境(真实存在的 run、真实数据、真实并发度);拿到一个错误先核对「是不是我复现脚本引入的」,再往下追。这次差点被自己的脚本带偏。

## 小结

这一章的坑收敛成两条底层规律:

1. **事务边界**——写锁要短,LLM/IO 调用放事务外(坑 1)。
2. **进程/线程边界**——跨 session 传普通值(坑 2)、改代码要重启 worker(坑 4)、catch 必 log(坑 5)。
