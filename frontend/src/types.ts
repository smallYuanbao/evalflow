export interface Dataset {
  id: number
  name: string
  description: string
  item_count?: number
  updated_at?: string
}

export interface DatasetPage {
  items: Dataset[]
  total: number
}

export interface DatasetItem {
  id: number
  input: string
  expected_output: string
  bucket: string
  gold_scores?: Record<string, number> | null // Ch18 校准:人工金标准 {metric: score}
}

export interface Run {
  id: number
  dataset_id: number
  status: string
  config?: string // 配置快照 JSON(如 {"top_k": 5}),列表回看用
  progress?: number // 已完成样本数(Ch10 进度)
  created_at?: string
  dataset_name?: string
}

export type BucketStat = { count: number } & Record<string, number | null>

export interface RunDetail {
  id: number
  dataset_id: number
  status: string
  config: string
  progress?: number // 已完成样本数(Ch10 进度)
  item_count: number
  scores: Record<string, number | null> // 指标 key → 均值(动态)
  by_bucket: Record<string, BucketStat>
  // Ch12 费用统计(可选:老 run 无此字段)
  input_tokens?: number
  output_tokens?: number
  cost?: number
}

export interface TraceRow {
  trace_id: number
  input: string
  output: string
  retrieved_context: string
  retrieval_hits?: { text: string; score: number; rank: number }[]
  latency_ms: number
  scores: { name: string; value: number | null; comment?: string }[]  // comment = Judge reason(Ch18)
}

// 逐条 Diff(Ch18):两条 run 按 dataset_item_id 匹配后的并排对比
export interface RunDiffSide {
  trace_id: number
  output: string
  retrieved_context: string
  retrieval_hits?: { text: string; score: number; rank: number }[]
  scores: Record<string, number | null>
}

export interface RunDiffPair {
  item_id: number
  input: string | null
  a: RunDiffSide | null
  b: RunDiffSide | null
  deltas: Record<string, number>
}

export interface RunDiffResult {
  run_a_id: number
  run_b_id: number
  different_datasets: boolean
  pairs: RunDiffPair[]
}

// Judge 校准(Ch18):每 metric 的 judge vs gold 一致性
export interface CalibrationMetric {
  bias: number | null // judge 均值 − gold 均值(系统性偏松/偏严)
  mae: number | null // 平均绝对误差
  corr: number | null // Pearson 相关系数
  n: number // 校准样本数
}

export interface CalibrationResult {
  run_id: number
  metrics: Record<string, CalibrationMetric>
}

// 历史指标趋势(Ch13):单个 run 的 per-metric 均值,用于折线图
export interface RunTrend {
  id: number
  dataset_id: number
  dataset_name?: string
  status: string
  created_at?: string
  scores: Record<string, number | null>
}

// 回归门禁(Ch15):逐指标判定 + 整体结论
export interface GateCheck {
  metric: string
  value: number | null
  threshold: number
  baseline_value: number | null
  delta: number | null
  passed: boolean
  note: string | null
}

export interface GateResult {
  passed: boolean
  checks: GateCheck[]
  run_id: number
  baseline_run_id: number | null
}

export interface KnowledgeChunk {
  id: string
  text: string
  category: string
  x: number
  y: number
}

export interface KnowledgeQuery {
  input: string
  x: number
  y: number
}

export interface KnowledgeMap {
  chunks: KnowledgeChunk[]
  queries: KnowledgeQuery[]
}
