import { motion } from 'framer-motion'
import { Bell, Calculator, CalendarClock, CheckCircle2, ChevronRight, Eye, EyeOff, FolderLock, HandCoins, Info, Landmark, Repeat, ShieldCheck, Target, TrendingUp, TriangleAlert } from 'lucide-react'

import { useState } from 'react'
import { AttentionCard, issueCopy } from '../components/journey'
import { BankLogo, CategoryIcon, SaarthiMark, Skeleton } from '../components/ui'
import { SafeToSpendCard } from '../features/planner/widgets'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { dueLabel, greeting, inr } from '../services/format'

export function Home() {
  const { overview: o, push, setTab } = useApp()
  const [hidden, setHidden] = useState(false)
  const { data: plan } = useData(() => api.plannerOverview())
  if (!o) return <div className="page"><Skeleton h={180} /><Skeleton h={60} /><Skeleton h={140} /></div>

  const first = o.user.name.split(' ')[0]
  const handled = o.journeys.filter(j => j.status === 'RESOLVED' || j.status === 'ESCALATED')
  const mask = (v: string) => (hidden ? '₹ ••••••' : v)
  const nextStep = !o.accounts.length ? { t: 'Link your first bank account', s: 'Needed for SIP autopay', f: () => push({ name: 'linkBank' }), I: Landmark }
    : !o.sips.length ? { t: 'Start your first SIP', s: 'Pick a fund in Invest', f: () => setTab('invest'), I: TrendingUp } : null

  return (
    <div>
      <div className="hello">
        <button className="avatar" onClick={() => push({ name: 'profile' })} aria-label="Profile">{o.user.name.split(' ').map(x => x[0]).slice(0, 2).join('')}</button>
        <div className="grow">
          <div className="muted" style={{ fontSize: 12 }}>{greeting()}</div>
          <div style={{ fontWeight: 700, fontSize: 17, letterSpacing: '-0.01em' }}>{first}</div>
        </div>
        <button className="icon-btn" aria-label="Notifications" onClick={() => setTab('saarthi')}><Bell size={18} />{o.attention.length > 0 && <span className="dot" />}</button>
      </div>

      <div className="page">
        <div className="balance-card">
          <div className="between" style={{ position: 'relative', zIndex: 1 }}>
            <div className="lbl">Bank balance · {o.accounts.length} linked account{o.accounts.length === 1 ? '' : 's'}</div>
            <button onClick={() => setHidden(h => !h)} style={{ color: '#fff', opacity: 0.8 }} aria-label="Toggle balance">{hidden ? <EyeOff size={16} /> : <Eye size={16} />}</button>
          </div>
          <div className="amt num">{mask(inr(o.cash))}</div>
          <div className="lbl" style={{ marginTop: 2 }}>Investments {mask(inr(o.portfolio_value))} · Net worth {mask(inr(plan?.net_worth.net_worth ?? o.net_worth))}</div>
          {o.accounts.length > 0 && (
            <div className="balance-split">
              {o.accounts.slice(0, 3).map(a => (
                <div key={a.id}>
                  <div className="k">{a.bank.replace(' Bank', '')} {a.masked}{a.status !== 'VERIFIED' ? ' ⚠' : ''}</div>
                  <div className="v num">{mask(inr(a.balance))}</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="svc-card">
          <div className="svc-title">Money services</div>
          <div className="svc-grid">
            {[
              { l: 'Mutual Funds', I: TrendingUp, f: () => setTab('invest') },
              { l: 'Start SIP', I: Repeat, f: () => setTab('invest') },
              { l: 'Personal Loan', I: HandCoins, f: () => push({ name: 'apply', kind: 'loan' }) },
              { l: 'Health Cover', I: ShieldCheck, f: () => push({ name: 'apply', kind: 'insurance' }) },
              { l: 'Money Plan', I: Target, f: () => setTab('plan') },
              { l: 'Can I Afford?', I: Calculator, f: () => setTab('plan'), isNew: true },
              { l: 'Doc Vault', I: FolderLock, f: () => push({ name: 'vault' }) },
              { l: 'Bank Accounts', I: Landmark, f: () => push({ name: 'banks' }) },
            ].map(({ l, I, f, isNew }) => (
              <button key={l} onClick={f}>
                <span className="si"><I size={20} />{isNew && <span className="new">NEW</span>}</span>{l}
              </button>
            ))}
          </div>
        </div>

        {plan && o.accounts.length > 0 && (
          <div className="section">
            <SafeToSpendCard pulse={plan.pulse} onOpen={() => setTab('plan')} />
          </div>
        )}

        {nextStep && (
          <div className="section">
            <button className="card card-pad card-saarthi row tap" style={{ width: '100%', textAlign: 'left', gap: 12 }} onClick={nextStep.f}>
              <div className="cat-icon cat-investment"><nextStep.I size={20} /></div>
              <div className="grow"><div style={{ fontWeight: 700 }}>{nextStep.t}</div><div className="muted" style={{ fontSize: 12 }}>{nextStep.s}</div></div>
              <ChevronRight size={18} className="muted" />
            </button>
          </div>
        )}

        {o.attention.length > 0 ? (
          <>
            <div className="section">
              <motion.button className="attn-banner tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => setTab('saarthi')} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
                <SaarthiMark size={34} />
                <div className="grow">
                  <div className="big">{o.attention.length} {o.attention.length === 1 ? 'journey needs' : 'journeys need'} your attention</div>
                  <div className="small">Saarthi's agent is on {o.attention.length === 1 ? 'it' : 'each one'}</div>
                </div>
                <ChevronRight size={18} />
              </motion.button>
            </div>
            <div className="section">
              <div className="stack">{o.attention.map((j, i) => <AttentionCard key={j.id} j={j} index={i} />)}</div>
            </div>
          </>
        ) : o.journeys.length > 0 && (
          <div className="section">
            <div className="attn-banner" style={{ background: 'var(--ok)' }}>
              <CheckCircle2 size={26} />
              <div className="grow"><div className="big">Nothing needs your action</div><div className="small">{handled.length ? `Saarthi handled ${handled.length} journey${handled.length === 1 ? '' : 's'} for you` : 'Saarthi is watching quietly'}</div></div>
            </div>
          </div>
        )}

        {o.obligations.length > 0 && (
          <div className="section">
            <div className="section-head"><div className="section-title">Upcoming SIP debits</div></div>
            <div className="card">
              {o.obligations.map(ob => (
                <button key={ob.sip_id} className="list-row" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'journey', id: ob.journey_id })}>
                  <div className="cat-icon" style={{ width: 34, height: 34, background: ob.status === 'failed' ? 'var(--bad-soft)' : 'var(--surface-2)', color: ob.status === 'failed' ? 'var(--bad)' : 'var(--ink-2)' }}>
                    {ob.status === 'failed' ? <TriangleAlert size={16} /> : <CalendarClock size={16} />}
                  </div>
                  <div className="grow"><div className="t">{ob.title}</div><div className="s">{ob.status === 'failed' ? 'Last debit failed' : `Next on ${dueLabel(ob.due)}`}</div></div>
                  <div className="num" style={{ fontWeight: 700 }}>{inr(ob.amount)}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {o.insights.length > 0 && (
          <div className="section">
            <div className="section-head"><div className="section-title">Saarthi insights</div></div>
            <div className="card card-saarthi">
              {o.insights.map(ins => (
                <button key={ins.text} className="insight" style={{ width: '100%', textAlign: 'left' }} onClick={() => ins.journey_id && push({ name: 'journey', id: ins.journey_id })}>
                  {ins.tone === 'ok' ? <CheckCircle2 size={17} color="var(--ok)" /> : ins.tone === 'warn' ? <TriangleAlert size={17} color="var(--warn)" /> : <Info size={17} color="var(--brand)" />}
                  <div className="t">{ins.text}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {handled.length > 0 && (
          <div className="section">
            <div className="section-head"><div className="section-title">Handled by Saarthi</div></div>
            <div className="card">
              {handled.map(j => {
                const c = issueCopy(j)
                return (
                  <button key={j.id} className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => push({ name: 'journey', id: j.id })}>
                    {j.category === 'bank_account' ? <BankLogo bank={j.partner_id} size={34} /> : <CategoryIcon category={j.category} size={34} />}
                    <div className="grow"><div className="t">{j.title}</div><div className="s" style={{ color: c.tone }}>{c.status}</div></div>
                    <ChevronRight size={16} className="muted" />
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
