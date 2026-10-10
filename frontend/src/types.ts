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
  scores: { name: string; value: number | null }[]
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
