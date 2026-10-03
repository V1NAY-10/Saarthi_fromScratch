import { AnimatePresence, motion } from 'framer-motion'
import { ArrowLeft, BadgeCheck, ChevronRight, Landmark, Loader2, ShieldCheck, Sparkles, TrendingUp, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { LinkBankForm } from '../components/LinkBankForm'
import { SaarthiMark } from '../components/ui'
import { useApp } from '../hooks/useApp'
import { api, setApiUser } from '../services/api'
import type { Account, Profile } from '../services/types'

type Step = 'welcome' | 'register' | 'kyc' | 'bank' | 'done'

export function Onboarding() {
  const { signIn } = useApp()
  const [step, setStep] = useState<Step>('welcome')
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [user, setUser] = useState<Profile | null>(null)
  const [account, setAccount] = useState<Account | null>(null)

  useEffect(() => { api.profiles().then(setProfiles).catch(() => setProfiles([])) }, [])

  const idx = ['register', 'kyc', 'bank'].indexOf(step)
  return (
    <div className="onb">
      {idx >= 0 && (
        <div className="row" style={{ marginBottom: 6 }}>
          {step === 'register' && <button className="icon-btn" onClick={() => setStep('welcome')} aria-label="Back"><ArrowLeft size={18} /></button>}
          <div className="onb-steps grow">{[0, 1, 2].map(i => <i key={i} className={i <= idx ? 'on' : ''} />)}</div>
        </div>
      )}
      <AnimatePresence mode="wait">
        <motion.div key={step} initial={{ opacity: 0, x: 14 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -14 }} transition={{ duration: 0.18 }} style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {step === 'welcome' && <Welcome profiles={profiles} onNew={() => setStep('register')} onContinue={p => signIn(p.id)} />}
          {step === 'register' && <Register onDone={u => { setUser(u); setApiUser(u.id); setStep('kyc') }} />}
          {step === 'kyc' && user && <Kyc user={user} onDone={() => setStep('bank')} />}
          {step === 'bank' && user && (
            <div>
              <h2 className="display" style={{ fontSize: 24, fontWeight: 800, marginTop: 8 }}>Link a bank account</h2>
              <p className="ink2" style={{ fontSize: 13.5, marginTop: 6, lineHeight: 1.5 }}>Your SIPs will be paid from here by autopay. The bank sends Re 1 to check the account is yours.</p>
              <LinkBankForm userName={user.name} onDone={a => { setAccount(a); setStep('done') }} />
              <button className="btn btn-ghost btn-block" style={{ marginTop: 10 }} onClick={() => signIn(user.id)}>Skip for now</button>
            </div>
          )}
          {step === 'done' && user && account && <Done account={account} onFinish={() => signIn(user.id)} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function Welcome({ profiles, onNew, onContinue }: { profiles: Profile[]; onNew: () => void; onContinue: (p: Profile) => void }) {
  return (
    <>
      <div className="onb-hero">
        <SaarthiMark size={52} />
        <h1>Invest without getting stuck.</h1>
        <p>Start a SIP in minutes. If a bank rejects a payment or can't verify your account, Saarthi's AI agent works out why and fixes it safely, with your approval.</p>
      </div>
      <div className="card card-pad" style={{ marginTop: 18 }}>
        {[
          { I: UserRound, t: 'Sign up & KYC', s: 'PAN verified against the registry' },
          { I: Landmark, t: 'Link your bank', s: 'Penny-drop verification' },
          { I: TrendingUp, t: 'Start a SIP', s: 'Autopay mandate + first installment' },
          { I: Sparkles, t: 'Saarthi handles failures', s: 'Diagnose → decide → act → verify' },
        ].map(({ I, t, s }) => (
          <div key={t} className="onb-feature"><div className="fi"><I size={17} /></div><div><div style={{ fontWeight: 700, fontSize: 13.5 }}>{t}</div><div className="muted" style={{ fontSize: 12 }}>{s}</div></div></div>
        ))}
      </div>
      <div style={{ flex: 1 }} />
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 18 }} onClick={onNew}>Create account</button>
      {profiles.length > 0 && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="eyebrow" style={{ padding: '12px 14px 0' }}>Continue as</div>
          {profiles.slice(0, 4).map(p => (
            <button key={p.id} className="list-row tap" style={{ width: '100%', textAlign: 'left' }} onClick={() => onContinue(p)}>
              <div className="avatar" style={{ width: 34, height: 34, fontSize: 12 }}>{p.name.split(' ').map(x => x[0]).slice(0, 2).join('')}</div>
              <div className="grow"><div className="t">{p.name}</div><div className="s">{p.phone} · PAN {p.pan_masked}</div></div>
              <ChevronRight size={16} className="muted" />
            </button>
          ))}
        </div>
      )}
    </>
  )
}

function Register({ onDone }: { onDone: (u: Profile) => void }) {
  const [f, setF] = useState({ name: '', phone: '', email: '', dob: '', pan: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null); setBusy(true)
    try { onDone(await api.register(f)) } catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }
  return (
    <form onSubmit={submit}>
      <h2 className="display" style={{ fontSize: 24, fontWeight: 800, marginTop: 8 }}>Create your account</h2>
      <p className="ink2" style={{ fontSize: 13.5, marginTop: 6 }}>Use your details exactly as they appear on your PAN.</p>
      <label className="field"><span className="lbl">Full name (as on PAN)</span><input className="input" value={f.name} onChange={set('name')} placeholder="Rohan Kumar Verma" autoComplete="name" /></label>
      <label className="field"><span className="lbl">PAN</span><input className="input mono" value={f.pan} onChange={e => setF({ ...f, pan: e.target.value.toUpperCase().slice(0, 10) })} placeholder="ABCPV1234K" /></label>
      <div className="hint">Sandbox: any well-formed individual PAN works (5 letters, 4 digits, 1 letter; 4th letter P).</div>
      <label className="field"><span className="lbl">Date of birth</span><input className="input" type="date" value={f.dob} onChange={set('dob')} /></label>
      <label className="field"><span className="lbl">Mobile number</span><div className="input-pre"><span>+91</span><input className="input num" style={{ paddingLeft: 48 }} inputMode="numeric" value={f.phone} onChange={e => setF({ ...f, phone: e.target.value.replace(/\D/g, '').slice(0, 10) })} placeholder="98765 43210" /></div></label>
      <label className="field"><span className="lbl">Email</span><input className="input" type="email" value={f.email} onChange={set('email')} placeholder="you@example.com" autoComplete="email" /></label>
      {err && <div className="form-err">{err}</div>}
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 18 }} disabled={busy}>
        {busy ? <><Loader2 size={18} className="spin" /> Verifying PAN…</> : 'Continue'}
      </button>
    </form>
  )
}

