import { lazy, Suspense } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout, Menu, Skeleton } from 'antd'
import ErrorBoundary from './components/ErrorBoundary'
import ApiKeyButton from './components/ApiKeyButton'

// 路由级懒加载:按视图拆包,首屏只加载入口 + 当前路由(Ch07 解决 1.4MB 单 chunk 警告)
const DatasetsView = lazy(() => import('./views/DatasetsView'))
const DatasetDetailView = lazy(() => import('./views/DatasetDetailView'))
const RunsView = lazy(() => import('./views/RunsView'))
const RunDetailView = lazy(() => import('./views/RunDetailView'))
const CompareView = lazy(() => import('./views/CompareView'))
const KnowledgeMapView = lazy(() => import('./views/KnowledgeMapView'))

export default function App() {
  const location = useLocation()
  // 根据当前 URL 选中 tab,让浏览器前进/后退也能正确切换菜单(问题3)
  const selectedKey = location.pathname.startsWith('/runs') || location.pathname.startsWith('/compare')
    ? 'runs'
    : location.pathname.startsWith('/knowledge')
      ? 'knowledge'
      : 'datasets'
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header style={{ display: 'flex', alignItems: 'center' }}>
        <Menu theme="dark" mode="horizontal" selectedKeys={[selectedKey]} style={{ flex: 1, minWidth: 0 }}>
          <Menu.Item key="datasets">
            <Link to="/datasets">评测集</Link>
          </Menu.Item>
          <Menu.Item key="runs">
            <Link to="/runs">评测记录</Link>
          </Menu.Item>
          <Menu.Item key="knowledge">
            <Link to="/knowledge">知识库</Link>
          </Menu.Item>
        </Menu>
        <ApiKeyButton />
      </Layout.Header>
      <Layout.Content style={{ padding: 24 }}>
        <ErrorBoundary>
          <Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} style={{ marginTop: 24 }} />}>
            <Routes>
              <Route path="/" element={<Navigate to="/datasets" replace />} />
              <Route path="/datasets" element={<DatasetsView />} />
              <Route path="/datasets/:datasetId" element={<DatasetDetailView />} />
              <Route path="/runs" element={<RunsView />} />
              <Route path="/runs/:runId" element={<RunDetailView />} />
              <Route path="/compare" element={<CompareView />} />
              <Route path="/knowledge" element={<KnowledgeMapView />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </Layout.Content>
    </Layout>
  )
}
