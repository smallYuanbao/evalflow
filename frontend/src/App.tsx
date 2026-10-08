import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import ErrorBoundary from './components/ErrorBoundary'
import DatasetsView from './views/DatasetsView'
import RunsView from './views/RunsView'
import RunDetailView from './views/RunDetailView'
import DatasetDetailView from './views/DatasetDetailView'

export default function App() {
  const location = useLocation()
  // 根据当前 URL 选中 tab,让浏览器前进/后退也能正确切换菜单(问题3)
  const selectedKey = location.pathname.startsWith('/runs') ? 'runs' : 'datasets'
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header>
        <Menu theme="dark" mode="horizontal" selectedKeys={[selectedKey]}>
          <Menu.Item key="datasets">
            <Link to="/datasets">评测集</Link>
          </Menu.Item>
          <Menu.Item key="runs">
            <Link to="/runs">评测记录</Link>
          </Menu.Item>
        </Menu>
      </Layout.Header>
      <Layout.Content style={{ padding: 24 }}>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Navigate to="/datasets" replace />} />
            <Route path="/datasets" element={<DatasetsView />} />
            <Route path="/datasets/:datasetId" element={<DatasetDetailView />} />
            <Route path="/runs" element={<RunsView />} />
            <Route path="/runs/:runId" element={<RunDetailView />} />
          </Routes>
        </ErrorBoundary>
      </Layout.Content>
    </Layout>
  )
}
