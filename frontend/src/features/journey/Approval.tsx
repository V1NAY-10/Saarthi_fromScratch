import { AnimatePresence, motion } from 'framer-motion'
import { ArrowDown, ArrowRight, CheckCircle2, FileCheck2, Loader2, Lock, RotateCcw, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { HealthRing, SaarthiMark, Sheet, TierBadge } from '../../components/ui'
import { inr } from '../../services/format'
import type { Decision, JourneyView, RecoveryOption } from '../../services/types'

/* ── Review & approve sheet ───────────────────────────── */
export function ApprovalSheet({ open, onClose, option, decision, view, onApprove }: {
  open: boolean; onClose: () => void; option: RecoveryOption; decision: Decision; view: JourneyView; onApprove: () => void
}) {
  const p = option.params
  const t = option.action_type
  const j = view.journey
  const acc = view.linked_account
  const retryNote = <div className="saarthi-strip" style={{ marginTop: 12 }}><SaarthiMark size={20} /><div className="t">Then {j.partner_name} re-presents your <b>{inr(t === 'reduce_sip_to_limit' ? p.new_amount : j.amount)}</b> SIP debit and Saarthi verifies the outcome with the bank.</div></div>
  let body, cta = 'Approve'
  if (t === 'fund_and_retry') {
    cta = `Approve & move ${inr(p.amount)}`
    body = (
      <div className="card card-pad" style={{ background: 'var(--surface-2)' }}>
        <div className="eyebrow">Transfer between your own accounts</div>
        <div className="between" style={{ marginTop: 10 }}>
          <div><div className="muted" style={{ fontSize: 11.5 }}>From</div><div style={{ fontWeight: 700 }}>{p.source_label}</div><div className="muted num" style={{ fontSize: 11.5 }}>Balance {inr(p.source_balance)}</div></div>
          <div style={{ textAlign: 'right' }}><div className="muted" style={{ fontSize: 11.5 }}>To</div><div style={{ fontWeight: 700 }}>{p.target_label}</div><div className="muted" style={{ fontSize: 11.5 }}>Autopay account</div></div>
        </div>
        <div className="display num" style={{ fontSize: 30, fontWeight: 800, textAlign: 'center', margin: '14px 0 2px' }}>{inr(p.amount)}</div>
        <div className="muted" style={{ textAlign: 'center', fontSize: 12 }}>exactly the shortfall, nothing more</div>
        <div style={{ textAlign: 'center', margin: '6px 0 -4px' }}><ArrowDown size={16} className="muted" /></div>
        {retryNote}
      </div>
    )
  } else if (t === 'retry_debit') {
    cta = `Approve debit of ${inr(p.amount)}`
    body = (
      <div className="card card-pad" style={{ background: 'var(--surface-2)' }}>
        <div className="eyebrow">Re-present the installment</div>
        <div className="kv" style={{ marginTop: 10 }}>
          <span className="k">Debit</span><span className="v">{inr(p.amount)}</span>
          <span className="k">From</span><span className="v">{acc?.bank} {acc?.masked}</span>
          <span className="k">Balance now</span><span className="v">{inr(acc?.balance)}</span>
        </div>
        {retryNote}
      </div>
    )
  } else if (t === 'raise_mandate_limit_and_retry') {
    cta = `Approve new limit ${inr(p.new_limit)}`
    body = (
      <div className="card card-pad" style={{ background: 'var(--surface-2)' }}>
        <div className="eyebrow">Amend autopay mandate</div>
        <div className="row" style={{ justifyContent: 'center', gap: 14, margin: '14px 0 4px' }}>
          <span className="display num" style={{ fontSize: 22, fontWeight: 800, color: 'var(--ink-3)' }}>{inr(p.old_limit)}</span>
          <ArrowRight size={18} className="muted" />
          <span className="display num" style={{ fontSize: 26, fontWeight: 800 }}>{inr(p.new_limit)}</span>
        </div>
        <div className="muted" style={{ textAlign: 'center', fontSize: 12 }}>UMRN {p.umrn} · maximum per debit</div>
        {retryNote}
      </div>
    )
  } else if (t === 'reduce_sip_to_limit') {
    cta = `Approve SIP of ${inr(p.new_amount)}`
    body = (
      <div className="card card-pad" style={{ background: 'var(--surface-2)' }}>
        <div className="eyebrow">Change your SIP</div>
        <div className="row" style={{ justifyContent: 'center', gap: 14, margin: '14px 0 4px' }}>
          <span className="display num" style={{ fontSize: 22, fontWeight: 800, color: 'var(--ink-3)' }}>{inr(p.old_amount)}</span>
          <ArrowRight size={18} className="muted" />
          <span className="display num" style={{ fontSize: 26, fontWeight: 800 }}>{inr(p.new_amount)}</span>
        </div>
        <div className="muted" style={{ textAlign: 'center', fontSize: 12 }}>per month · stays within your existing autopay limit</div>
        {retryNote}
      </div>
    )
  } else {
    cta = 'Approve one-time consent'
    body = (
      <div className="card card-pad" style={{ background: 'var(--surface-2)' }}>
        <div className="eyebrow">Account Aggregator consent</div>
        <div className="kv" style={{ marginTop: 10 }}>
          <span className="k">Data</span><span className="v">Account holder name & PAN</span>
          <span className="k">Account</span><span className="v">{p.account_label}</span>
          <span className="k">Fetched from</span><span className="v">{j.partner_name} (FIP)</span>
          <span className="k">Purpose</span><span className="v">Prove the account is yours</span>
          <span className="k">Validity</span><span className="v">One-time fetch</span>
        </div>
        <div className="saarthi-strip" style={{ marginTop: 12 }}><FileCheck2 size={18} color="var(--brand)" /><div className="t">If the bank's PAN matches your KYC PAN, the account is verified. If not, Saarthi stops and hands over to a specialist.</div></div>
      </div>
    )
  }
  return (
    <Sheet open={open} onClose={onClose} title={option.effects.shares_data ? 'Approve data consent' : 'Approve recovery'}>
      <div className="row" style={{ marginBottom: 12 }}><TierBadge tier={decision.tier} long /></div>
      {body}
      <div className="stack" style={{ marginTop: 14, gap: 6 }}>
        <div className="row muted" style={{ fontSize: 12 }}><RotateCcw size={14} /> {option.effects.moves_money ? 'Reversible: funds stay in your own name' : 'Consent can be revoked anytime'}</div>
        <div className="row muted" style={{ fontSize: 12 }}><Lock size={14} /> Saarthi will do nothing beyond what's shown here</div>
      </div>
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 16 }} onClick={onApprove}>{cta}</button>
    </Sheet>
  )
}