function Kyc({ user, onDone }: { user: Profile; onDone: () => void }) {
  const [shown, setShown] = useState(0)
  const ok = user.kyc_status === 'VERIFIED'
  const steps = ['PAN format validated', `PAN ${user.pan_masked} found in registry`, 'Name & date of birth matched', ok ? 'KYC verified' : 'KYC failed']
  useEffect(() => {
    if (shown >= steps.length) return
    const t = window.setTimeout(() => setShown(s => s + 1), 420)
    return () => window.clearTimeout(t)
  }, [shown, steps.length])
  return (
    <div>
      <h2 className="display" style={{ fontSize: 24, fontWeight: 800, marginTop: 8 }}>Verifying your identity</h2>
      <p className="ink2" style={{ fontSize: 13.5, marginTop: 6 }}>Hi {user.name.split(' ')[0]}, we're checking your PAN with the registry.</p>
      <div className="card card-pad" style={{ marginTop: 16 }}>
        {steps.map((s, i) => (
          <div key={s} className="kyc-step" style={{ opacity: i < shown ? 1 : 0.4 }}>
            {i < shown ? <BadgeCheck size={20} color={i === 3 && !ok ? 'var(--bad)' : 'var(--ok)'} /> : <Loader2 size={20} className={i === shown ? 'spin' : ''} color="var(--ink-3)" />}
            {s}
          </div>
        ))}
      </div>
      {shown >= steps.length && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="safe-note" style={{ marginTop: 14 }}><ShieldCheck size={16} style={{ flexShrink: 0, marginTop: 1 }} /><span>Your PAN is saved to your document vault as verified KYC evidence.</span></div>
          <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 16 }} onClick={onDone}>Link a bank account</button>
        </motion.div>
      )}
    </div>
  )
}

function Done({ account, onFinish }: { account: Account; onFinish: () => void }) {
  const ok = account.status === 'VERIFIED'
  return (
    <div style={{ textAlign: 'center', paddingTop: 30 }}>
      <div className="success-badge" style={ok ? undefined : { background: 'var(--warn-soft)', color: 'var(--warn)' }}>{ok ? <BadgeCheck size={34} /> : <SaarthiMark size={34} />}</div>
      <h2 className="display" style={{ fontSize: 22, fontWeight: 800, marginTop: 14 }}>{ok ? 'Bank account verified' : "The bank couldn't verify this account"}</h2>
      <p className="ink2" style={{ fontSize: 13.5, marginTop: 8, lineHeight: 1.5 }}>
        {ok ? `${account.bank} ${account.masked} is ready for autopay. Next, pick a fund and start a SIP.`
          : `${account.bank} has the account under “${account.bank_name_on_record}”. Saarthi is already investigating. You'll see what it found on the home screen.`}
      </p>
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 22 }} onClick={onFinish}>{ok ? 'Go to app' : 'See what Saarthi found'}</button>
    </div>
  )
}
