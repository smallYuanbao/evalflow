# Ch01 踩坑:SQLite 数据地基

> 这一章建 6 张表 + 起 SQLAlchemy ORM。坑都在「SQLite 和别的数据库不一样」上。

## 坑 1:SQLite 默认不开启外键约束

**现象**:插一条 `dataset_id=99999`(不存在的评测集)的孤儿样本,居然 commit 成功——外键形同虚设。

**根因**:SQLite 的 `foreign_keys` 默认是 **OFF**(为了向后兼容),而且它是**连接级**设置,不是库级——换一个连接就失效了。

**修法**:在 SQLAlchemy 的 `connect` 事件里,每个新连接都开一次:

```python
@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

**原理**:MySQL/PostgreSQL 外键默认强制,SQLite 偏偏默认关。`PRAGMA` 是 per-connection 的,所以用 `connect` 事件「每个连接进来都设一遍」,而不是在别处设一次就以为生效。配套写一条反向测试(插孤儿数据断言 `IntegrityError`)锁死这个行为。

## 坑 2:SQLite 不自动创建目录

**现象**:`sqlite:///data/eval.db`,当 `data/` 目录不存在时,连接直接报错。

**根因**:SQLite 只负责读写**文件**,不会像某些数据库那样自动建目录。

**修法**:建 engine 前先确保父目录存在:

```python
def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///"):
        db_path = url[len("sqlite:///"):]
        if db_path and db_path != ":memory:":
            parent = Path(db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
```

## 坑 3:跨线程访问 SQLite 连接

**现象**:多线程/线程池里用同一个连接会报 `SQLite objects created in a thread can only be used in that same thread`。

**根因**:SQLAlchemy 对 SQLite 默认 `check_same_thread=True`,连接被限制在创建它的线程内。

**修法**:

```python
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite 单文件,允许跨线程
)
```

**原理**:这条当时只是「先设上」,但到了 Ch10 用线程池并发跑样本时,它就是能不能跑的命门。**早期埋的坑/伏笔,后面对并发时才会兑现**——基础设施层要提前想清楚并发场景。

## 坑 4:`scores.value` 用 NULL 还是 0

**现象**:评测分数里,「judge 调用失败没评上」和「评出来就是 0 分」是两回事,如果都记 0,均值会被拉低、误报成「质量差」。

**根因**:这是数据语义问题——**「没评上」≠「零分」**。

**修法**:`value` 列设 `nullable=True`,judge 失败记 `NULL`,聚合时**跳过 NULL 只对真实分数求均值**。

```python
value = Column(Float, nullable=True)  # NULL = 没评上(别记 0)
```

**原理**:这是「评测/埋点类系统」的通用设计:真实值、缺失值、零值要严格区分。NULL 让「失败样本」不参与聚合,不污染结果——这条贯穿 Ch02、Ch05,是理解后续所有「judge 失败记 NULL」的根。
