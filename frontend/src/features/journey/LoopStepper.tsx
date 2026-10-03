import { Check } from 'lucide-react'
import type { LoopStage } from '../../services/types'

const LABEL: Record<string, string> = {
  perceive: 'Perceive', diagnose: 'Diagnose', decide: 'Decide', act: 'Act', verify: 'Verify', learn: 'Learn',
}

export function LoopStepper({ loop }: { loop: LoopStage[] }) {
  const done = loop.filter(s => s.state === 'done').length
  const pct = Math.max(0, Math.min(1, (done - 1) / (loop.length - 1)))
  return (
    <div className="loop">
      <div className="loop-line"><i style={{ width: `${pct * 100}%` }} /></div>
      {loop.map(s => (
        <div key={s.stage} className={`loop-step ${s.state}`}>
          <div className="loop-dot">
            {s.state === 'done' ? <Check size={12} strokeWidth={3.5} /> : s.state === 'current' ? <i /> : null}
          </div>
          <div className="loop-label">{LABEL[s.stage]}</div>
        </div>
      ))}
    </div>
  )
}
