import { render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import ModelCompareView from '../ModelCompareView'

vi.mock('../../api', () => ({
  api: { getModelComparison: vi.fn() },
}))

test('展示模型性价比对比(Ch19)', async () => {
  vi.mocked(api.getModelComparison).mockResolvedValue({
    models: [
      { model: 'deepseek-chat', run_count: 2, avg_cost: 0.001, avg_cost_per_item: 0.0005, avg_scores: { faithfulness: 0.85 } },
      { model: 'gpt-4o', run_count: 1, avg_cost: 0.02, avg_cost_per_item: 0.01, avg_scores: { faithfulness: 0.95 } },
    ],
  })
  render(<ModelCompareView />)
  await waitFor(() => expect(screen.getByText('deepseek-chat')).toBeInTheDocument())
  expect(screen.getByText('gpt-4o')).toBeInTheDocument()
  expect(screen.getByText('单条成本(元)')).toBeInTheDocument()
})
