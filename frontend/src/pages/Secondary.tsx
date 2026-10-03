import { BadgeCheck, BookOpen, ChevronRight, Clock, FileText, LogOut } from 'lucide-react'
import { JourneyRow } from '../components/journey'
import { Skeleton, TierBadge, TopBar } from '../components/ui'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { PARTNER_SHORT, dateTime } from '../services/format'

export function JourneysList() {
  const { pop } = useApp()
  const { data } = useData(() => api.journeys())
  return (
    <div>
      <TopBar title="My Journeys" sub="Every financial process, one view" onBack={pop} />
      <div className="page">
        {!data ? <Skeleton h={300} /> : !data.length ? <div className="card empty">No journeys yet.</div> : (
          (['investment', 'bank_account'] as const).map(cat => {
            const js = data.filter(j => j.category === cat)
            if (!js.length) return null
            return (
              <div key={cat} className="section" style={{ marginTop: 14 }}>
                <div className="eyebrow" style={{ margin: '0 4px 8px' }}>{{ investment: 'SIPs', bank_account: 'Bank verification' }[cat]}</div>
                <div className="card">{js.map(j => <JourneyRow key={j.id} j={j} />)}</div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

const DOC_STATUS: Record<string, [string, string]> = {
  VERIFIED: ['Verified', 'pill-ok'], FAILED: ['Failed', 'pill-bad'], UNDER_REVIEW: ['Under review', 'pill-warn'],
}

export function Profile() {
  const { overview, push, signOut } = useApp()
  const { data } = useData(() => api.documents())
  const u = overview?.user
  return (
    <div>
      <TopBar title="Profile" sub="Identity, documents & knowledge" />
      <div className="page">
        {u && (
          <div className="card card-pad row" style={{ gap: 12 }}>
            <div className="avatar" style={{ width: 46, height: 46 }}>{u.name.split(' ').map(x => x[0]).slice(0, 2).join('')}</div>
            <div className="grow">
              <div style={{ fontWeight: 700 }}>{u.name}</div>
              <div className="muted" style={{ fontSize: 12 }}>{u.phone} · PAN {u.pan_masked}</div>
            </div>
            {u.kyc_status === 'VERIFIED' ? <span className="pill pill-ok"><BadgeCheck size={12} /> KYC</span> : <span className="pill pill-bad">KYC {u.kyc_status.toLowerCase()}</span>}
          </div>
        )}
        <div className="section">
          <div className="section-head"><div className="section-title">Document vault</div></div>
          {!data ? <Skeleton h={100} /> : !data.length ? <div className="card empty">No documents.</div> : (
            <div className="stack">
              {data.map(d => {
                const [label, cls] = DOC_STATUS[d.status] ?? [d.status, 'pill-neutral']
                return (
                  <div key={d.id} className="card card-pad row" style={{ alignItems: 'flex-start', gap: 12 }}>
                    <div className="cat-icon" style={{ width: 36, height: 36, background: 'var(--surface-2)', color: 'var(--brand)' }}><FileText size={17} /></div>
                    <div className="grow">
                      <div className="between"><div style={{ fontWeight: 700, fontSize: 13.5 }}>{d.name}</div><span className={`pill ${cls}`}>{label}</span></div>
                      <div className="muted row" style={{ fontSize: 11.5, marginTop: 4, gap: 5 }}><Clock size={11} /> {dateTime(d.updated_at)} · {d.source}</div>
                      {d.meta.number && <div className="ink2 mono" style={{ fontSize: 12, marginTop: 4 }}>{d.meta.number} · {d.meta.name}</div>}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
        <div className="section">
          <div className="card">
            <button className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'knowledge' })}>
              <div className="cat-icon cat-investment" style={{ width: 34, height: 34 }}><BookOpen size={16} /></div>
              <div className="grow"><div className="t">Failure knowledge</div><div className="s">Bank codes, rules & what Saarthi has learned</div></div>
              <ChevronRight size={16} className="muted" />
            </button>
            <button className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={signOut}>
              <div className="cat-icon" style={{ width: 34, height: 34, background: 'var(--bad-soft)', color: 'var(--bad)' }}><LogOut size={16} /></div>
              <div className="grow"><div className="t">Sign out</div><div className="s">Switch to another profile</div></div>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function Knowledge() {
  const { pop } = useApp()
  const { data } = useData(() => api.knowledge())
  const codes = data?.filter(k => k.kind === 'failure_code') ?? []
  const policies = data?.filter(k => k.kind !== 'failure_code') ?? []
  return (
    <div>
      <TopBar title="Failure knowledge" sub="What Saarthi knows about partner failures" onBack={pop} />
      <div className="page">
        {!data ? <Skeleton h={300} /> : <>
          <div className="eyebrow" style={{ margin: '6px 4px 8px' }}>Bank codes → standard failures</div>
          <div className="card">
            {codes.map(k => (
              <div key={k.id} className="list-row" style={{ alignItems: 'flex-start' }}>
                <div className="grow">
                  <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
                    <span className="chip">{PARTNER_SHORT[k.partner_id ?? ''] ?? k.partner_id}</span>
                    <span className="code-chip" style={{ fontSize: 10.5 }}>{k.code}</span>
                  </div>
                  <div className="t" style={{ marginTop: 6 }}>{k.data.meaning}</div>
                  <div className="s mono" style={{ fontSize: 10.5 }}>{k.data.standard_code}</div>
                  <div className="s" style={{ marginTop: 3 }}>{k.learned ? `Learned: ${k.learned.resolved}/${k.learned.occurrences} incidents resolved · last ${k.learned.last_outcome?.toLowerCase()}` : 'Not seen yet'}</div>
                </div>
                <TierBadge tier={k.data.action_tier} />
              </div>
            ))}
          </div>
          <div className="eyebrow" style={{ margin: '20px 4px 8px' }}>Policies & requirements (retrieved by BM25)</div>
          <div className="card">
            {policies.map(k => (
              <div key={k.id} className="list-row" style={{ alignItems: 'flex-start' }}>
                <div className="grow">
                  <div className="t">{k.title}</div>
                  <div className="s" style={{ lineHeight: 1.45, marginTop: 3 }}>{k.body}</div>
                  <span className="chip" style={{ marginTop: 6 }}>{k.kind.replace('_', ' ')}</span>
                </div>
              </div>
            ))}
          </div>
        </>}
      </div>
    </div>
  )
}
