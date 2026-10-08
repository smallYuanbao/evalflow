import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { api } from '../../api'
import DatasetsView from '../DatasetsView'

vi.mock('../../api', () => ({
  api: { listDatasets: vi.fn() },
}))

test('渲染评测集列表', async () => {
  vi.mocked(api.listDatasets).mockResolvedValue([{ id: 1, name: '育儿', description: '', item_count: 7 }])
  render(
    <MemoryRouter>
      <DatasetsView />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('育儿')).toBeInTheDocument())
})

test('加载失败显示错误兜底', async () => {
  vi.mocked(api.listDatasets).mockRejectedValue(new Error('boom'))
  render(
    <MemoryRouter>
      <DatasetsView />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('加载失败')).toBeInTheDocument())
})

test('新建评测集名称为空时确认按钮禁用', async () => {
  vi.mocked(api.listDatasets).mockResolvedValue([{ id: 1, name: '育儿', description: '', item_count: 7 }])
  render(
    <MemoryRouter>
      <DatasetsView />
    </MemoryRouter>,
  )
  await waitFor(() => expect(screen.getByText('育儿')).toBeInTheDocument())
  fireEvent.click(screen.getByText('新建评测集'))
  const ok = await screen.findByRole('button', { name: 'OK' })
  expect(ok).toBeDisabled()
})
