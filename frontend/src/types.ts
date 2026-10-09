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
  created_at?: string
  dataset_name?: string
}

export type BucketStat = { count: number } & Record<string, number | null>

export interface RunDetail {
  id: number
  dataset_id: number
  status: string
  config: string
  item_count: number
  scores: Record<string, number | null> // 指标 key → 均值(动态)
  by_bucket: Record<string, BucketStat>
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
