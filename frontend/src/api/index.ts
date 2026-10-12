// 类型化接口方法(不再手写 header,统一走 client)
import { request } from './client'
import type { BucketAttributionResult, CalibrationResult, Dataset, DatasetItem, DatasetPage, GateResult, KnowledgeMap, ModelComparison, Run, RunDetail, RunDiffResult, RunTrend, TraceRow } from '../types'

export const api = {
  // 读接口都收 signal(useRequest 用来打断上次请求);写接口一次性触发,不收
  listDatasets: (params: { page?: number; page_size?: number; search?: string } = {}, signal?: AbortSignal) => {
    const qs = new URLSearchParams()
    qs.set('page', String(params.page ?? 1))
    qs.set('page_size', String(params.page_size ?? 10))
    if (params.search) qs.set('search', params.search)
    return request<DatasetPage>(`/datasets?${qs}`, { signal })
  },
  createDataset: (name: string, description: string) =>
    request<Dataset>('/datasets', { method: 'POST', data: { name, description } }),
  listItems: (id: number, signal?: AbortSignal) =>
    request<DatasetItem[]>(`/datasets/${id}/items`, { signal }),
  getDataset: (id: number, signal?: AbortSignal) => request<Dataset>(`/datasets/${id}`, { signal }),
  addItem: (id: number, body: { input: string; expected_output: string; bucket: string }) =>
    request<DatasetItem>(`/datasets/${id}/items`, { method: 'POST', data: body }),
  setItemGold: (datasetId: number, itemId: number, goldScores: Record<string, number>) =>
    request<{ id: number; gold_scores: Record<string, number> }>(`/datasets/${datasetId}/items/${itemId}/gold`, {
      method: 'PUT',
      data: { gold_scores: goldScores },
    }),
  createRun: (dataset_id: number, config?: { top_k?: number; retrieval?: 'dense' | 'hybrid' }) =>
    request<Run>('/runs', { method: 'POST', data: { dataset_id, config: JSON.stringify(config ?? {}) } }),
  listRuns: (signal?: AbortSignal) => request<Run[]>('/runs', { signal }),
  getRun: (id: number, signal?: AbortSignal) => request<RunDetail>(`/runs/${id}`, { signal }),
  listRunsTrend: (dataset_id?: number, signal?: AbortSignal) =>
    request<RunTrend[]>(`/runs/trend${dataset_id != null ? `?dataset_id=${dataset_id}` : ''}`, { signal }),
  getRunGate: (id: number, baselineId?: number, signal?: AbortSignal) => {
    const qs = baselineId != null ? `?baseline_run_id=${baselineId}` : ''
    return request<GateResult>(`/runs/${id}/gate${qs}`, { signal })
  },
  exportRunCsv: (id: number) => request<string>(`/runs/${id}/export`),
  getRunDiff: (a: number, b: number, signal?: AbortSignal) => request<RunDiffResult>(`/runs/${a}/diff/${b}`, { signal }),
  getRunCalibration: (id: number, signal?: AbortSignal) => request<CalibrationResult>(`/runs/${id}/calibration`, { signal }),
  getBucketAttribution: (id: number, baselineId: number, signal?: AbortSignal) =>
    request<BucketAttributionResult>(`/runs/${id}/bucket-attribution?baseline_run_id=${baselineId}`, { signal }),
  getModelComparison: (signal?: AbortSignal) => request<{ models: ModelComparison[] }>('/runs/model-comparison', { signal }),
  listTraces: (id: number, signal?: AbortSignal) => request<TraceRow[]>(`/runs/${id}/traces`, { signal }),
  getKnowledgeMap: (signal?: AbortSignal) => request<KnowledgeMap>('/knowledge/map', { signal }),
}
