import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import DatasetDetailView from '../DatasetDetailView'

vi.mock('../../api', () => ({
  api: { getDataset: vi.fn(), listItems: vi.fn().mockResolvedValue([]), setItemGold: vi.fn() },
}))

test('展示评测集名称与加样本表单', async () => {
  vi.mocked(api.getDataset).mockResolvedValue({ id: 1, name: '育儿', description: '', item_count: 7 })
  render(
    <MemoryRouter initialEntries={['/datasets/1']}>
      <Routes>
        <Route path="/datasets/:datasetId" element={<DatasetDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('育儿')).toBeInTheDocument())
  expect(screen.getByPlaceholderText('问题')).toBeInTheDocument()
})

test('问题为空时加样本按钮禁用', async () => {
  vi.mocked(api.getDataset).mockResolvedValue({ id: 1, name: '育儿', description: '', item_count: 7 })
  render(
    <MemoryRouter initialEntries={['/datasets/1']}>
      <Routes>
        <Route path="/datasets/:datasetId" element={<DatasetDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('育儿')).toBeInTheDocument())
  expect(screen.getByRole('button', { name: '加样本' })).toBeDisabled()
})

test('点标金标准打开标注弹窗(Ch18)', async () => {
  vi.mocked(api.getDataset).mockResolvedValue({ id: 1, name: '育儿', description: '', item_count: 1 })
  vi.mocked(api.listItems).mockResolvedValue([
    { id: 1, input: '宝宝发烧', expected_output: '物理降温/就医', bucket: '护理', gold_scores: { faithfulness: 0.9 } },
  ])
  render(
    <MemoryRouter initialEntries={['/datasets/1']}>
      <Routes>
        <Route path="/datasets/:datasetId" element={<DatasetDetailView />} />
      </Routes>
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('宝宝发烧')).toBeInTheDocument())
  expect(screen.getByText(/忠实度=0\.9/)).toBeInTheDocument() // 金标准列
  fireEvent.click(screen.getByRole('button', { name: '标金标准' }))
  await waitFor(() => expect(screen.getByText(/标金标准 —/)).toBeInTheDocument())
  expect(screen.getByText('忠实度')).toBeInTheDocument() // 弹窗里的指标标签
})
