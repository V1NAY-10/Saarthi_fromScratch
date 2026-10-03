import { FlaskConical, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../services/api'
import { BANKS } from '../services/format'
import type { Account } from '../services/types'
import { BankLogo } from './ui'

/** Link a bank account. The dashed "sandbox" box holds what the *bank* knows (name on its record,
 *  whose PAN it has, the balance). In production those come from the bank; here the presenter sets
 *  them to create realistic situations, and Saarthi only learns them through the bank's APIs. */
export function LinkBankForm({ userName, onDone, cta = 'Link & verify' }: { userName: string; onDone: (a: Account) => void; cta?: string }) {
  const [bank, setBank] = useState('hdfc')
  const [accountNo, setAccountNo] = useState('')
  const [holder, setHolder] = useState(userName)
  const [balance, setBalance] = useState('25000')
  const [owner, setOwner] = useState<'self' | 'other'>('self')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function submit() {
    setErr(null); setBusy(true)
    try {
      onDone(await api.linkAccount({ bank, account_no: accountNo, holder_name: holder, opening_balance: Number(balance || 0), owner }))
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div>
      <div className="field">
        <span className="lbl">Bank</span>
        <div className="pick-grid">
          {BANKS.map(b => (
            <button key={b.id} type="button" className={`pick row ${bank === b.id ? 'on' : ''}`} style={{ gap: 10 }} onClick={() => setBank(b.id)}>
              <BankLogo bank={b.id} size={30} />
              <div><div className="pt">{b.name}</div><div className="ps">{b.dialect}</div></div>
            </button>
          ))}
        </div>
      </div>
      <label className="field">
        <span className="lbl">Account number</span>
        <input className="input mono" inputMode="numeric" value={accountNo} onChange={e => setAccountNo(e.target.value.replace(/\D/g, '').slice(0, 18))} placeholder="9 to 18 digits" />
      </label>

      <div className="sandbox">
        <div className="sandbox-tag"><FlaskConical size={12} /> Sandbox · what the bank has on record</div>
        <label className="field" style={{ marginTop: 10 }}>
          <span className="lbl">Account holder name at the bank</span>
          <input className="input" value={holder} onChange={e => setHolder(e.target.value)} />
          <div className="chips-row">
            {[userName, initials(userName), 'Suresh Patel'].filter((v, i, a) => v && a.indexOf(v) === i).map(n => (
              <button key={n} type="button" className={`chip-btn ${holder === n ? 'on' : ''}`} onClick={() => setHolder(n)}>{n}</button>
            ))}
          </div>
          <div className="hint">Your PAN says <b>{userName}</b>. Penny-drop verification compares the two.</div>
        </label>
        <div className="field">
          <span className="lbl">Whose PAN is linked to this account at the bank?</span>
          <div className="pick-grid">
            <button type="button" className={`pick ${owner === 'self' ? 'on' : ''}`} onClick={() => setOwner('self')}><div className="pt">Mine</div><div className="ps">My own account</div></button>
            <button type="button" className={`pick ${owner === 'other' ? 'on' : ''}`} onClick={() => setOwner('other')}><div className="pt">Someone else</div><div className="ps">e.g. a parent's account</div></button>
          </div>
          <div className="hint">Saarthi can't see this. It can only find out by asking the bank via Account Aggregator, with your consent.</div>
        </div>
        <label className="field">
          <span className="lbl">Balance</span>
          <div className="input-pre"><span>₹</span><input className="input num" inputMode="numeric" value={balance} onChange={e => setBalance(e.target.value.replace(/\D/g, '').slice(0, 8))} /></div>
          <div className="chips-row">
            {['2000', '25000', '100000'].map(v => <button key={v} type="button" className={`chip-btn ${balance === v ? 'on' : ''}`} onClick={() => setBalance(v)}>₹{Number(v).toLocaleString('en-IN')}</button>)}
          </div>
        </label>
      </div>

      {err && <div className="form-err">{err}</div>}
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 16 }} disabled={busy || accountNo.length < 9} onClick={submit}>
        {busy ? <><Loader2 size={18} className="spin" /> Verifying with the bank…</> : cta}
      </button>
    </div>
  )
}

function initials(name: string) {
  const p = name.trim().split(/\s+/)
  if (p.length < 2) return ''
  return [...p.slice(0, -1).map(x => x[0].toUpperCase()), p[p.length - 1]].join(' ')
}
