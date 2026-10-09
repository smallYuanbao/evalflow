import { render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import KnowledgeMapView from '../KnowledgeMapView'

vi.mock('../../api', () => ({
  api: { getKnowledgeMap: vi.fn() },
}))

test('空知识库显示空态', async () => {
  vi.mocked(api.getKnowledgeMap).mockResolvedValue({ chunks: [], queries: [] })
  render(<KnowledgeMapView />)
  await waitFor(() => expect(screen.getByText('暂无知识库数据')).toBeInTheDocument())
})

test('加载失败显示错误兜底', async () => {
  vi.mocked(api.getKnowledgeMap).mockRejectedValue(new Error('boom'))
  render(<KnowledgeMapView />)
  await waitFor(() => expect(screen.getByText('加载失败')).toBeInTheDocument())
})
