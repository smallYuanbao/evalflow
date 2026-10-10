# Ch11 踩坑:LLM 可靠性(重试 + 熔断)

> 这一章给 LLM 调用装重试 + 熔断 + judge 采样。坑主要在「熔断器和重试怎么不打架」和「测试怎么 mock」。

## 坑 1:openai 异常在测试里极难构造

**现象**:测试要 mock `create` 抛「可重试异常」时,发现大部分 openai 异常构造不出来——`APIConnectionError` 要 request 参数,`RateLimitError`/`InternalServerError` 要 request + response 两个 keyword-only 参数。

**根因**:openai 库的异常继承 `APIStatusError`,构造函数要 httpx 的 Request/Response 对象,测试里造不出来。

**修法**:用唯一能简单构造的 `openai.APITimeoutError("超时")` 代表「可重试异常」,用普通 `ValueError` 代表「不可重试异常」。测试目的是验证重试/熔断的**分支逻辑**,不要求用真实的每个异常子类。

**原理**:单测不用追求「异常完全真实」,只要 `except` 能正确匹配分类即可——可重试的用 APITimeoutError(它正好是 `_RETRYABLE` 成员),不可重试的用非 `_RETRYABLE` 的任意异常。

## 坑 2:熔断器的 before_call 必须放在 try 外面

**现象**:熔断打开后,`chat` 没有抛 `CircuitOpenError` 快速失败,反而被当成「非可重试异常」处理,还调了 `on_success` 把熔断重置了——熔断形同虚设。

**根因**:`before_call()` 如果放在 `try` 块**里面**,它抛的 `CircuitOpenError` 会被后面的 `except Exception` 捕获,走「非可重试 → on_success 重置熔断」分支,熔断刚打开就被关掉。

**修法**:`before_call()` 放在 try 块**外面**,它抛的异常直接往上传播:

```python
for attempt in range(...):
    _circuit.before_call()   # ← 在 try 外,CircuitOpenError 直接冒泡
    try:
        r = _client.chat.completions.create(**kwargs)
        ...
```

**原理**:熔断的「快速失败」信号必须穿透重试循环直达调用方,不能被兜底 except 拦截。**凡是「故意要往外抛」的异常,别放进会被捕获的代码块里。**

## 坑 3:4xx 不是熔断故障,要 on_success 不是 on_failure

**现象**:鉴权错(401)或参数错(400)发生时,如果把它记进熔断器的连续失败计数,几次之后熔断被打开——但服务其实是通的,只是配置错了。

**根因**:熔断的语义是「**服务不可用**才短路」。4xx 是「请求本身错」,说明服务正常响应了。

**修法**:非可重试异常(4xx)分支调 `on_success()`(重置熔断)而不是 `on_failure()`:

```python
except Exception:
    _circuit.on_success()  # 4xx:服务通,不算故障
    raise
```

**原理**:熔断只统计「网络/5xx/429」这类服务端问题。4xx 是配置/参数错误,应该立即暴露给调用方,而不是污染熔断状态。

## 坑 4:熔断阈值要大于单请求重试次数

**现象**:如果熔断阈值设得比「单请求重试次数」小,一个请求重试几次失败就会触发熔断,后续所有请求被快速失败——熔断太敏感、误伤。

**根因**:重试在熔断之内,每次失败都记入熔断器。单请求重试 3 次 = 最多 4 次失败,如果阈值 ≤ 4,单个坏请求就打开熔断。

**修法**:熔断阈值(5)> 单请求最大失败次数(4),保证熔断是「**多个请求连续失败**」的累计触发,不是单请求重试触发。

**原理**:重试管「单个请求的瞬时故障自愈」,熔断管「服务的整体可用性」,两者层次不同,阈值要拉开,否则职责重叠、熔断误伤。

## 坑 5:测试熔断/重试要 mock 时钟和 sleep

**现象**:跑重试测试时退避真的 sleep 了几秒,测试奇慢;测冷却恢复时等不起 30 秒冷却。

**根因**:重试用 `time.sleep` 退避,熔断用 `time.monotonic()` 判断冷却,都是真实时间。

**修法**:测试里 monkeypatch 掉,并重置模块级单例熔断器:

```python
monkeypatch.setattr(llm.time, "sleep", lambda s: None)      # 退避不真等
monkeypatch.setattr(llm.time, "monotonic", lambda: 1000.0)  # 冻结/可控时钟
llm._circuit._reset()  # 每个测试开头隔离共享状态
```

**原理**:凡是涉及「时间」的逻辑,测试都要能注入假时钟,否则要么慢、要么不可测。这也是为什么 CircuitBreaker 用 `time.monotonic()`(测时间差)而非 wall clock。

## 小结

这一章的坑收敛成一句:**熔断和重试是两个层次,别让它们打架**——熔断只管服务可用性(4xx 不算故障)、阈值要高于单请求重试、快速失败信号要穿透重试循环。
