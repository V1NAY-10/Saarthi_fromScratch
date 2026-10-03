import { CalendarClock, ChevronRight, FastForward, Loader2, Pencil, Repeat } from 'lucide-react'
import { useState } from 'react'
import { SaarthiStrip } from '../components/journey'
import { FundLogo, Sheet, Skeleton, StatusPill, TopBar } from '../components/ui'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { dueLabel, inr } from '../services/format'
import type { Sip } from '../services/types'

export function Invest() {
  const { overview: o, push } = useApp()
  const { data: funds } = useData(() => api.funds())
  if (!o) return <div className="page"><Skeleton h={140} /><Skeleton h={200} /></div>
  const gain = o.portfolio_value - o.invested
  return (
    <div>
      <TopBar title="Invest" sub="Mutual funds · SIPs" />
      <div className="page">
        <div className="card card-pad">
          <div className="muted" style={{ fontSize: 12 }}>Portfolio value</div>
          <div className="between" style={{ marginTop: 2 }}>
            <div className="display num" style={{ fontSize: 28, fontWeight: 800 }}>{inr(o.portfolio_value)}</div>
            {o.invested > 0 && <span className={`pill ${gain >= 0 ? 'pill-ok' : 'pill-bad'}`}>{gain >= 0 ? '+' : ''}{inr(gain)}</span>}
          </div>
          <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>Invested {inr(o.invested)} · {o.sips.length} SIP{o.sips.length === 1 ? '' : 's'}</div>
        </div>

        {o.sips.length > 0 && (
          <div className="section">
            <div className="section-head"><div className="section-title">Your SIPs</div></div>
            <div className="stack">{o.sips.map(s => <SipCard key={s.id} s={s} />)}</div>
          </div>
        )}

        <div className="section">
          <div className="section-head"><div className="section-title">Explore funds</div><span className="muted" style={{ fontSize: 11.5 }}>3Y returns</span></div>
          <div className="card">
            {!funds ? <Skeleton h={300} mt={0} /> : funds.map(f => (
              <button key={f.id} className="fund-row tap" onClick={() => push({ name: 'fund', id: f.id })}>
                <FundLogo id={f.id} name={f.name} />
                <div className="grow">
                  <div style={{ fontWeight: 700, fontSize: 13.5 }}>{f.name}</div>
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>{f.category} · {f.risk} · min {inr(f.min_sip)}</div>
                </div>
                <div className="ret">{f.returns_3y.toFixed(1)}%</div>
                <ChevronRight size={16} className="muted" />
              </button>
            ))}
          </div>
          <div className="muted" style={{ fontSize: 11, margin: '8px 4px 0' }}>Sandbox funds. Names, NAVs and returns are illustrative.</div>
        </div>
      </div>
    </div>
  )
}

function SipCard({ s }: { s: Sip }) {
  const { push, bump, showToast } = useApp()
  const [busy, setBusy] = useState(false)
  const [edit, setEdit] = useState(false)
  const j = useApp().overview?.journeys.find(x => x.id === s.journey_id)
  const blocked = s.journey_status === 'ATTENTION' || s.journey_status === 'ESCALATED'

  async function run() {
    setBusy(true)
    try {
      const r = await api.runInstallment(s.id)
      if (r.status === 'SUCCESS') showToast(`Installment debited · ${r.transaction?.units} units allotted`)
      else { showToast(`Bank rejected the debit (${r.code}). Saarthi is investigating.`); push({ name: 'journey', id: s.journey_id }) }
      bump()
    } catch (e) { showToast((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="card card-pad">
      <div className="between" style={{ alignItems: 'flex-start' }}>
        <button className="row" style={{ textAlign: 'left', alignItems: 'flex-start' }} onClick={() => push({ name: 'journey', id: s.journey_id })}>
          <FundLogo id={s.fund.id} name={s.fund.name} size={34} />
          <div>
            <div style={{ fontWeight: 700 }}>{s.fund.name}</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{s.account.bank} {s.account.masked} · UMRN limit {inr(s.mandate.max_amount)}</div>
          </div>
        </button>
        <StatusPill status={s.journey_status} />
      </div>
      <div className="row" style={{ gap: 14, marginTop: 12, fontSize: 12.5, flexWrap: 'wrap' }}>
        <span className="row ink2" style={{ gap: 5 }}><Repeat size={14} /> {inr(s.amount)}/month</span>
        <span className="row ink2" style={{ gap: 5 }}><CalendarClock size={14} /> {s.installments_paid} paid · next {dueLabel(s.next_due)}</span>
      </div>
      <div className="row" style={{ gap: 14, marginTop: 6, fontSize: 12.5 }}>
        <span className="ink2">Value <b className="num">{inr(s.current_value)}</b></span>
        <span className="ink2">Units <b className="num">{s.units.toFixed(3)}</b></span>
      </div>
      {j && j.status !== 'ON_TRACK' && <SaarthiStrip j={j} />}
      <div className="row" style={{ gap: 8, marginTop: 12 }}>
        <button className="btn btn-soft btn-sm grow" disabled={busy || blocked} onClick={run}>
          {busy ? <Loader2 size={14} className="spin" /> : <FastForward size={14} />} Run next installment
        </button>
        <button className="btn btn-ghost btn-sm" onClick={() => setEdit(true)}><Pencil size={13} /> Amount</button>
      </div>
      <div className="muted" style={{ fontSize: 10.5, marginTop: 6 }}>Sandbox: “Run next installment” fast-forwards to the debit date.</div>
      <EditAmount sip={s} open={edit} onClose={() => setEdit(false)} />
    </div>
  )
}

function EditAmount({ sip, open, onClose }: { sip: Sip; open: boolean; onClose: () => void }) {
  const { bump, showToast } = useApp()
  const [amount, setAmount] = useState(String(sip.amount))
  const [err, setErr] = useState<string | null>(null)
  const n = Number(amount || 0)
  async function save() {
    setErr(null)
    try { await api.updateSip(sip.id, n); showToast(`SIP changed to ${inr(n)}/month`); bump(); onClose() } catch (e) { setErr((e as Error).message) }
  }
  return (
    <Sheet open={open} onClose={onClose} title="Change SIP amount">
      <label className="field" style={{ marginTop: 0 }}>
        <span className="lbl">Monthly amount</span>
        <div className="input-pre"><span>₹</span><input className="input num" inputMode="numeric" value={amount} onChange={e => setAmount(e.target.value.replace(/\D/g, '').slice(0, 7))} /></div>
        <div className="chips-row">{[sip.amount + 1000, sip.amount * 2, sip.mandate.max_amount].filter((v, i, a) => a.indexOf(v) === i).map(v => (
          <button key={v} type="button" className={`chip-btn ${n === v ? 'on' : ''}`} onClick={() => setAmount(String(v))}>{inr(v)}</button>
        ))}</div>
      </label>
      <div className="card card-pad" style={{ background: 'var(--surface-2)', marginTop: 14 }}>
        <div className="kv">
          <span className="k">Current SIP</span><span className="v">{inr(sip.amount)}</span>
          <span className="k">Autopay limit (mandate)</span><span className="v">{inr(sip.mandate.max_amount)}</span>
        </div>
      </div>
      {n > sip.mandate.max_amount && <div className="hint" style={{ marginTop: 10 }}>This is above your autopay limit. The app saves it anyway, just as many real apps do.</div>}
      {err && <div className="form-err">{err}</div>}
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 16 }} onClick={save}>Save</button>
    </Sheet>
  )
}
