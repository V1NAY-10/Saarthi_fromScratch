import { ChevronRight, FileCheck2, Landmark, ShieldCheck, UserCheck } from 'lucide-react'
import { issueCopy } from '../components/journey'
import { CategoryIcon, HealthPill, SaarthiMark, Skeleton, StatusPill, TopBar } from '../components/ui'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { inr } from '../services/format'

/** Loans, insurance and KYC: application journeys that share the Document Vault. */
export function Loans() {
  const { overview: o, push } = useApp()
  const { data: lenders } = useData(() => api.catalog('loan'))
  if (!o) return <div className="page"><Skeleton h={200} /></div>
  const apps = o.journeys.filter(j => ['loan', 'insurance', 'kyc'].includes(j.category))
  return (
    <div>
      <TopBar title="Loans & insurance" sub="Applications reuse your Document Vault" />
      <div className="page">
        <button className="card card-pad card-saarthi tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'apply', kind: 'loan' })}>
          <div className="row" style={{ gap: 12 }}>
            <div className="cat-icon cat-loan"><Landmark size={20} /></div>
            <div className="grow"><div style={{ fontWeight: 800 }}>Personal loan up to ₹15 lakh</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>From {Math.min(...(lenders ?? [{ rate: 11.25 }]).map(l => l.rate ?? 99))}% p.a. · documents from your vault</div></div>
            <ChevronRight size={18} className="muted" />
          </div>
          <div className="saarthi-strip" style={{ marginTop: 12 }}><SaarthiMark size={20} /><div className="t">If a lender rejects a document, Saarthi reads the lender's rule, checks your vault and tells you exactly what will pass.</div></div>
        </button>
        <div className="quick" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
          <button onClick={() => push({ name: 'apply', kind: 'insurance' })}><span className="qi"><ShieldCheck size={20} /></span>Health insurance</button>
          <button onClick={() => push({ name: 'apply', kind: 'kyc' })}><span className="qi"><UserCheck size={20} /></span>Re-verify KYC</button>
        </div>

        <div className="section">
          <div className="section-head"><div className="section-title">Your applications</div></div>
          {!apps.length ? <div className="card empty"><FileCheck2 size={22} style={{ marginBottom: 6 }} /><br />No applications yet.</div> : (
            <div className="card">
              {apps.map(j => {
                const c = issueCopy(j)
                return (
                  <button key={j.id} className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'journey', id: j.id })}>
                    <CategoryIcon category={j.category} size={36} />
                    <div className="grow"><div className="t">{j.title}{j.amount ? ` · ${inr(j.amount)}` : ''}</div>
                      <div className="s" style={{ color: j.status === 'ATTENTION' ? c.tone : undefined }}>{j.partner_name.split(' (')[0]} · {j.status === 'ATTENTION' ? c.status : j.stage}</div></div>
                    <div style={{ textAlign: 'right' }}><HealthPill score={j.health_score} /><div style={{ marginTop: 4 }}><StatusPill status={j.status} /></div></div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
        <div className="muted" style={{ fontSize: 11, margin: '12px 4px' }}>Sandbox lenders and insurer. Their names, rules and codes are synthetic.</div>
      </div>
    </div>
  )
}
