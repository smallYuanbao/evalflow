import '@testing-library/jest-dom/vitest'

// antd 在 jsdom 下需要 matchMedia,补 stub(测 antd 的必备 gotcha)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// recharts 的 ResponsiveContainer 依赖 ResizeObserver,jsdom 没有,补最小实现
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub
