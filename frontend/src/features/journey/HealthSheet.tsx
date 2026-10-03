import { HealthRing, Sheet } from '../../components/ui'
import type { Health } from '../../services/types'

export function HealthSheet({ open, onClose, health }: { open: boolean; onClose: () => void; health: Health }) {
  const factors = [...health.factors].sort((a, b) => a.impact - b.impact)
  const sum = health.factors.reduce((s, f) => s + f.impact, 0)
  return (
    <Sheet open={open} onClose={onClose} title={`Why is my Journey Health ${health.score}?`}>
      <div className="row" style={{ gap: 16, marginBottom: 6 }}>
        <HealthRing score={health.score} size={76} />
        <div className="grow">
          <div style={{ fontWeight: 700, fontSize: 15 }}>{health.band.label}</div>
          <div className="muted" style={{ fontSize: 12.5, marginTop: 3, lineHeight: 1.45 }}>
            Deterministic score — every point comes from a rule over verified journey data. No guesswork.
          </div>
        </div>
      </div>
      <div className="divider" />
      <div className="factor">
        <div className="fl">Base score<div className="fd">Every journey starts here</div></div>
        <div className="fv">{health.base}</div>
      </div>
      {factors.map(f => (
        <div key={f.key} className="factor">
          <div className="fl">{f.label}{f.detail && <div className="fd">{f.detail}</div>}</div>
          <div className={`fv ${f.impact > 0 ? 'pos' : 'neg'}`}>{f.impact > 0 ? '+' : ''}{f.impact}</div>
        </div>
      ))}
      <div className="formula">
        <span className="muted">{health.base} {sum >= 0 ? '+' : '−'} {Math.abs(sum)}{health.base + sum !== health.score ? ' (capped 0–100)' : ''}</span>
        <span style={{ fontSize: 15, fontWeight: 800 }}>= {health.score} / 100</span>
      </div>
    </Sheet>
  )
}
