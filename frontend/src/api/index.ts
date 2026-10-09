// 类型化接口方法(不再手写 header,统一走 client)
import { request } from './client'
import type { Dataset, DatasetItem, DatasetPage, KnowledgeMap, Run, RunDetail, TraceRow } from '../types'

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
  createRun: (dataset_id: number) =>
    request<Run>('/runs', { method: 'POST', data: { dataset_id, config: '{}' } }),
  listRuns: (signal?: AbortSignal) => request<Run[]>('/runs', { signal }),
  getRun: (id: number, signal?: AbortSignal) => request<RunDetail>(`/runs/${id}`, { signal }),
  listTraces: (id: number, signal?: AbortSignal) => request<TraceRow[]>(`/runs/${id}/traces`, { signal }),
  getKnowledgeMap: (signal?: AbortSignal) => request<KnowledgeMap>('/knowledge/map', { signal }),
}
