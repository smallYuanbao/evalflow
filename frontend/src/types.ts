export interface Dataset {
  id: number
  name: string
  description: string
  item_count?: number
  updated_at?: string
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
  created_at?: string
  dataset_name?: string
}

export interface BucketStat {
  count: number
  recall_avg: number | null
  faithfulness_avg: number | null
  rejection_rate: number | null
}

export interface RunDetail {
  id: number
  dataset_id: number
  status: string
  config: string
  item_count: number
  scores: {
    recall_avg: number | null
    faithfulness_avg: number | null
    rejection_rate: number | null
  }
  by_bucket: Record<string, BucketStat>
}

export interface TraceRow {
  trace_id: number
  input: string
  output: string
  retrieved_context: string
  latency_ms: number
  scores: { name: string; value: number | null }[]
}
