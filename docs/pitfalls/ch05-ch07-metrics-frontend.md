# Ch05-07 踩坑:指标深化 · 多 run 对比 · 前端增强

> 这三章坑不多,多是前面章节坑的延续和一次小重构。合在一篇记。

## Ch05:LLM judge 的 NULL 聚合(延续)

**要点**:新增 5 个 LLM judge 后,「judge 失败记 NULL、聚合跳过 NULL」的规则贯穿所有指标。实现时把聚合改成**按指标注册表动态遍历**,而不是硬编码指标名——否则每加一个指标都要改一堆聚合代码。

```python
# 聚合一次 run 的分数:按指标注册表动态遍历,不再硬编码指标名
# judge 挂(NULL)不参与均值
```

**原理**:指标会越来越多,把「有哪些指标」收敛成一份注册表(单一事实来源),聚合/分桶/前端都从它遍历,加指标只改一处。这是「消除硬编码」的典型场景。

## Ch06:config 解析失败要回退默认值

**要点**:`_config_top_k()` 从 `run.config`(JSON 字符串)里取 `top_k`,但老数据可能没有这个字段、config 可能是空串或坏 JSON。不处理会 `KeyError`/`JSONDecodeError` 直接炸。

```python
def config_top_k(config_str: str) -> int:
    try:
        return int(json.loads(config_str or "{}").get("top_k", 2))
    except (TypeError, ValueError, json.JSONDecodeError):
        return 2
```

**原理**:**读「可能缺失/损坏」的外部数据(用户输入、历史数据、配置字符串)必须做容错回退**,不能假设它一定符合预期。缺省值选一个合理默认(这里是 top_k=2)。

## Ch07:无实质坑

这章是把分桶图指标从写死的 `recall` 改成通用 `value` 字段(参数泛化),纯重构、无新坑。略。

## 小结

坑少的章节,往往不是「没踩坑」,而是**前面的坑已经挡住了这类问题**(NULL 语义、config 容错在前面埋好了)。这也说明:前几章把地基打对,后面加功能就顺。
