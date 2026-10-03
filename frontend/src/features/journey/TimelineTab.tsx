import { AlertTriangle, Check, Clock, Info } from 'lucide-react'
import { motion } from 'framer-motion'
import { SaarthiMark } from '../../components/ui'
import { PARTNER_SHORT, relDay, time } from '../../services/format'
import type { TimelineEvent } from '../../services/types'

function actorTag(e: TimelineEvent) {
  if (e.actor === 'saarthi') return 'Saarthi'
  if (e.actor === 'user') return 'You'
  if (e.actor === 'system') return 'App'
  return PARTNER_SHORT[e.actor] ?? e.actor
}

export function TimelineTab({ events }: { events: TimelineEvent[] }) {
  let lastDay = ''
  return (
    <div className="card">
      <div className="tl">
        {events.map((e, i) => {
          const day = relDay(e.ts)
          const showDay = day !== lastDay
          lastDay = day
          const saarthi = e.actor === 'saarthi'
          return (
            <div key={e.id}>
              {showDay && <div className="tl-day">{day}</div>}
              <motion.div className="tl-item" initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i * 0.03, 0.4) }}>
                <div className="tl-line" />
                <div className="tl-time num">{time(e.ts)}</div>
                {saarthi ? <div className="tl-node saarthi" style={{ background: 'none' }}><SaarthiMark size={22} /></div>
                  : <div className={`tl-node ${e.status}`}>
                    {e.status === 'failed' ? <AlertTriangle size={12} /> : e.status === 'info' ? <Info size={12} /> : e.status === 'waiting' ? <Clock size={12} /> : <Check size={12} strokeWidth={3} />}
                  </div>}
                <div>
                  <div className="tl-title">{e.title}{e.status === 'failed' ? ' ⚠' : ''}</div>
                  {e.detail && <div className={`tl-detail ${/^[A-Z0-9_]+$/.test(e.detail) ? 'mono' : ''}`}>{e.detail}</div>}
                  <div className="tl-tags">
                    <span className="chip">{actorTag(e)}</span>
                    <span className="chip" style={{ textTransform: 'capitalize' }}>{e.loop_stage}</span>
                  </div>
                </div>
              </motion.div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
