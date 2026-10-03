import { motion } from 'framer-motion'
import { Activity, BookOpen, ChevronRight, FileText, MessageCircle } from 'lucide-react'
import { issueCopy } from '../components/journey'
import { CategoryIcon, HealthPill, HealthRing, SaarthiMark, Skeleton } from '../components/ui'
import { useApp } from '../hooks/useApp'
import { ago } from '../services/format'

const EVENT_ICON: Record<string, string> = {
  PERCEIVE: 'Perceived', DIAGNOSIS: 'Diagnosed', DECISION: 'Decided', USER_APPROVED: 'Approved', ACTION_STARTED: 'Acting',
  ACTION_COMPLETED: 'Verified', ACTION_FAILED: 'Failed', LEARN: 'Learned', HEALTH_UPDATED: 'Health', ESCALATED: 'Escalated', REFUSED: 'Refused', BLOCKED: 'Blocked',
  REGISTERED: 'Signed up', KYC_VERIFIED: 'KYC', ACCOUNT_VERIFIED: 'Bank', SIP_STARTED: 'SIP', SIP_UPDATED: 'SIP', BALANCE_CHANGED: 'Sandbox',
}

export function SaarthiHub() {
  const { overview: o, push, openChat, setTab } = useApp()
  if (!o) return <div className="page"><Skeleton h={180} /><Skeleton h={200} /></div>
  const name = (id: string | null) => o.journeys.find(j => j.id === id)?.title ?? ''
  return (
    <div>
      <div className="page" style={{ paddingTop: 10 }}>
        <motion.div className="hub-hero" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="row"><SaarthiMark size={32} /><div>
            <div className="display" style={{ fontSize: 22, fontWeight: 800 }}>Saarthi</div>
          </div></div>
          <div className="ink2" style={{ fontSize: 14, marginTop: 6 }}>Your financial journeys, understood.</div>
          <div className="row" style={{ gap: 16, marginTop: 16 }}>
            <HealthRing score={o.overall_health} size={92} stroke={8} />
            <div className="grow">
              <div className="eyebrow">Overall journey health</div>
              <div style={{ fontSize: 13, marginTop: 6, lineHeight: 1.45 }} className="ink2">
                Across {o.journeys.length} journey{o.journeys.length === 1 ? '' : 's'} with {new Set(o.journeys.map(j => j.partner_id)).size} bank{new Set(o.journeys.map(j => j.partner_id)).size === 1 ? '' : 's'}. {o.attention.length ? `${o.attention.length} need${o.attention.length === 1 ? 's' : ''} you.` : 'Nothing needs you.'}
              </div>
            </div>
          </div>
        </motion.div>

        <button className="ask-bar tap" style={{ marginTop: 14 }} onClick={() => openChat()}>
          <MessageCircle size={18} color="var(--brand)" /> <span className="grow">Ask about any journey: “Why did my SIP fail?”</span>
          <span className="btn btn-soft btn-sm">Ask</span>
        </button>

        <div className="section">
          <div className="section-head"><div className="section-title">What needs your attention?</div></div>
          <div className="card">
            {!o.journeys.length && <div className="empty">No journeys yet. Link a bank and start a SIP, and Saarthi will watch every step.</div>}
            {[...o.journeys].sort((a, b) => a.health_score - b.health_score).slice(0, 4).map((j, i) => {
              const c = issueCopy(j)
              return (
                <button key={j.id} className="attn-item tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'journey', id: j.id })}>
                  <span className="attn-num" style={j.status === 'ATTENTION' ? undefined : { background: 'var(--line)', color: 'var(--ink-2)' }}>{i + 1}</span>
                  <div className="grow">
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>{j.title}</div>
                    <div style={{ fontSize: 12, color: j.status === 'ATTENTION' ? c.tone : 'var(--ink-3)', fontWeight: 500, marginTop: 1 }}>
                      {j.status === 'ATTENTION' ? `${c.status} · ${j.saarthi?.tier === 'TIER_3' ? 'specialist review advised' : 'recovery available'}` : j.status === 'ON_TRACK' ? 'No action needed' : c.status}
                    </div>
                  </div>
                  <HealthPill score={j.health_score} />
                </button>
              )
            })}
          </div>
        </div>

        <div className="section">
          <div className="section-head">
            <div className="section-title">My journeys</div>
            <button className="section-link" onClick={() => push({ name: 'journeys' })}>See all</button>
          </div>
          <div className="jgrid">
            {o.journeys.map(j => (
              <button key={j.id} className="card jtile tap" style={{ textAlign: 'left' }} onClick={() => push({ name: 'journey', id: j.id })}>
                <div className="between"><CategoryIcon category={j.category} size={32} /><HealthPill score={j.health_score} /></div>
                <div className="t">{j.title}</div>
                <div className="s">{j.status === 'ATTENTION' ? (j.agent_status === 'RUNNING' ? '◌ Investigating' : '⚠ Attention required') : j.status === 'ESCALATED' ? '🟠 With specialist' : j.status === 'RESOLVED' ? '🟢 Resolved' : j.status === 'COMPLETE' ? '🟢 Complete' : '🟢 On track'}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="section">
          <div className="section-head"><div className="section-title">What Saarthi is doing</div><Activity size={16} className="muted" /></div>
          <div className="card">
            {o.intelligence.slice(0, 8).map(a => (
              <div key={a.id} className="feed-item">
                <span className={`audit-type ${a.event_type}`} style={{ height: 'fit-content', marginTop: 2 }}>{EVENT_ICON[a.event_type] ?? a.event_type}</span>
                <div className="grow">
                  <div className="t">{a.summary}</div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{name(a.journey_id)} · {ago(a.ts)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="section">
          <div className="card">
            <button className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'knowledge' })}>
              <div className="cat-icon cat-investment" style={{ width: 34, height: 34 }}><BookOpen size={16} /></div>
              <div className="grow"><div className="t">Failure knowledge</div><div className="s">Partner codes, rules & learned outcomes</div></div>
              <ChevronRight size={16} className="muted" />
            </button>
            <button className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => setTab('profile')}>
              <div className="cat-icon cat-kyc" style={{ width: 34, height: 34 }}><FileText size={16} /></div>
              <div className="grow"><div className="t">Document Vault</div><div className="s">Your documents as journey evidence</div></div>
              <ChevronRight size={16} className="muted" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
