// 指标定义(Ch24):标签 + 人话解释。之前 METRIC_LABELS 在 4 个视图里各抄一份,
// 释义更是哪里都没有——「召回(机械)」和「上下文召回」光看名字根本分不清,得能悬停看说明。

export const METRIC_LABELS: Record<string, string> = {
  recall: '召回(机械)',
  hit_at_k: '命中@k',
  mrr: 'MRR',
  context_precision: '上下文精度',
  context_recall: '上下文召回',
  faithfulness: '忠实度',
  answer_relevance: '答案相关性',
  answer_correctness: '答案正确性',
  rejection: '拒答率',
}

/** 指标 key → 一句话解释(悬停 tooltip 用) */
export const METRIC_DESC: Record<string, string> = {
  recall: '机械指标(不调 LLM):标准答案要点在检索到的证据里命中了多少',
  hit_at_k: '机械指标:top-k 检索结果里是否命中了相关文档(0 或 1)',
  mrr: '机械指标:第一个相关文档排名的倒数——越靠前越接近 1',
  context_precision: 'LLM 裁判:检索到的证据里真正有用的占比(噪声多不多)',
  context_recall: 'LLM 裁判:回答问题所需的要点被证据覆盖了多少(有没有漏检)',
  faithfulness: 'LLM 裁判:回答是否忠于证据、没有编造夸大',
  answer_relevance: 'LLM 裁判:回答是否切题,有没有答非所问',
  answer_correctness: 'LLM 裁判:回答与标准答案要点是否语义一致',
  rejection: '机械指标:库外题是否正确地拒答(命中拒答词记 1)',
}

export const METRIC_ORDER = Object.keys(METRIC_LABELS)

export const metricLabel = (k: string) => METRIC_LABELS[k] ?? k
export const metricDesc = (k: string) => METRIC_DESC[k] ?? ''
