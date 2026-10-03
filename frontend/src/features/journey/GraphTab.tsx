import { motion } from 'framer-motion'
import type { Diagnosis, GraphData, GraphNode } from '../../services/types'

const KIND: Record<string, string> = {
  partner: 'Partner', status: 'Partner status', failure: 'Failure type', cause: 'Root cause',
  evidence: 'Evidence', action: 'Action', outcome: 'Expected outcome', equivalent: 'Same failure',
}

const W = 356, NODE_W = 206, NODE_H = 50, GAP = 26, X = 8, EQ_X = 236, EQ_W = 112

function style(n: GraphNode) {
  switch (n.state) {
    case 'done': return { stroke: '#0a5bd3', fill: '#ffffff', text: '#0b1b33' }
    case 'active': return { stroke: '#0a5bd3', fill: '#eaf1fd', text: '#06275e' }
    case 'warn': return { stroke: '#c97a00', fill: '#fff4dd', text: '#7a4a00' }
    case 'pending': return { stroke: '#b4bfce', fill: '#f7f9fc', text: '#44546c' }
    default: return { stroke: '#cfd8e4', fill: '#f7f9fc', text: '#8593a8' }
  }
}

export function GraphTab({ graph, diag }: { graph: GraphData | null; diag: Diagnosis | null }) {
  if (!graph || !graph.nodes.length || !diag) return <div className="card empty">No failure graph — this journey has no interruption.</div>
  const main = graph.nodes.filter(n => n.kind !== 'equivalent')
  const eqs = graph.nodes.filter(n => n.kind === 'equivalent')
  const pos: Record<string, { x: number; y: number; w: number }> = {}
  main.forEach((n, i) => { pos[n.id] = { x: X, y: 10 + i * (NODE_H + GAP), w: NODE_W } })
  const fy = pos['failure']?.y ?? 0
  eqs.forEach((n, i) => { pos[n.id] = { x: EQ_X, y: fy - 34 + i * (NODE_H + 18), w: EQ_W } })
  const H = 10 + main.length * (NODE_H + GAP)

  return (
    <div className="card">
      <div style={{ padding: '14px 14px 0' }}>
        <div className="card-title">Saarthi Failure Knowledge Graph</div>
        <div className="muted" style={{ fontSize: 12, marginTop: 2, lineHeight: 1.45 }}>
          How Saarthi turned <span className="mono">{diag.partner.raw_code}</span> into a recovery. Grey nodes are other partners' codes that mean the same thing.
        </div>
      </div>
      <div className="graph-wrap">
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
          <defs>
            <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill="#8fb3ea" />
            </marker>
          </defs>
          {graph.edges.map((e, i) => {
            const a = pos[e.from], b = pos[e.to]
            if (!a || !b) return null
            if (e.label === 'same failure') {
              const x1 = a.x, y1 = a.y + NODE_H / 2, x2 = b.x + b.w, y2 = b.y + NODE_H / 2
              return <motion.path key={i} d={`M${x1},${y1} C${x1 - 12},${y1} ${x2 + 12},${y2} ${x2 + 2},${y2}`} stroke="#cfd8e4" strokeDasharray="4 4" strokeWidth={1.5} fill="none" markerEnd="url(#arr)"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.9, duration: 0.5 }} />
            }
            const x = a.x + 26, y1 = a.y + NODE_H, y2 = b.y - 2
            return (
              <g key={i}>
                <motion.line x1={x} y1={y1} x2={x} y2={y2} stroke="#8fb3ea" strokeWidth={2} markerEnd="url(#arr)"
                  initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: i * 0.12, duration: 0.3 }} />
                <text x={x + 10} y={(y1 + y2) / 2 + 4} fontSize="10" fill="#8593a8" fontWeight="600">{e.label}</text>
              </g>
            )
          })}
          {graph.nodes.map((n, i) => {
            const p = pos[n.id]
            const s = style(n)
            return (
              <motion.g key={n.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}>
                <rect x={p.x} y={p.y} width={p.w} height={NODE_H} rx={11} fill={s.fill} stroke={s.stroke} strokeWidth={1.5}
                  strokeDasharray={n.state === 'pending' || n.state === 'ghost' ? '4 3' : undefined} />
                <foreignObject x={p.x + 10} y={p.y + 5} width={p.w - 20} height={NODE_H - 8}>
                  <div style={{ fontFamily: 'Inter, sans-serif', lineHeight: 1.2 }}>
                    <div style={{ fontSize: 8.5, fontWeight: 800, letterSpacing: '0.07em', textTransform: 'uppercase', color: '#8593a8' }}>
                      {n.kind === 'equivalent' ? n.sub : KIND[n.kind]}{n.kind === 'action' && n.sub ? ` · ${n.sub.replace('_', ' ')}` : ''}
                    </div>
                    <div style={{ fontSize: n.kind === 'status' || n.kind === 'equivalent' ? 10.5 : 11.5, fontWeight: 700, color: s.text, marginTop: 2, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', fontFamily: n.kind === 'status' || n.kind === 'equivalent' ? 'ui-monospace, Consolas, monospace' : undefined }}>
                      {n.label}
                    </div>
                  </div>
                </foreignObject>
              </motion.g>
            )
          })}
        </svg>
      </div>
      <div className="graph-legend">
        <span><i style={{ background: '#fff', border: '1.5px solid #0a5bd3' }} />Verified</span>
        <span><i style={{ background: '#eaf1fd', border: '1.5px solid #0a5bd3' }} />In progress</span>
        <span><i style={{ background: '#fff4dd', border: '1.5px solid #c97a00' }} />Unconfirmed</span>
        <span><i style={{ background: '#f7f9fc', border: '1.5px dashed #b4bfce' }} />Pending / cross-partner</span>
      </div>
      <div className="divider" style={{ margin: '0 14px' }} />
      <div style={{ padding: '10px 14px 14px' }}>
        <div className="eyebrow">Partner rule (retrieved)</div>
        <div style={{ fontSize: 13, fontWeight: 700, marginTop: 6 }}>{diag.kb_entry.title}</div>
        <div className="muted" style={{ fontSize: 12, marginTop: 4, lineHeight: 1.5 }}>{diag.kb_entry.body}</div>
        {diag.learned && (
          <div className="kv" style={{ marginTop: 10 }}>
            <span className="k">Seen across journeys</span><span className="v num">{diag.learned.occurrences.toLocaleString('en-IN')}</span>
            <span className="k">Resolved via this path</span><span className="v num">{(diag.learned.success_rate * 100).toFixed(1)}%</span>
            <span className="k">Avg. resolution time</span><span className="v num">{diag.learned.avg_resolution_s < 3600 ? `${Math.round(diag.learned.avg_resolution_s)}s` : `${(diag.learned.avg_resolution_s / 3600).toFixed(1)}h`}</span>
          </div>
        )}
      </div>
    </div>
  )
}
