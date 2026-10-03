import { useState } from 'react'
import { JsonView } from '../../components/ui'
import { dateTime } from '../../services/format'
import type { AuditEntry } from '../../services/types'

const ACTOR: Record<string, string> = {
  saarthi: 'Saarthi', diagnosis_engine: 'Diagnosis engine', decision_engine: 'Decision engine', safety_engine: 'Safety engine',
  action_engine: 'Action engine', health_engine: 'Health engine', user: 'You',
}

export function AuditList({ entries, compact = false }: { entries: AuditEntry[]; compact?: boolean }) {
  const [open, setOpen] = useState<number | null>(null)
  if (!entries.length) return <div className="empty">No audit events yet.</div>
  return (
    <>
      {entries.map(a => (
        <button key={a.id} className="audit-item" style={{ width: '100%', textAlign: 'left', display: 'block' }} onClick={() => setOpen(open === a.id ? null : a.id)}>
          <div className="between">
            <span className={`audit-type ${a.event_type}`}>{a.event_type.replace('_', ' ')}</span>
            <span className="muted num" style={{ fontSize: 11 }}>{dateTime(a.ts)}</span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, marginTop: 6, lineHeight: 1.4 }}>{a.summary}</div>
          <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>{ACTOR[a.actor] ?? a.actor}{!compact && ' · tap for record'}</div>
          {open === a.id && !compact && <JsonView data={a.data} />}
        </button>
      ))}
    </>
  )
}

export function AuditTab({ entries }: { entries: AuditEntry[] }) {
  return (
    <div className="card">
      <div style={{ padding: '12px 14px 4px' }}>
        <div className="card-title">Saarthi audit log</div>
        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>Every perception, decision and action is recorded — immutable, newest first.</div>
      </div>
      <AuditList entries={entries} />
    </div>
  )
}
