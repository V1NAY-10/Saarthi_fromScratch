import { motion } from 'framer-motion'
import { Cpu, FlaskConical, LogOut, Minus, Plus, RotateCcw, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { BankLogo, SaarthiMark } from '../components/ui'
import { AgentBadge, AgentTrace } from '../features/journey/AgentTrace'
import { useApp } from '../hooks/useApp'
import { api } from '../services/api'
import { inr, time } from '../services/format'
import type { AuditEntry, JourneyView, Overview } from '../services/types'

const STAGES: [string, string, string][] = [
  ['perceive', 'Perceive', 'Bank rejection intercepted & normalized'],
  ['diagnose', 'Diagnose', 'Agent investigates with tools'],
  ['decide', 'Decide', 'Deterministic safety tiers'],
  ['act', 'Act', 'Partner APIs execute'],
  ['verify', 'Verify', 'Outcome confirmed with the bank'],
  ['learn', 'Learn', 'Outcome feeds future diagnoses'],
]

/** Desktop-only panel beside the phone: shows the agent working live, plus sandbox controls. */
export function EnginePanel() {
  const { userId, focusJourney, overview, bump, version, signOut, showToast } = useApp()
  const [view, setView] = useState<JourneyView | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [sys, setSys] = useState<Overview['system'] | null>(null)
  const [resetting, setResetting] = useState(false)

  // Focus: the journey being viewed, else the most recent one needing attention.
  const jid = focusJourney ?? overview?.attention[0]?.id ?? overview?.journeys[0]?.id ?? null

  useEffect(() => { api.system().then(setSys).catch(() => { }) }, [])
  useEffect(() => {
    if (!userId) { setView(null); setAudit([]); return }
    let alive = true
    const load = () => {
      if (jid) api.journey(jid).then(v => alive && setView(v)).catch(() => { })
      else setView(null)
      api.audit(30).then(a => alive && setAudit(a)).catch(() => { })
    }
    load()
    const t = window.setInterval(load, 1500)
    return () => { alive = false; window.clearInterval(t) }
  }, [userId, jid, version])

  async function reset() {
    if (!window.confirm('Wipe all sandbox users, accounts, SIPs and journeys?')) return
    setResetting(true)
    await api.reset()
    signOut()
    setResetting(false)
    showToast('Sandbox reset. Every user and journey was removed.')
  }

  async function nudge(id: string, delta: number) {
    try { await api.adjustBalance(id, delta); bump() } catch (e) { showToast((e as Error).message) }
  }

  const j = view?.journey
  const run = view?.agent_run
  return (
    <aside className="engine">
      <div className="eng-card">
        <div className="eng-brand">
          <SaarthiMark size={40} />
          <div className="grow">
            <div className="display" style={{ fontSize: 20, fontWeight: 800 }}>Saarthi</div>
            <div className="muted" style={{ fontSize: 12.5 }}>From financial status to financial resolution.</div>
          </div>
        </div>
        <div className="row" style={{ gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
          <span className="pill pill-info"><Cpu size={11} /> Deterministic safety engine</span>
          {sys && (sys.llm_enabled
            ? <span className="pill pill-ok"><Sparkles size={11} /> Claude agent · {sys.model}</span>
            : <span className="pill pill-neutral">Agent: deterministic planner (no API key)</span>)}
        </div>
      </div>

      {!userId ? (
        <div className="eng-card" style={{ flex: 1 }}>
          <div className="eyebrow">How to demo</div>
          {[
            ['Create an account', 'Any well-formed PAN works in the sandbox.'],
            ['Link a bank account', 'Set the name the bank holds. Initials or a different person will fail verification.'],
            ['Start a SIP', 'Use a balance lower than the SIP to make the first debit bounce.'],
            ['Watch the agent', 'It investigates with tools, gets a tier from the safety engine and proposes a fix.'],
            ['Approve', 'The fix runs through the bank APIs and is verified with the bank. Saarthi then learns from it.'],
            ['Step up the SIP', 'Raise the amount above the autopay limit and run the next installment.'],
          ].map(([t, s], i) => (
            <div key={t} className="row" style={{ alignItems: 'flex-start', gap: 10, marginTop: 12 }}>
              <span className="attn-num">{i + 1}</span>
              <div><div style={{ fontWeight: 700, fontSize: 13 }}>{t}</div><div className="muted" style={{ fontSize: 12, lineHeight: 1.4 }}>{s}</div></div>
            </div>
          ))}
        </div>
      ) : <>
        <div className="eng-card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="between">
            <div style={{ minWidth: 0 }}>
              <div className="eyebrow">{run?.status === 'RUNNING' ? 'Agent working' : 'Live loop'}</div>
              <div style={{ fontWeight: 700, fontSize: 14, marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{j?.title ?? 'No journey yet'} {j && <span className="muted" style={{ fontWeight: 500 }}>· {j.partner_name}</span>}</div>
            </div>
            {j && <span className="display num" style={{ fontSize: 22, fontWeight: 800 }}>{view?.health.score}</span>}
          </div>
          <div className="eng-loop">
            {STAGES.map(([k, l, d], i) => {
              const st = view?.loop.find(s => s.stage === k)?.state ?? 'pending'
              return (
                <motion.div key={k} className={`eng-stage ${st}`} layout>
                  <div className="n">0{i + 1}</div><div className="l">{l}</div><div className="d">{d}</div>
                </motion.div>
              )
            })}
          </div>
          {run ? <>
            <div className="between" style={{ marginTop: 12 }}><div className="eyebrow">Agent trace</div><AgentBadge run={run} /></div>
            <div className="eng-trace"><AgentTrace key={run.id} run={run} compact /></div>
          </> : (
            <div className="eng-feed" style={{ marginTop: 12 }}>
              <div className="eyebrow">Audit stream</div>
              {audit.map(a => (
                <div key={a.id} className="eng-ev">
                  <span className="ts">{time(a.ts)}</span>
                  <div><span className={`audit-type ${a.event_type}`}>{a.event_type.replace(/_/g, ' ')}</span><div style={{ marginTop: 4, fontWeight: 500, lineHeight: 1.4 }}>{a.summary}</div></div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="eng-card">
          <div className="between">
            <div className="sandbox-tag"><FlaskConical size={12} /> Sandbox · bank-side balances</div>
            <div className="row" style={{ gap: 4 }}>
              <button className="btn btn-ghost btn-sm" onClick={signOut} title="Sign out"><LogOut size={13} /></button>
              <button className="btn btn-ghost btn-sm" onClick={reset} disabled={resetting}><RotateCcw size={13} /> Reset</button>
            </div>
          </div>
          {!overview?.accounts.length ? <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>No accounts linked yet.</div> : overview.accounts.map(a => (
            <div key={a.id} className="row" style={{ marginTop: 8, gap: 8 }}>
              <BankLogo bank={a.partner_id} size={26} />
              <div className="grow" style={{ fontSize: 12.5, fontWeight: 600 }}>{a.bank} {a.masked}</div>
              <span className="num" style={{ fontSize: 12.5, fontWeight: 700 }}>{inr(a.balance)}</span>
              <button className="btn btn-ghost btn-sm" style={{ width: 30, padding: 0 }} onClick={() => nudge(a.id, -Math.min(5000, a.balance))} aria-label="Withdraw 5000"><Minus size={13} /></button>
              <button className="btn btn-ghost btn-sm" style={{ width: 30, padding: 0 }} onClick={() => nudge(a.id, 5000)} aria-label="Add 5000"><Plus size={13} /></button>
            </div>
          ))}
        </div>
      </>}
    </aside>
  )
}
