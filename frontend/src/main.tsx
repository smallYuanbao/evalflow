import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/es/locale/zh_CN' // 走 ESM 入口:antd/locale/zh_CN 是 CJS,dev 下 interop 拿到的不是 locale 本身
import 'antd/dist/reset.css'
import App from './App.tsx'

// ConfigProvider locale 是全局文案的根因(Ch23):不配的话弹窗按钮是 OK/Cancel、
// 分页器/空态也是英文。配一次,所有 antd 组件都走中文,不用逐个弹窗写 okText。
createRoot(document.getElementById('root')!).render(
  <ConfigProvider locale={zhCN}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ConfigProvider>,
)
