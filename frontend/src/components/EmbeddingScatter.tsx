import { Empty } from 'antd'
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import type { KnowledgeChunk, KnowledgeQuery } from '../types'

const COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']

// 悬停显示「这个点是什么」,而不是 PCA 的 x/y 坐标——那两个数字没有绝对意义(Ch23)
type Point = Partial<KnowledgeChunk & KnowledgeQuery>

export default function EmbeddingScatter({ chunks, queries }: { chunks: KnowledgeChunk[]; queries: KnowledgeQuery[] }) {
  if (!chunks.length) return <Empty description="暂无知识库数据" style={{ margin: '0 auto' }} />
  // 按 category 分组,每组一个 Scatter 系列,用不同颜色;query 用叉号叠加
  const cats = Array.from(new Set(chunks.map((c) => c.category)))
  return (
    <ResponsiveContainer width="100%" height={420}>
      <ScatterChart margin={{ top: 16, right: 24, bottom: 16, left: 16 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis type="number" dataKey="x" name="x" />
        <YAxis type="number" dataKey="y" name="y" />
        <Tooltip
          cursor={{ strokeDasharray: '3 3' }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const p = payload[0].payload as Point
            const isChunk = p.category != null
            return (
              <div style={{ background: '#fff', border: '1px solid #eee', borderRadius: 6, padding: 8, fontSize: 12, maxWidth: 320 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {isChunk ? `知识块 · ${p.category}` : `样本问题${p.bucket ? ` · ${p.bucket}` : ''}`}
                </div>
                <div style={{ color: '#444', whiteSpace: 'pre-wrap' }}>{p.text ?? p.input}</div>
              </div>
            )
          }}
        />
        <Legend />
        {cats.map((cat, i) => (
          <Scatter
            key={cat}
            name={cat}
            data={chunks.filter((c) => c.category === cat)}
            fill={COLORS[i % COLORS.length]}
          />
        ))}
        <Scatter name="query" data={queries} fill="#000000" shape="cross" />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