/* ── Execution overlay: steps revealed as partner responses arrive ───────────────────────────── */
function preview(actionType: string, bank: string): string[] {
  return ({
    fund_and_retry: ['Transferring the shortfall', 'Re-checking the autopay account balance', `Asking ${bank} to re-present the debit`, `Verifying the outcome with ${bank}`],
    retry_debit: ['Re-checking the autopay account balance', `Asking ${bank} to re-present the debit`, `Verifying the outcome with ${bank}`],
    raise_mandate_limit_and_retry: [`Amending the mandate with ${bank}`, `Asking ${bank} to re-present the debit`, `Verifying the outcome with ${bank}`],
    reduce_sip_to_limit: ['Updating your SIP amount', `Asking ${bank} to re-present the debit`, `Verifying the outcome with ${bank}`],
    verify_ownership_via_aa: ['Creating consent artefact', `Fetching the holder profile from ${bank}`, 'Comparing PAN with your KYC', `Confirming verification with ${bank}`, 'Verifying the outcome'],
  } as Record<string, string[]>)[actionType] ?? ['Executing']
}

export function Execution({ actionType, result, view, onDone }: { actionType: string; result: JourneyView | null; view: JourneyView; onDone: () => void }) {
  const steps0 = preview(actionType, view.journey.partner_name)
  const steps = result?.action_result?.result.steps
  const [shown, setShown] = useState(0)
  const ok = result?.action_result?.status === 'COMPLETED'

  useEffect(() => {
    if (!steps) return
    if (shown >= steps.length) return
    const t = window.setTimeout(() => setShown(s => s + 1), shown === 0 ? 350 : 750)
    return () => window.clearTimeout(t)
  }, [steps, shown])

  const finished = !!steps && shown >= steps.length
  const total = steps?.length ?? steps0.length
  const d = result?.diagnosis
  return (
    <motion.div className="full" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <div style={{ padding: '58px 20px 16px' }}>
        <div className="row"><SaarthiMark size={28} /><span className="eyebrow" style={{ color: 'var(--brand)' }}>Act → Verify</span></div>
        <div className="display" style={{ fontSize: 22, fontWeight: 800, marginTop: 10 }}>
          {finished ? (ok ? 'Recovered & verified' : 'Stopped safely, re-assessing') : 'Saarthi is recovering your journey'}
        </div>
        <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>Every step is executed through the partner and checked before moving on.</div>
      </div>
      <div style={{ padding: '0 16px', flex: 1, overflowY: 'auto' }}>
        <div className="card card-pad">
          {Array.from({ length: total }).map((_, i) => {
            const real = steps?.[i]
            const state = real && i < shown ? (real.ok ? 'ok' : 'no') : (i === shown ? 'run' : 'wait')
            return (
              <div key={i} className="exec-step" style={{ opacity: state === 'wait' ? 0.45 : 1 }}>
                <span className={`exec-ic ${state === 'wait' ? '' : state}`} style={state === 'wait' ? { background: 'var(--line-2)' } : undefined}>
                  {state === 'ok' ? <CheckCircle2 size={15} /> : state === 'no' ? <XCircle size={15} /> : state === 'run' ? <Loader2 size={15} className="spin" /> : null}
                </span>
                <div className="grow">
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{real && i < shown ? real.label : steps0[i] ?? 'Working'}</div>
                  <AnimatePresence>
                    {real && i < shown && (
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
                        <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>{real.detail}</div>
                        {real.partner_normalized && (
                          <div className="row" style={{ gap: 6, marginTop: 5 }}>
                            <span className="chip">{String(real.partner_normalized.partner_name)}</span>
                            <span className="code-chip" style={{ fontSize: 10 }}>{String(real.partner_normalized.raw_code ?? real.partner_normalized.state)}</span>
                            <span className={`pill ${real.ok ? 'pill-ok' : 'pill-bad'}`} style={{ height: 18 }}>{String(real.partner_normalized.state)}</span>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            )
          })}
        </div>
        <AnimatePresence>
          {finished && ok && d?.health_transition && (
            <motion.div className="card card-pad" style={{ marginTop: 12, textAlign: 'center' }} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
              <div className="eyebrow">Journey health</div>
              <div style={{ display: 'flex', justifyContent: 'center', margin: '12px 0 6px' }}>
                <HealthRing score={d.health_transition.after} from={d.health_transition.before} size={116} stroke={10} />
              </div>
              <div className="row" style={{ justifyContent: 'center', gap: 8 }}>
                <span className="pill pill-ok">RESOLVED</span>
                <span className="muted num" style={{ fontSize: 12.5 }}>{d.health_transition.before} → {d.health_transition.after}</span>
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 10 }}>Timeline updated · Audit log updated · Learning event recorded</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div style={{ padding: '12px 16px 26px' }}>
        <button className="btn btn-primary btn-lg btn-block" disabled={!finished} onClick={onDone}>{finished ? 'Done' : 'Working…'}</button>
      </div>
    </motion.div>
  )
}
