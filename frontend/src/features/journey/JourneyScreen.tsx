import { AnimatePresence, motion } from 'framer-motion'
import { Eye, Headset, MessageCircle, Plus, RefreshCw, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { HealthRing, SaarthiMark, Skeleton, StatusPill, TopBar } from '../../components/ui'
import { useApp, useData } from '../../hooks/useApp'
import { BalanceSheet } from '../../pages/Banks'
import { api } from '../../services/api'
import { inr } from '../../services/format'
import type { JourneyView } from '../../services/types'
import { AgentBadge, AgentTrace } from './AgentTrace'
import { ApprovalSheet, Execution } from './Approval'
import { AuditTab } from './AuditTab'
import {
  DecisionCard, EvidenceKnowledge, NameMatch, Normalization, Options, ResolvedCard, SupportCaseCard, TierExplainer, WhatHappened,
} from './DiagnosisTab'
import { GraphTab } from './GraphTab'
import { HealthSheet } from './HealthSheet'
import { LoopStepper } from './LoopStepper'
import { TimelineTab } from './TimelineTab'

type TabKey = 'diagnosis' | 'agent' | 'timeline' | 'graph' | 'audit'
const TABS: [TabKey, string][] = [['diagnosis', 'Diagnosis'], ['agent', 'Agent'], ['timeline', 'Timeline'], ['graph', 'Graph'], ['audit', 'Audit']]

const EYEBROW: Record<string, string> = {
  ATTENTION: 'Journey interrupted', RESOLVED: 'Journey resolved', ESCALATED: 'With a specialist', ON_TRACK: 'On track', COMPLETE: 'Complete',
}

export function JourneyScreen({ id, autoApprove }: { id: string; autoApprove?: boolean }) {
  const { pop, bump, openChat, showToast } = useApp()
  const { data: view, setData, reload } = useData(() => api.journey(id), [id])
  const [tab, setTab] = useState<TabKey>('diagnosis')
  const [healthOpen, setHealthOpen] = useState(false)
  const [approveOpen, setApproveOpen] = useState(false)
  const [topUp, setTopUp] = useState(false)
  const [exec, setExec] = useState<{ type: string; result: JourneyView | null } | null>(null)
  const [busy, setBusy] = useState(false)

  const investigating = !!view && view.journey.status === 'ATTENTION' && (view.agent_run?.status === 'RUNNING' || !view.diagnosis)

  // A run that is in progress, or finished moments ago, is shown live step by step before the
  // diagnosis appears. The offline planner finishes in milliseconds; this replays its real trace.
  const seenRuns = useRef(new Set<string>())
  const [liveRun, setLiveRun] = useState<string | null>(null)
  const r0 = view?.agent_run
  useEffect(() => {
    if (!r0 || seenRuns.current.has(r0.id) || view?.journey.status !== 'ATTENTION') return
    seenRuns.current.add(r0.id)
    const fresh = r0.status === 'RUNNING' || (r0.finished_at && Date.now() - new Date(r0.finished_at).getTime() < 10000)
    if (fresh) setLiveRun(r0.id)
  }, [r0?.id, r0?.status, r0?.finished_at, view?.journey.status])
  const endLive = useCallback(() => setLiveRun(null), [])
  const showLive = investigating || (!!r0 && liveRun === r0.id && view?.journey.status === 'ATTENTION')

  // Poll while the agent works; refresh the app shell once it's done.
  useEffect(() => {
    if (!investigating) return
    const t = window.setInterval(reload, 900)
    return () => { window.clearInterval(t); bump() }
  }, [investigating, reload, bump])

  useEffect(() => { if (autoApprove && view?.journey.status === 'ATTENTION' && view.diagnosis) setApproveOpen(true) }, [autoApprove, view?.journey.status, view?.diagnosis])

  if (!view) return <div><TopBar title="Loading…" onBack={pop} /><div className="page"><Skeleton h={160} /><Skeleton h={220} /><Skeleton h={180} /></div></div>

  const j = view.journey
  const d = view.diagnosis?.status === 'DIAGNOSED' && !showLive ? view.diagnosis : null
  const decision = d?.decisions.primary ?? null
  const option = d && decision ? d.options.find(o => o.id === decision.option_id)! : null
  const completed = view.actions.find(a => a.status === 'COMPLETED' && a.result?.steps && a.action_type !== 'remind_before_window')
  const pendingAction = view.actions.find(a => a.status === 'PENDING_APPROVAL')
  const waitingTopUp = j.status === 'ATTENTION' && j.stage === 'Waiting for a top-up'
  const run = view.agent_run

  async function approve() {
    if (!option) return
    setApproveOpen(false)
    setExec({ type: option.action_type, result: null })
    try {
      let actionId = pendingAction?.id
      if (!actionId) actionId = (await api.recover(id, option.id)).action.id
      const res = await api.approve(id, actionId)
      setExec({ type: option.action_type, result: res })
      setData(res)
    } catch (e) {
      setExec(null)
      showToast((e as Error).message)
      reload()
    }
  }

  async function escalate() {
    setBusy(true)
    try { setData(await api.escalate(id)); bump(); setTab('diagnosis') } catch (e) { showToast((e as Error).message) } finally { setBusy(false) }
  }

  async function pickAlt(optionId: string) {
    try {
      const r = await api.recover(id, optionId)
      showToast(r.outcome === 'EXECUTED' ? 'Done. That Tier 1 action ran automatically.' : r.outcome === 'APPROVAL_REQUIRED' ? 'This option needs your approval.' : 'Escalation recommended for this option.')
      setData(r.view); bump()
    } catch (e) { showToast((e as Error).message) }
  }

  async function rerun() {
    try { setData(await api.diagnose(id)); setTab('agent') } catch (e) { showToast((e as Error).message) }
  }

  return (
    <div>
      <TopBar title={j.title} sub={`${j.partner_name} · ${j.partner_ref}`} onBack={pop}
        right={<button className="icon-btn" onClick={() => openChat(id)} aria-label="Ask Saarthi"><MessageCircle size={18} /></button>} />
      <div className="page page-tight">
        <motion.div className="card jhero" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="between" style={{ alignItems: 'flex-start' }}>
            <div className="grow">
              <div className="eyebrow" style={{ color: j.status === 'ATTENTION' ? 'var(--bad)' : j.status === 'ESCALATED' ? 'var(--warn)' : 'var(--ok)' }}>{EYEBROW[j.status]}</div>
              <div className="amt num" style={{ marginTop: 4 }}>{j.amount ? inr(j.amount) : j.category === 'bank_account' ? 'Verification' : '—'}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{j.subtitle} · {j.stage}</div>
              <div style={{ marginTop: 8 }}><StatusPill status={j.status} /></div>
            </div>
            <button onClick={() => setHealthOpen(true)} style={{ textAlign: 'center' }} aria-label="Why this health score">
              <HealthRing score={view.health.score} size={84} />
              <div className="section-link" style={{ fontSize: 11, marginTop: 4 }}>Why {view.health.score}?</div>
            </button>
          </div>
          <LoopStepper loop={view.loop} />
        </motion.div>

        <div className="seg">
          {TABS.map(([k, l]) => (
            <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>
              {tab === k && <motion.span layoutId="seg" className="seg-bg" transition={{ type: 'spring', damping: 30, stiffness: 400 }} />}
              {l}
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={tab} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            {tab === 'diagnosis' && (
              <div>
                {showLive && run && <Investigating view={view} onDone={endLive} />}
                {j.status === 'RESOLVED' && completed && <ResolvedCard view={view} action={completed} />}
                {j.status === 'ESCALATED' && view.support_case && <SupportCaseCard view={view} />}
                {waitingTopUp && view.linked_account && (
                  <div className="card card-pad card-saarthi">
                    <div className="row"><Eye size={18} color="var(--brand)" /><div className="card-title">Saarthi is watching for a top-up</div></div>
                    <p className="ink2" style={{ fontSize: 13, lineHeight: 1.5, marginTop: 8 }}>
                      None of your other accounts could safely cover the shortfall, so Saarthi set a reminder instead of moving money. When {view.linked_account.bank} {view.linked_account.masked} receives funds, it re-plans automatically.
                    </p>
                    <button className="btn btn-soft btn-block" style={{ marginTop: 12 }} onClick={() => setTopUp(true)}><Plus size={15} /> Add money (sandbox)</button>
                  </div>
                )}
                {d ? (
                  <>
                    {j.status !== 'ATTENTION' && <div className="eyebrow" style={{ margin: '18px 4px 8px' }}>Original diagnosis</div>}
                    <WhatHappened d={d} run={run} />
                    <NameMatch d={d} />
                    <Normalization d={d} />
                    {decision && <DecisionCard d={d} decision={decision} view={view} />}
                    {j.status === 'ATTENTION' && !waitingTopUp && <Options d={d} onPick={pickAlt} />}
                    <EvidenceKnowledge d={d} />
                    {j.status === 'ATTENTION' && <TierExplainer />}
                  </>
                ) : !showLive && j.status === 'ON_TRACK' && (
                  <OnTrack view={view} />
                )}
              </div>
            )}
            {tab === 'agent' && (
              <div className="card card-pad">
                {run ? <>
                  <div className="between" style={{ marginBottom: 8 }}>
                    <div><div className="card-title">How Saarthi investigated</div><div className="muted" style={{ fontSize: 11.5 }}>{run.trace.filter(t => t.type === 'tool').length} tool calls · every tier set by the safety engine</div></div>
                    <AgentBadge run={run} />
                  </div>
                  <AgentTrace run={run} />
                  {j.status === 'ATTENTION' && !investigating && <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={rerun}><RefreshCw size={13} /> Re-run investigation</button>}
                </> : <div className="empty">Saarthi hasn't needed to investigate this journey.</div>}
              </div>
            )}
            {tab === 'timeline' && <TimelineTab events={view.timeline} />}
            {tab === 'graph' && <GraphTab graph={view.graph} diag={d} />}
            {tab === 'audit' && <AuditTab entries={view.audit} />}
          </motion.div>
        </AnimatePresence>
      </div>

      {j.status === 'ATTENTION' && decision && !showLive && !waitingTopUp && (
        <div className="cta-bar">
          {decision.tier === 'TIER_3' ? (
            <button className="btn btn-warn btn-lg btn-block" disabled={busy} onClick={escalate}><Headset size={18} /> {busy ? 'Preparing case…' : 'Escalate to a specialist'}</button>
          ) : (
            <button className="btn btn-primary btn-lg btn-block" onClick={() => setApproveOpen(true)}>Review & approve recovery</button>
          )}
          <div className="hint"><ShieldCheck size={13} /> {decision.tier === 'TIER_3' ? "Saarthi won't act on an account it can't prove is yours" : 'Nothing happens without your approval'}</div>
        </div>
      )}

      <HealthSheet open={healthOpen} onClose={() => setHealthOpen(false)} health={view.health} />
      {option && decision && (
        <ApprovalSheet open={approveOpen} onClose={() => setApproveOpen(false)} option={option} decision={decision} view={view} onApprove={approve} />
      )}
      <BalanceSheet account={topUp ? view.linked_account : null} onClose={() => { setTopUp(false); reload() }} />
      <AnimatePresence>
        {exec && <Execution actionType={exec.type} result={exec.result} view={view} onDone={() => { setExec(null); bump(); reload(); setTab('diagnosis') }} />}
      </AnimatePresence>
    </div>
  )
}

function Investigating({ view, onDone }: { view: JourneyView; onDone: () => void }) {
  const run = view.agent_run!
  const failed = [...view.timeline].reverse().find(e => e.status === 'failed')
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="agent-live">
        <SaarthiMark size={30} />
        <div className="grow">
          <div className="t">Saarthi is investigating</div>
          <div className="s">{failed ? `${view.journey.partner_name} returned ${view.journey.state.failure_code}` : 'Checking with the bank'}</div>
        </div>
        <AgentBadge run={run} />
      </div>
      <div className="card card-pad" style={{ marginTop: 10 }}>
        <AgentTrace run={run} replay onDone={onDone} />
      </div>
    </motion.div>
  )
}

function OnTrack({ view }: { view: JourneyView }) {
  const j = view.journey
  const sip = view.sip, acc = view.linked_account, m = view.mandate
  return (
    <div className="card card-pad">
      <div className="row"><ShieldCheck size={20} color="var(--ok)" /><div className="card-title">No action needed</div></div>
      <p className="ink2" style={{ fontSize: 13, lineHeight: 1.5, marginTop: 8 }}>
        {j.category === 'investment' ? 'Every installment so far has been debited and verified. Saarthi checks each one as it happens.' : 'This account is verified.'}
      </p>
      <div className="kv" style={{ marginTop: 12 }}>
        <span className="k">Stage</span><span className="v">{j.stage}</span>
        {sip && <><span className="k">Installments paid</span><span className="v">{sip.installments_paid}</span></>}
        {m && <><span className="k">Autopay limit</span><span className="v">{inr(m.max_amount)} · {m.umrn}</span></>}
        {acc && <><span className="k">Autopay account</span><span className="v">{acc.bank} {acc.masked} · {inr(acc.balance)}</span></>}
        <span className="k">Reference</span><span className="v mono" style={{ fontSize: 11.5 }}>{j.partner_ref}</span>
      </div>
    </div>
  )
}
