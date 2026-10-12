"""BM25 稀疏检索(Ch16):给混合检索提供「关键词精确匹配」一路。

dense(向量)管语义相近,BM25 管字面命中——商品名/编号/专业术语这类「必须对上」的词,
纯向量会漏,BM25 不会。中文无空格,这里用字符二元组(bigram)当词;生产一般上 jieba 分词 + 停用词。
手写 BM25 是为了把公式讲透,小语料下与 jieba 相当。
"""
import math


def _tokenize(text: str) -> list[str]:
    """字符 bigram 分词:中文无空格,二元组能捕获「发烧」「湿疹」这类双字关键词。"""
    t = text.strip()
    if len(t) <= 1:
        return [t] if t else []
    return [t[i:i + 2] for i in range(len(t) - 1)]


class BM25:
    """标准 Okapi BM25:词频(f)+ 文档频率/IDF + 长度归一化(|D|/avgdl)。"""

    def __init__(self, docs: list[dict], k1: float = 1.5, b: float = 0.75):
        self.docs = docs                     # [{id, text, ...}]
        self.k1, self.b = k1, b
        self.doc_tokens = [_tokenize(d["text"]) for d in docs]
        self.doc_len = [len(t) for t in self.doc_tokens]
        self.avgdl = sum(self.doc_len) / len(docs) if docs else 0.0
        self.n = len(docs)
        # 词 → 出现该词的文档数(文档频率),IDF 用
        self.df: dict[str, int] = {}
        for toks in self.doc_tokens:
            for term in set(toks):
                self.df[term] = self.df.get(term, 0) + 1

    def _idf(self, term: str) -> float:
        # 标准平滑 IDF:log((N - n + 0.5)/(n + 0.5) + 1),保证 n=0 时也不为负
        n_t = self.df.get(term, 0)
        return math.log((self.n - n_t + 0.5) / (n_t + 0.5) + 1)

    def search(self, query: str, top_k: int = 2) -> list[tuple[str, str, float]]:
        """返回 [(id, text, bm25_score)],按分数降序;无命中的返回空。"""
        q_tokens = _tokenize(query)
        scored: list[tuple[str, str, float]] = []
        for i, toks in enumerate(self.doc_tokens):
            score = 0.0
            for term in q_tokens:
                f = toks.count(term)
                if f == 0:
                    continue
                idf = self._idf(term)
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / max(self.avgdl, 1e-9))
                score += idf * (f * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((self.docs[i]["id"], self.docs[i]["text"], score))
        scored.sort(key=lambda x: -x[2])
        return scored[:top_k]
