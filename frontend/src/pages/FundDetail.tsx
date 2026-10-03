import { motion } from 'framer-motion'
import { CheckCircle2, Landmark, Loader2, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { AccountStatus, BankLogo, FundLogo, SaarthiMark, Sheet, Skeleton, TopBar } from '../components/ui'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { inr } from '../services/format'
import type { Fund, SipStartResult } from '../services/types'

export function FundDetail({ id }: { id: string }) {
  const { pop } = useApp()
  const { data: f } = useData(() => api.fund(id), [id])
  const [open, setOpen] = useState(false)
  if (!f) return <div><TopBar title="Loading…" onBack={pop} /><div className="page"><Skeleton h={200} /></div></div>
  return (
    <div>
      <TopBar title={f.name} sub={f.amc} onBack={pop} />
      <div className="page page-tight">
        <div className="card card-pad">
          <div className="row"><FundLogo id={f.id} name={f.name} size={44} /><div>
            <div style={{ fontWeight: 800, fontSize: 16 }}>{f.name}</div>
            <div className="muted" style={{ fontSize: 12 }}>{f.category} · {f.risk} risk</div>
          </div></div>
          <div className="stat-grid">
            <div className="stat"><div className="k">1Y</div><div className="v ret">{f.returns_1y}%</div></div>
            <div className="stat"><div className="k">3Y p.a.</div><div className="v ret">{f.returns_3y}%</div></div>
            <div className="stat"><div className="k">5Y p.a.</div><div className="v ret">{f.returns_5y}%</div></div>
          </div>
          <div className="kv" style={{ marginTop: 14 }}>
            <span className="k">NAV</span><span className="v num">₹{f.nav}</span>
            <span className="k">Minimum SIP</span><span className="v">{inr(f.min_sip)}</span>
            <span className="k">Expense ratio</span><span className="v">{f.expense_ratio}%</span>
            <span className="k">Fund size</span><span className="v">₹{f.aum_cr.toLocaleString('en-IN')} Cr</span>
          </div>
        </div>
        <div className="saarthi-strip" style={{ marginTop: 12 }}>
          <SaarthiMark size={20} />
          <div className="t">If a debit for this SIP ever fails, Saarthi diagnoses it with the bank and proposes a safe fix.</div>
        </div>
      </div>
      <div className="cta-bar">
        <button className="btn btn-primary btn-lg btn-block" onClick={() => setOpen(true)}>Start SIP</button>
      </div>
      <StartSip fund={f} open={open} onClose={() => setOpen(false)} />
    </div>
  )
}

function StartSip({ fund, open, onClose }: { fund: Fund; open: boolean; onClose: () => void }) {
  const { overview, push, replace, bump } = useApp()
  const accounts = overview?.accounts ?? []
  const verified = accounts.filter(a => a.status === 'VERIFIED')
  const [amount, setAmount] = useState(String(Math.max(fund.min_sip, 5000)))
  const [day, setDay] = useState(5)
  const [acc, setAcc] = useState<string | null>(null)
  const [limitMode, setLimitMode] = useState<'same' | 'double'>('same')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [result, setResult] = useState<SipStartResult | null>(null)
  const n = Number(amount || 0)
  const accountId = acc ?? verified[0]?.id ?? null
  const chosen = accounts.find(a => a.id === accountId)
  const limit = limitMode === 'same' ? n : n * 2

  async function start() {
    if (!accountId) return
    setErr(null); setBusy(true)
    try {
      const r = await api.startSip({ fund_id: fund.id, amount: n, sip_day: day, account_id: accountId, mandate_limit: limit })
      setResult(r); bump()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  if (result) {
    const ok = result.installment.status === 'SUCCESS'
    return (
      <Sheet open={open} onClose={() => { onClose(); setResult(null) }} title={ok ? 'SIP started' : 'First installment failed'}>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} style={{ textAlign: 'center', padding: '6px 0 4px' }}>
          {ok ? <div className="success-badge"><CheckCircle2 size={34} /></div> : <div className="success-badge" style={{ background: 'var(--brand-soft)' }}><SaarthiMark size={34} /></div>}
          <div className="display" style={{ fontSize: 19, fontWeight: 800, marginTop: 12 }}>
            {ok ? `${inr(n)} invested in ${fund.name}` : `${chosen?.bank} returned the debit`}
          </div>
          <div className="muted" style={{ fontSize: 13, marginTop: 6, lineHeight: 1.5 }}>
            {ok ? `${result.installment.transaction?.units} units at NAV ₹${result.installment.transaction?.nav} · Ref ${result.installment.transaction?.bank_ref}`
              : <>Code <span className="mono">{result.installment.code}</span>. Saarthi's agent has already started investigating.</>}
          </div>
        </motion.div>
        <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 18 }} onClick={() => { onClose(); setResult(null); replace({ name: 'journey', id: result.journey_id }) }}>
          {ok ? 'View SIP journey' : 'Watch Saarthi work'}
        </button>
      </Sheet>
    )
  }

  return (
    <Sheet open={open} onClose={onClose} title="Start a monthly SIP">
      <label className="field" style={{ marginTop: 0 }}>
        <span className="lbl">Monthly amount</span>
        <div className="input-pre"><span>₹</span><input className="input num" inputMode="numeric" value={amount} onChange={e => setAmount(e.target.value.replace(/\D/g, '').slice(0, 7))} /></div>
        <div className="chips-row">{[1000, 2000, 5000, 10000].filter(v => v >= fund.min_sip).map(v => (
          <button key={v} type="button" className={`chip-btn ${n === v ? 'on' : ''}`} onClick={() => setAmount(String(v))}>{inr(v)}</button>
        ))}</div>
      </label>
      <div className="field">
        <span className="lbl">SIP date</span>
        <div className="chips-row" style={{ marginTop: 0 }}>{[1, 5, 10, 15, 20, 25].map(d => (
          <button key={d} type="button" className={`chip-btn ${day === d ? 'on' : ''}`} onClick={() => setDay(d)}>{d}{d === 1 ? 'st' : 'th'}</button>
        ))}</div>
      </div>
      <div className="field">
        <span className="lbl">Pay from (autopay)</span>
        {accounts.length === 0 ? (
          <button className="btn btn-soft btn-block" onClick={() => { onClose(); push({ name: 'linkBank' }) }}><Landmark size={15} /> Link a bank account first</button>
        ) : accounts.map(a => (
          <button key={a.id} type="button" disabled={a.status !== 'VERIFIED'} className={`pick row ${accountId === a.id ? 'on' : ''}`}
            style={{ width: '100%', gap: 10, marginTop: 6, opacity: a.status === 'VERIFIED' ? 1 : 0.55 }} onClick={() => setAcc(a.id)}>
            <BankLogo bank={a.partner_id} size={30} />
            <div className="grow"><div className="pt">{a.bank} {a.masked}</div><div className="ps">Balance {inr(a.balance)}</div></div>
            <AccountStatus status={a.status} />
          </button>
        ))}
      </div>
      <div className="field">
        <span className="lbl">Autopay limit (mandate maximum)</span>
        <div className="pick-grid">
          <button type="button" className={`pick ${limitMode === 'same' ? 'on' : ''}`} onClick={() => setLimitMode('same')}><div className="pt">{inr(n)}</div><div className="ps">Same as SIP</div></button>
          <button type="button" className={`pick ${limitMode === 'double' ? 'on' : ''}`} onClick={() => setLimitMode('double')}><div className="pt">{inr(n * 2)}</div><div className="ps">Room to step up</div></button>
        </div>
        <div className="hint">The bank refuses any debit above this limit.</div>
      </div>
      {chosen && n > chosen.balance && (
        <div className="hint" style={{ color: 'var(--warn)', fontWeight: 600 }}>{chosen.bank} {chosen.masked} has {inr(chosen.balance)}, which is less than {inr(n)}. The first debit will be presented today.</div>
      )}
      {err && <div className="form-err">{err}</div>}
      <div className="row muted" style={{ fontSize: 11.5, marginTop: 14, gap: 6 }}><ShieldCheck size={13} /> First installment is debited today; then every month on the {day}{day === 1 ? 'st' : 'th'}.</div>
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 12 }} disabled={busy || !accountId || !n} onClick={start}>
        {busy ? <><Loader2 size={18} className="spin" /> Registering mandate…</> : `Approve autopay & pay ${inr(n)}`}
      </button>
    </Sheet>
  )
}
