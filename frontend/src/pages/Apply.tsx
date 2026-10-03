import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, ChevronRight, FilePlus2, Landmark, Loader2, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { UploadSheet } from '../components/UploadSheet'
import { AccountStatus, BankLogo, SaarthiMark, Skeleton, TopBar } from '../components/ui'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { inr } from '../services/format'
import type { PartnerOffer, Precheck } from '../services/types'

const KIND_TITLE: Record<string, string> = { loan: 'Personal loan', insurance: 'Health insurance', kyc: 'Re-verify KYC' }

/** Generic application flow for loans, insurance and KYC. */
export function Apply({ kind, partnerId }: { kind: string; partnerId?: string }) {
  const { pop, overview, replace, bump, showToast } = useApp()
  const { data: offers } = useData(() => api.catalog(kind), [kind])
  const [partner, setPartner] = useState<PartnerOffer | null>(null)
  const [amount, setAmount] = useState(300000)
  const [tenure, setTenure] = useState(24)
  const [income, setIncome] = useState('90000')
  const [acc, setAcc] = useState<string | null>(null)
  const [pre, setPre] = useState<Precheck | null>(null)
  const [sel, setSel] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [uploadFor, setUploadFor] = useState<string | null>(null)

  useEffect(() => {
    if (offers && !partner && (partnerId || offers.length === 1)) setPartner(offers.find(o => o.partner_id === partnerId) ?? offers[0])
  }, [offers, partner, partnerId])

  const accounts = overview?.accounts ?? []
  const accountId = acc ?? accounts.find(a => a.status === 'VERIFIED')?.id ?? null

  function applyPrecheck(p: Precheck) {
    setPre(p)
    setSel(s => {
      const out: Record<string, string> = {}
      for (const i of p.checklist) {
        const keep = i.candidates.find(c => c.document_id === s[i.role])
        const pick = keep ?? i.candidates[0]
        if (pick) out[i.role] = pick.document_id
      }
      return out
    })
  }

  async function start() {
    if (!partner) return
    setErr(null); setBusy(true)
    try {
      applyPrecheck(await api.startApplication({ partner_id: partner.partner_id, amount, tenure_months: tenure,
        monthly_income: Number(income || 0), account_id: kind === 'kyc' ? undefined : accountId ?? undefined }))
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  async function submit() {
    if (!pre) return
    setBusy(true); setErr(null)
    try {
      const r = await api.submitApplication(pre.journey_id, sel)
      bump()
      if (r.status === 'SUCCESS') showToast(kind === 'loan' ? 'Approved and disbursed' : kind === 'insurance' ? 'Policy issued' : 'Identity verified')
      else showToast(`${partner?.name.split(' (')[0]} returned ${r.code}. Saarthi is investigating.`)
      replace({ name: 'journey', id: pre.journey_id })
    } catch (e) { setErr((e as Error).message); setBusy(false) }
  }

  // ---- step 1: choose a partner
  if (!partner) {
    return (
      <div>
        <TopBar title={KIND_TITLE[kind]} sub="Choose a sandbox partner" onBack={pop} />
        <div className="page">
          {!offers ? <Skeleton h={200} /> : <div className="stack">{offers.map(o => (
            <button key={o.partner_id} className="card card-pad tap" style={{ textAlign: 'left', width: '100%' }} onClick={() => setPartner(o)}>
              <div className="between"><div style={{ fontWeight: 800 }}>{o.name}</div><ChevronRight size={16} className="muted" /></div>
              <div className="row" style={{ gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                {o.rate && <span className="pill pill-info">{o.rate}% p.a.</span>}
                {o.tagline && <span className="chip">{o.tagline}</span>}
              </div>
              <div className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>Needs: {o.requirements.map(r => r.label.split(':')[0]).join(' · ')}</div>
            </button>
          ))}</div>}
        </div>
      </div>
    )
  }

  // ---- step 3: documents
  if (pre) {
    const blocked = pre.checklist.some(i => !sel[i.role])
    const warn = pre.checklist.some(i => { const c = i.candidates.find(x => x.document_id === sel[i.role]); return c && !c.ok })
    return (
      <div>
        <TopBar title="Documents" sub={partner.name} onBack={pop} />
        <div className="page page-tight">
          <motion.div className="card card-pad card-saarthi" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            <div className="row"><SaarthiMark size={22} /><div style={{ fontWeight: 700, fontSize: 13.5 }}>{pre.saarthi_note}</div></div>
            {pre.problems.map(p => <div key={p} className="row" style={{ gap: 6, marginTop: 8, fontSize: 12.5, color: 'var(--warn)', fontWeight: 600 }}><AlertTriangle size={14} /> {p}</div>)}
            {pre.missing.map(m => <div key={m} className="row" style={{ gap: 6, marginTop: 8, fontSize: 12.5, color: 'var(--bad)', fontWeight: 600 }}><AlertTriangle size={14} /> {m} not in your vault</div>)}
            {!pre.problems.length && !pre.missing.length && <div className="row" style={{ gap: 6, marginTop: 8, fontSize: 12.5, color: 'var(--ok)', fontWeight: 600 }}><CheckCircle2 size={14} /> Everything meets {partner.name.split(' (')[0]}'s published rules</div>}
          </motion.div>

          {pre.checklist.map(i => (
            <div key={i.role} className="card card-pad" style={{ marginTop: 10 }}>
              <div className="between"><div style={{ fontWeight: 700 }}>{i.label}</div><button className="section-link" onClick={() => setUploadFor(i.doc_type)}><FilePlus2 size={13} /> Upload</button></div>
              <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>Rule: {i.requirement}</div>
              {!i.candidates.length && <div className="hint" style={{ color: 'var(--bad)' }}>Nothing in your vault yet. If you submit without it, the partner will reject the application.</div>}
              {i.candidates.map(c => (
                <button key={c.document_id} className={`pick ${sel[i.role] === c.document_id ? 'on' : ''}`} style={{ width: '100%', marginTop: 8 }}
                  onClick={() => setSel(s => ({ ...s, [i.role]: c.document_id }))}>
                  <div className="between"><div className="pt">{c.name} v{c.version}</div>
                    {c.ok ? <span className="pill pill-ok">Meets rule</span> : <span className="pill pill-warn">Won't pass</span>}</div>
                  <div className="ps">{c.summary}</div>
                  {c.evidence?.map(e => <div key={e.required} className="ps" style={{ color: 'var(--warn)', marginTop: 3 }}>Needs {e.required} · has {e.found}</div>)}
                </button>
              ))}
              {i.candidates.length > 0 && <button className="section-link" style={{ marginTop: 8 }} onClick={() => setSel(s => { const n = { ...s }; delete n[i.role]; return n })}>Don't attach</button>}
            </div>
          ))}
          {err && <div className="form-err">{err}</div>}
        </div>
        <div className="cta-bar">
          <button className="btn btn-primary btn-lg btn-block" disabled={busy} onClick={submit}>
            {busy ? <><Loader2 size={18} className="spin" /> Sending to partner…</> : warn || blocked ? 'Submit anyway' : `Submit to ${partner.name.split(' (')[0]}`}
          </button>
          <div className="hint"><ShieldCheck size={13} /> Only the documents shown are shared, exactly these versions.</div>
        </div>
        <UploadSheet open={!!uploadFor} onClose={() => setUploadFor(null)} want={uploadFor ?? undefined}
          onDone={async () => applyPrecheck(await api.precheck(pre.journey_id))} />
      </div>
    )
  }

  // ---- step 2: details
  return (
    <div>
      <TopBar title={KIND_TITLE[kind]} sub={partner.name} onBack={pop} />
      <div className="page page-tight">
        {kind === 'loan' && <>
          <div className="card card-pad">
            <div className="muted" style={{ fontSize: 12 }}>Loan amount</div>
            <div className="display num" style={{ fontSize: 30, fontWeight: 800 }}>{inr(amount)}</div>
            <input type="range" min={50000} max={partner.max_amount ?? 1000000} step={10000} value={amount} onChange={e => setAmount(Number(e.target.value))} style={{ width: '100%', marginTop: 8 }} />
            <div className="field"><span className="lbl">Tenure</span><div className="chips-row" style={{ marginTop: 0 }}>
              {[12, 24, 36, 48, 60].map(t => <button key={t} className={`chip-btn ${tenure === t ? 'on' : ''}`} onClick={() => setTenure(t)}>{t} mo</button>)}
            </div></div>
            <label className="field"><span className="lbl">Monthly income (as declared)</span>
              <div className="input-pre"><span>₹</span><input className="input num" inputMode="numeric" value={income} onChange={e => setIncome(e.target.value.replace(/\D/g, '').slice(0, 8))} /></div>
              <div className="hint">The lender checks this against your salary slip.</div>
            </label>
            {partner.rate && <div className="kv" style={{ marginTop: 12 }}><span className="k">Interest</span><span className="v">{partner.rate}% p.a.</span>
              <span className="k">EMI (approx.)</span><span className="v num">{inr(emi(amount, partner.rate, tenure))}</span></div>}
          </div>
        </>}
        {kind === 'insurance' && (
          <div className="card card-pad">
            <div style={{ fontWeight: 800, fontSize: 16 }}>{partner.plan}</div>
            <div className="kv" style={{ marginTop: 10 }}><span className="k">Cover</span><span className="v">{inr(partner.cover)}</span>
              <span className="k">Premium</span><span className="v">{inr(partner.premium_per_year)} / year</span></div>
          </div>
        )}
        {kind === 'kyc' && <div className="card card-pad ink2" style={{ fontSize: 13, lineHeight: 1.5 }}>Submit an identity document to the sandbox KYC registry. Saarthi checks it against your KYC record first.</div>}
        {kind !== 'kyc' && (
          <div className="field">
            <span className="lbl">{kind === 'loan' ? 'Disbursal account' : 'Pay premium from'}</span>
            {!accounts.length ? <div className="hint"><Landmark size={12} /> Link a bank account first.</div> : accounts.map(a => (
              <button key={a.id} className={`pick row ${accountId === a.id ? 'on' : ''}`} style={{ width: '100%', gap: 10, marginTop: 6 }} onClick={() => setAcc(a.id)}>
                <BankLogo bank={a.partner_id} size={28} />
                <div className="grow"><div className="pt">{a.bank} {a.masked}</div><div className="ps">Balance {inr(a.balance)}</div></div>
                <AccountStatus status={a.status} />
              </button>
            ))}
          </div>
        )}
        <div className="card card-pad" style={{ marginTop: 12, background: 'var(--surface-2)' }}>
          <div className="eyebrow">{partner.name.split(' (')[0]} will ask for</div>
          {partner.requirements.map(r => <div key={r.doc_type} style={{ fontSize: 12.5, marginTop: 6 }}>• {r.label}</div>)}
        </div>
        {err && <div className="form-err">{err}</div>}
      </div>
      <div className="cta-bar">
        <button className="btn btn-primary btn-lg btn-block" disabled={busy || (kind !== 'kyc' && !accountId)} onClick={start}>
          {busy ? <><Loader2 size={18} className="spin" /> Checking your vault…</> : 'Continue to documents'}
        </button>
      </div>
    </div>
  )
}

function emi(p: number, rate: number, n: number) {
  const r = rate / 1200
  return Math.round(p * r * (1 + r) ** n / ((1 + r) ** n - 1))
}
