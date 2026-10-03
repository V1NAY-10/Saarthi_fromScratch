import { motion } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import { useApp } from '../hooks/useApp'
import { inr } from '../services/format'
import type { Journey } from '../services/types'
import { CategoryIcon, HealthPill, SaarthiMark, StatusPill } from './ui'

/** Human copy for an interrupted journey, keyed by normalized failure type. */
export function issueCopy(j: Journey) {
  const ft = j.saarthi?.failure_type
  if (j.status === 'ESCALATED') return { status: 'With a specialist', tone: 'var(--warn)', line: 'Saarthi handed this over with the full case file.', cta: 'View case' }
  if (j.status === 'RESOLVED') return { status: 'Resolved by Saarthi', tone: 'var(--ok)', line: 'Recovered and verified with the bank.', cta: 'View' }
  if (j.status === 'ATTENTION' && (!j.saarthi || j.agent_status === 'RUNNING')) return { status: 'Saarthi is investigating', tone: 'var(--brand)', line: 'The agent is checking with the bank right now.', cta: 'Watch' }
  if (j.status === 'ATTENTION' && j.stage === 'Waiting for a top-up') return { status: 'Waiting for a top-up', tone: 'var(--warn)', line: 'Saarthi will re-plan as soon as money arrives.', cta: 'Open' }
  if (ft === 'PAYMENT_FAILURE') return { status: 'Payment unsuccessful', tone: 'var(--bad)', line: 'Saarthi found the reason.', cta: 'Understand & fix' }
  if (ft === 'MANDATE_LIMIT') return { status: 'Above autopay limit', tone: 'var(--bad)', line: 'Saarthi found the reason.', cta: 'Understand & fix' }
  if (ft === 'ACCOUNT_VERIFICATION') return { status: 'Account not verified', tone: 'var(--bad)', line: j.saarthi?.tier === 'TIER_3' ? 'Needs a human check.' : 'Saarthi can prove ownership.', cta: 'Resolve' }
  return { status: j.stage, tone: 'var(--ink-2)', line: '', cta: 'Open' }
}

export function AttentionCard({ j, index = 0 }: { j: Journey; index?: number }) {
  const { push } = useApp()
  const c = issueCopy(j)
  return (
    <motion.div className="card card-saarthi jcard tap" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }} onClick={() => push({ name: 'journey', id: j.id })} style={{ cursor: 'pointer' }}>
      <div className="jcard-top">
        <CategoryIcon category={j.category} />
        <div className="grow">
          <div className="between">
            <div className="title">{j.title}</div>
            {j.amount > 0 && <div className="amount num">{inr(j.amount)}</div>}
          </div>
          <div className="status-line" style={{ color: c.tone }}>{c.status}</div>
          <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>{j.partner_name} · {j.subtitle}</div>
        </div>
      </div>
      <div className="saarthi-says">
        <SaarthiMark size={20} />
        <div className="t">{c.line}</div>
        <button className="btn btn-primary btn-sm" onClick={e => { e.stopPropagation(); push({ name: 'journey', id: j.id }) }}>{c.cta}</button>
      </div>
    </motion.div>
  )
}

export function JourneyRow({ j }: { j: Journey }) {
  const { push } = useApp()
  return (
    <button className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'journey', id: j.id })}>
      <CategoryIcon category={j.category} size={36} />
      <div className="grow">
        <div className="t">{j.title}</div>
        <div className="s">{j.partner_name} · {j.stage}</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <HealthPill score={j.health_score} />
        <div style={{ marginTop: 4 }}><StatusPill status={j.status} /></div>
      </div>
    </button>
  )
}

/** Contextual Saarthi strip embedded in host-app screens (Invest / Loans / Insure). */
export function SaarthiStrip({ j }: { j: Journey }) {
  const { push } = useApp()
  const c = issueCopy(j)
  const text = j.status === 'ATTENTION' ? <><b>{c.status}.</b> {j.saarthi ? j.saarthi.summary.split('. ')[0] + '.' : c.line}</>
    : j.status === 'RESOLVED' ? <><b>Resolved.</b> Saarthi recovered this journey and verified it with {j.partner_name}.</>
      : j.status === 'ESCALATED' ? <><b>With a specialist.</b> Saarthi shared the full case so you won't repeat anything.</>
        : <><b>No action needed.</b> Saarthi is watching this journey.</>
  return (
    <button className="saarthi-strip tap" style={{ width: '100%', textAlign: 'left', marginTop: 12 }} onClick={() => push({ name: 'journey', id: j.id })}>
      <SaarthiMark size={22} />
      <div className="t grow">{text}</div>
      <ChevronRight size={16} color="var(--brand)" />
    </button>
  )
}
