import { FlaskConical, Minus, Plus } from 'lucide-react'
import { useState } from 'react'
import { LinkBankForm } from '../components/LinkBankForm'
import { AccountStatus, BankLogo, SaarthiMark, Sheet, Skeleton, TopBar } from '../components/ui'
import { useApp } from '../hooks/useApp'
import { api } from '../services/api'
import { inr } from '../services/format'
import type { Account } from '../services/types'

export function Banks() {
  const { overview: o, push } = useApp()
  const [money, setMoney] = useState<Account | null>(null)
  if (!o) return <div className="page"><Skeleton h={200} /></div>
  return (
    <div>
      <TopBar title="Bank accounts" sub="Autopay sources for your SIPs" />
      <div className="page">
        <div className="card card-pad">
          <div className="muted" style={{ fontSize: 12 }}>Total across {o.accounts.length} account{o.accounts.length === 1 ? '' : 's'}</div>
          <div className="display num" style={{ fontSize: 28, fontWeight: 800, marginTop: 2 }}>{inr(o.cash)}</div>
        </div>
        <div className="section">
          {o.accounts.length === 0 ? <div className="card empty">No bank accounts yet.</div> : (
            <div className="card">
              {o.accounts.map(a => (
                <div key={a.id} className="acct">
                  <BankLogo bank={a.partner_id} />
                  <div className="grow">
                    <div className="between"><div style={{ fontWeight: 700 }}>{a.bank} {a.masked}</div><AccountStatus status={a.status} /></div>
                    <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>Bank record: {a.bank_name_on_record ?? '—'}{a.name_match !== null ? ` · match ${a.name_match.toFixed(2)}` : ''}</div>
                    <div className="between" style={{ marginTop: 8 }}>
                      <div className="num" style={{ fontWeight: 800, fontSize: 16 }}>{inr(a.balance)}</div>
                      <div className="row" style={{ gap: 6 }}>
                        {a.journey_id && a.status !== 'VERIFIED' && <button className="btn btn-soft btn-sm" onClick={() => push({ name: 'journey', id: a.journey_id! })}><SaarthiMark size={16} /> Saarthi</button>}
                        <button className="btn btn-ghost btn-sm" onClick={() => setMoney(a)}><FlaskConical size={13} /> Balance</button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} onClick={() => push({ name: 'linkBank' })}><Plus size={16} /> Link a bank account</button>
        </div>
      </div>
      <BalanceSheet account={money} onClose={() => setMoney(null)} />
    </div>
  )
}

export function BalanceSheet({ account, onClose }: { account: Account | null; onClose: () => void }) {
  const { bump, showToast } = useApp()
  const [amt, setAmt] = useState('5000')
  const [err, setErr] = useState<string | null>(null)
  async function go(sign: 1 | -1) {
    if (!account) return
    setErr(null)
    try {
      const a = await api.adjustBalance(account.id, sign * Number(amt || 0))
      showToast(`${a.bank} ${a.masked}: balance now ${inr(a.balance)}`)
      bump(); onClose()
    } catch (e) { setErr((e as Error).message) }
  }
  return (
    <Sheet open={!!account} onClose={onClose} title="Change balance (sandbox)">
      {account && <>
        <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.5 }}>Simulates money arriving in or leaving <b>{account.bank} {account.masked}</b> outside the app, like a salary credit or a card payment. Current balance {inr(account.balance)}.</div>
        <label className="field">
          <span className="lbl">Amount</span>
          <div className="input-pre"><span>₹</span><input className="input num" inputMode="numeric" value={amt} onChange={e => setAmt(e.target.value.replace(/\D/g, '').slice(0, 8))} /></div>
          <div className="chips-row">{['1000', '5000', '25000'].map(v => <button key={v} className={`chip-btn ${amt === v ? 'on' : ''}`} onClick={() => setAmt(v)}>₹{Number(v).toLocaleString('en-IN')}</button>)}</div>
        </label>
        {err && <div className="form-err">{err}</div>}
        <div className="row" style={{ gap: 8, marginTop: 16 }}>
          <button className="btn btn-ghost btn-lg grow" onClick={() => go(-1)}><Minus size={16} /> Withdraw</button>
          <button className="btn btn-primary btn-lg grow" onClick={() => go(1)}><Plus size={16} /> Add money</button>
        </div>
      </>}
    </Sheet>
  )
}

export function LinkBank() {
  const { pop, replace, overview, bump, showToast } = useApp()
  return (
    <div>
      <TopBar title="Link a bank account" sub="Verified by a Re 1 penny drop" onBack={pop} />
      <div className="page">
        <LinkBankForm userName={overview?.user.name ?? ''} onDone={a => {
          bump()
          if (a.status === 'VERIFIED') { showToast(`${a.bank} ${a.masked} verified`); pop() }
          else { showToast(`${a.bank} couldn't verify the account. Saarthi is on it.`); replace({ name: 'journey', id: a.journey_id! }) }
        }} />
      </div>
    </div>
  )
}
