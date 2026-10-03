import { AnimatePresence, animate, motion } from 'framer-motion'
import { ArrowLeft, Check, Landmark, PiggyBank, ShieldCheck, TrendingUp, UserCheck, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { TIER_TEXT, bankMeta, fundColor } from '../services/format'
import type { JourneyStatus, Tier } from '../services/types'

/* Saarthi mark: two points joined by a guiding path */
export function SaarthiMark({ size = 22, className = '' }: { size?: number; className?: string }) {
  const s = size * 0.62
  return (
    <span className={`smark ${className}`} style={{ width: size, height: size, borderRadius: size * 0.32 }}>
      <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
        <path d="M5 16.5c0-3 2.6-4.6 7-4.6s7-1.6 7-4.4" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="5" cy="16.5" r="2.5" fill="#fff" />
        <circle cx="19" cy="7.5" r="2.5" fill="#fff" />
      </svg>
    </span>
  )
}

export function bandColor(score: number) {
  if (score >= 85) return 'var(--ok)'
  if (score >= 60) return '#d59a00'
  if (score >= 35) return 'var(--warn)'
  return 'var(--bad)'
}

export function HealthRing({ score, size = 72, stroke = 7, from, label = 'HEALTH' }:
  { score: number; size?: number; stroke?: number; from?: number; label?: string }) {
  const [shown, setShown] = useState(from ?? score)
  useEffect(() => {
    const c = animate(from ?? shown, score, { duration: from !== undefined ? 1.6 : 0.6, ease: [0.2, 0.8, 0.2, 1], onUpdate: v => setShown(Math.round(v)) })
    return () => c.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [score, from])
  const r = (size - stroke) / 2
  const C = 2 * Math.PI * r
  const color = bandColor(shown)
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--line)" strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={C} strokeDashoffset={C * (1 - shown / 100)} style={{ transition: 'stroke 0.4s' }} />
      </svg>
      <div className="ring-val">
        <div>
          <div className="ring-num" style={{ fontSize: size * 0.32, color }}>{shown}</div>
          {size >= 64 && <div className="ring-sub">{label}</div>}
        </div>
      </div>
    </div>
  )
}

export function HealthPill({ score }: { score: number }) {
  return (
    <span className="hp" style={{ color: bandColor(score) }}>
      <span className="bar"><i style={{ width: `${score}%`, background: bandColor(score) }} /></span>
      {score}
    </span>
  )
}

const STATUS: Record<JourneyStatus, [string, string]> = {
  ATTENTION: ['Attention required', 'pill-bad'],
  ESCALATED: ['With specialist', 'pill-warn'],
  RESOLVED: ['Resolved', 'pill-ok'],
  ON_TRACK: ['On track', 'pill-ok'],
  COMPLETE: ['Complete', 'pill-ok'],
}
export function StatusPill({ status }: { status: JourneyStatus }) {
  const [t, c] = STATUS[status] ?? [status, 'pill-neutral']
  return <span className={`pill ${c}`}><span className="pd" />{t}</span>
}

export function TierBadge({ tier, long = false }: { tier: Tier; long?: boolean }) {
  const n = tier.slice(-1)
  return <span className={`tier tier-${n}`}>{long ? `${TIER_TEXT[tier].short} — ${TIER_TEXT[tier].long}` : TIER_TEXT[tier].short}</span>
}

export function CategoryIcon({ category, size = 40 }: { category: string; size?: number }) {
  const I = { investment: TrendingUp, bank_account: Landmark, insurance: ShieldCheck, kyc: UserCheck }[category] ?? PiggyBank
  return <div className={`cat-icon cat-${category}`} style={{ width: size, height: size }}><I size={size * 0.48} /></div>
}

export function TopBar({ title, sub, onBack, right }: { title: string; sub?: string; onBack?: () => void; right?: ReactNode }) {
  return (
    <div className="topbar">
      {onBack && <button className="icon-btn" onClick={onBack} aria-label="Back"><ArrowLeft size={18} /></button>}
      <div className="grow">
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {right}
    </div>
  )
}

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="backdrop" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div className="sheet" initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 320 }}>
            <div className="sheet-grab" />
            <div className="sheet-head">
              <h2>{title}</h2>
              <button className="icon-btn" style={{ width: 32, height: 32 }} onClick={onClose} aria-label="Close"><X size={16} /></button>
            </div>
            <div className="sheet-body">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

export function CheckRow({ passed, label, detail }: { passed: boolean; label: string; detail?: string }) {
  return (
    <div className="check">
      <span className={`ci ${passed ? 'ok' : 'no'}`}>{passed ? <Check size={11} strokeWidth={3.5} /> : <X size={11} strokeWidth={3.5} />}</span>
      <div className="grow">
        <div className="cl">{label}</div>
        {detail && <div className="cd">{detail}</div>}
      </div>
    </div>
  )
}

export function JsonView({ data }: { data: unknown }) {
  const json = JSON.stringify(data, null, 2) ?? ''
  const html = json
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/("(?:\\.|[^"\\])*")(\s*:)?/g, (_m, s, colon) => colon ? `<span class="k">${s}</span>${colon}` : `<span class="s">${s}</span>`)
    .replace(/\b(-?\d+(?:\.\d+)?)\b(?![^<]*<\/span>)/g, '<span class="n">$1</span>')
  return <div className="json" dangerouslySetInnerHTML={{ __html: html }} />
}

export function Skeleton({ h = 80, mt = 10 }: { h?: number; mt?: number }) {
  return <div className="skeleton" style={{ height: h, marginTop: mt }} />
}

export function BankLogo({ bank, size = 38 }: { bank: string; size?: number }) {
  const m = bankMeta(bank)
  return <div className="bank-logo" style={{ background: m.color, width: size, height: size, fontSize: size * 0.27 }}>{m.short.slice(0, 4)}</div>
}

export function FundLogo({ id, name, size = 38 }: { id: string; name: string; size?: number }) {
  return <div className="fund-logo" style={{ background: fundColor(id), width: size, height: size }}>{name[0]}</div>
}

export function AccountStatus({ status }: { status: string }) {
  if (status === 'VERIFIED') return <span className="pill pill-ok"><span className="pd" />Verified</span>
  if (status === 'UNVERIFIED') return <span className="pill pill-bad"><span className="pd" />Not verified</span>
  return <span className="pill pill-neutral"><span className="pd" />Verifying</span>
}
