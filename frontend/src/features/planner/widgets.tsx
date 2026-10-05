import { AlertTriangle, CalendarClock, ChevronRight, Info, Loader2, ShieldAlert, Wallet } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Sheet } from '../../components/ui'
import { api } from '../../services/api'
import { inr, inrShort } from '../../services/format'
import type { PlannerAttentionCard, PlannerForecast, PlannerGoal, PlannerOverview, PlannerPulse } from '../../services/types'

const shortDate = (iso: string) =>
  new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

/* ─────────────────────────── Safe to Spend ─────────────────────────── */

const PULSE_COPY: Record<PlannerPulse['status'], { tag: string; cls: string }> = {
  HEALTHY: { tag: 'On track', cls: 'ok' },
  TIGHT: { tag: 'Tight month', cls: 'warn' },
  OVERCOMMITTED: { tag: 'Over-committed', cls: 'bad' },
}

export function SafeToSpendCard({ pulse, onOpen }: { pulse: PlannerPulse; onOpen?: () => void }) {
  const copy = PULSE_COPY[pulse.status]
  const parts = [
    { k: 'Due before payday', v: pulse.committed_before_payday, n: pulse.committed_items },
    { k: 'Essentials', v: pulse.essentials_reserved },
    { k: 'Safety buffer', v: pulse.safety_buffer },
  ]
  return (
    <button className="sts-card tap" onClick={onOpen} disabled={!onOpen}>
      <div className="between">
        <span className="sts-eyebrow"><Wallet size={13} /> Safe to spend today</span>
        <span className={`sts-tag ${copy.cls}`}>{copy.tag}</span>
      </div>
      <div className="sts-amount num">
        {inr(pulse.per_day)}<span>/day</span>
      </div>
      <div className="sts-sub">
        {inr(pulse.total_until_payday)} free for the next {pulse.days_to_payday} day{pulse.days_to_payday === 1 ? '' : 's'} · payday {shortDate(pulse.next_payday)}
      </div>
      <div className="sts-split">
        {parts.map(p => (
          <div key={p.k}>
            <div className="k">{p.k}{p.n ? ` (${p.n})` : ''}</div>
            <div className="v num">{inr(p.v)}</div>
          </div>
        ))}
      </div>
      {onOpen && <ChevronRight size={16} className="sts-chev" />}
    </button>
  )
}

/* ─────────────────────────── 30-day forecast chart ─────────────────────────── */

const W = 340
const H = 150
const PAD = { l: 6, r: 6, t: 18, b: 22 }

export function ForecastChart({ forecast }: { forecast: PlannerForecast }) {
  const pts = forecast.points
  const svgRef = useRef<SVGSVGElement>(null)
  const [hover, setHover] = useState<number | null>(null)

  const geo = useMemo(() => {
    const vals = pts.map(p => p.balance)
    const lo = Math.min(0, ...vals)
    const hi = Math.max(...vals, 1)
    const span = hi - lo || 1
    const x = (i: number) => PAD.l + (i / Math.max(1, pts.length - 1)) * (W - PAD.l - PAD.r)
    const y = (v: number) => PAD.t + (1 - (v - lo) / span) * (H - PAD.t - PAD.b)
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.balance).toFixed(1)}`).join(' ')
    const area = `${line} L${x(pts.length - 1).toFixed(1)},${y(lo).toFixed(1)} L${x(0).toFixed(1)},${y(lo).toFixed(1)} Z`
    return { x, y, line, area, zeroY: y(0), lo }
  }, [pts])

  const lowIdx = pts.findIndex(p => p.date === forecast.lowest.date)
  const negative = !!forecast.first_negative_date
  const active = hover ?? null

  function pick(clientX: number) {
    const r = svgRef.current?.getBoundingClientRect()
    if (!r) return
    const rel = ((clientX - r.left) / r.width) * W
    const i = Math.round(((rel - PAD.l) / (W - PAD.l - PAD.r)) * (pts.length - 1))
    setHover(Math.max(0, Math.min(pts.length - 1, i)))
  }

  const ap = active !== null ? pts[active] : null
  const tipLeft = active !== null ? Math.min(Math.max((geo.x(active) / W) * 100, 18), 82) : 0

  return (
    <div className="fc">
      <div className="fc-head">
        <div>
          <div className="fc-k">Lowest point</div>
          <div className={`fc-v num ${forecast.lowest.balance < 0 ? 'neg' : ''}`}>{inr(forecast.lowest.balance)}</div>
          <div className="fc-s">on {shortDate(forecast.lowest.date)}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="fc-k">In {forecast.days} days</div>
          <div className="fc-v num">{inr(forecast.end_balance)}</div>
          <div className="fc-s">from {inr(forecast.start_balance)} today</div>
        </div>
      </div>

      <div className="fc-plot">
        {ap && (
          <div className="fc-tip" style={{ left: `${tipLeft}%` }}>
            <b>{shortDate(ap.date)}</b> · <span className="num">{inr(ap.balance)}</span>
            {ap.events.map((e, i) => (
              <div key={i} className={`fc-ev ${e.amount > 0 ? 'in' : ''}`}>{e.title} {e.amount > 0 ? '+' : '−'}{inrShort(Math.abs(e.amount))}</div>
            ))}
          </div>
        )}
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="fc-svg"
          role="img"
          aria-label={`Projected balance over ${forecast.days} days, lowest ${inr(forecast.lowest.balance)} on ${shortDate(forecast.lowest.date)}`}
          onPointerMove={e => pick(e.clientX)}
          onPointerDown={e => pick(e.clientX)}
          onPointerLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id="fcFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.18" />
              <stop offset="100%" stopColor="var(--brand)" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          {/* zero line: recessive, dashed */}
          <line x1={PAD.l} x2={W - PAD.r} y1={geo.zeroY} y2={geo.zeroY} stroke="var(--ink-4)" strokeDasharray="3 4" strokeWidth="1" />
          {negative && (
            <rect x={PAD.l} y={geo.zeroY} width={W - PAD.l - PAD.r} height={Math.max(0, H - PAD.b - geo.zeroY)} fill="var(--bad-soft)" />
          )}
          <path d={geo.area} fill="url(#fcFill)" />
          <path d={geo.line} fill="none" stroke="var(--brand)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          {/* event ticks along the baseline */}
          {pts.map((p, i) => p.events.length > 0 && (
            <circle key={p.date} cx={geo.x(i)} cy={H - PAD.b + 8} r="2.5"
              fill={p.events.some(e => e.amount > 0) ? 'var(--ok)' : 'var(--ink-3)'} />
          ))}
          {/* lowest point: the one direct label */}
          {lowIdx >= 0 && (
            <g>
              <circle cx={geo.x(lowIdx)} cy={geo.y(pts[lowIdx].balance)} r="5" fill={pts[lowIdx].balance < 0 ? 'var(--bad)' : 'var(--brand)'} stroke="var(--surface)" strokeWidth="2" />
              <text x={geo.x(lowIdx) + (geo.x(lowIdx) > W / 2 ? -9 : 9)} y={geo.y(pts[lowIdx].balance) + 14}
                textAnchor={geo.x(lowIdx) > W / 2 ? 'end' : 'start'} className="fc-label">
                {inrShort(pts[lowIdx].balance)}
              </text>
            </g>
          )}
          {active !== null && (
            <g>
              <line x1={geo.x(active)} x2={geo.x(active)} y1={PAD.t - 6} y2={H - PAD.b} stroke="var(--ink-3)" strokeWidth="1" />
              <circle cx={geo.x(active)} cy={geo.y(pts[active].balance)} r="4.5" fill="var(--brand)" stroke="var(--surface)" strokeWidth="2" />
            </g>
          )}
        </svg>
        <div className="fc-axis">
          <span>Today</span>
          <span>{shortDate(pts[Math.floor(pts.length / 2)].date)}</span>
          <span>{shortDate(pts[pts.length - 1].date)}</span>
        </div>
      </div>
      <div className="fc-legend">
        <span><i className="fc-dot" style={{ background: 'var(--ink-3)' }} /> Scheduled debit</span>
        <span><i className="fc-dot" style={{ background: 'var(--ok)' }} /> Salary credit</span>
        <span className="muted">Tap the chart for details</span>
      </div>
      {negative && (
        <div className="fc-alert"><ShieldAlert size={15} /> Balance runs out on {shortDate(forecast.first_negative_date!)} at your usual spending.</div>
      )}
    </div>
  )
}

/* ─────────────────────────── Needs-attention feed ─────────────────────────── */

const LEVEL_ICON = { critical: AlertTriangle, warning: AlertTriangle, info: Info }

export function AttentionFeed({ cards, onAction }: { cards: PlannerAttentionCard[]; onAction: (c: PlannerAttentionCard) => void }) {
  if (!cards.length) return null
  return (
    <div className="attn-feed">
      {cards.slice(0, 4).map(c => {
        const I = LEVEL_ICON[c.level] ?? Info
        return (
          <button key={c.id} className={`attn-item ${c.level} tap`} onClick={() => onAction(c)}>
            <span className="attn-ic"><I size={16} /></span>
            <span className="grow">
              <span className="t">{c.title}</span>
              <span className="d">{c.detail}</span>
              <span className="a">{c.action_label} <ChevronRight size={12} /></span>
            </span>
          </button>
        )
      })}
    </div>
  )
}

/* ─────────────────────────── Edit income & expenses ─────────────────────────── */

export function ProfileSheet({ open, onClose, profile, onSaved }:
  { open: boolean; onClose: () => void; profile: PlannerOverview['profile']; onSaved: (msg: string) => void }) {
  const [f, setF] = useState({
    monthly_income: String(profile.monthly_income),
    essential_expenses: String(profile.essential_expenses),
    discretionary_expenses: String(profile.discretionary_expenses),
    target_runway_months: String(profile.target_runway_months),
    salary_day: String(profile.salary_day || 1),
  })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF(s => ({ ...s, [k]: e.target.value }))

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await api.plannerUpdateProfile({
        monthly_income: Number(f.monthly_income),
        essential_expenses: Number(f.essential_expenses),
        discretionary_expenses: Number(f.discretionary_expenses),
        target_runway_months: Number(f.target_runway_months),
        salary_day: Number(f.salary_day),
      })
      onSaved('Plan updated with your new numbers')
      onClose()
    } catch (x) {
      setErr((x as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const fields: { k: keyof typeof f; label: string; hint?: string }[] = [
    { k: 'monthly_income', label: 'Monthly take-home income (₹)', hint: profile.income_verified ? `Currently ${profile.income_source.toLowerCase()}` : undefined },
    { k: 'essential_expenses', label: 'Essentials: rent, bills, groceries (₹/mo)' },
    { k: 'discretionary_expenses', label: 'Lifestyle: dining, shopping, OTT (₹/mo)' },
  ]
  return (
    <Sheet open={open} onClose={onClose} title="Income & expenses">
      <form onSubmit={save}>
        {fields.map(x => (
          <label key={x.k} className="field">
            <span className="lbl">{x.label}</span>
            <input className="input num" type="number" min={0} step={500} required value={f[x.k]} onChange={set(x.k)} />
            {x.hint && <span className="hint">{x.hint}</span>}
          </label>
        ))}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <label className="field">
            <span className="lbl">Salary credited on</span>
            <select className="input" value={f.salary_day} onChange={set('salary_day')}>
              {Array.from({ length: 28 }, (_, i) => i + 1).map(d => <option key={d} value={d}>{d}{['st', 'nd', 'rd'][((d + 90) % 100 - 10) % 10 - 1] || 'th'} of month</option>)}
            </select>
          </label>
          <label className="field">
            <span className="lbl">Emergency target</span>
            <select className="input" value={f.target_runway_months} onChange={set('target_runway_months')}>
              {[3, 4, 6, 9, 12].map(m => <option key={m} value={m}>{m} months</option>)}
            </select>
          </label>
        </div>
        {err && <div className="form-err">{err}</div>}
        <button className="btn btn-primary" style={{ width: '100%', marginTop: 18 }} disabled={busy}>
          {busy ? <Loader2 size={16} className="spin" /> : 'Save & recalculate'}
        </button>
      </form>
    </Sheet>
  )
}

/* ─────────────────────────── Goal: add money / change monthly saving ─────────────────────────── */

export function GoalActionSheet({ goal, mode, onClose, onSaved }:
  { goal: PlannerGoal | null; mode: 'add' | 'edit'; onClose: () => void; onSaved: (msg: string) => void }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const open = !!goal

  const amount = Number(value)
  const presets = mode === 'add' ? [1000, 5000, 10000, 25000] : goal ? [goal.monthly_required, goal.monthly_contribution + 2000, goal.monthly_contribution + 5000] : []

  async function save(e: React.FormEvent) {
    e.preventDefault()
    if (!goal || !(amount >= 0)) return
    setBusy(true)
    setErr(null)
    try {
      if (mode === 'add') {
        await api.plannerAddMoney(goal.id, amount)
        onSaved(`${inr(amount)} added to ${goal.name}`)
      } else {
        await api.plannerUpdateGoal(goal.id, { monthly_contribution: amount })
        onSaved(`${goal.name}: saving ${inr(amount)}/mo`)
      }
      setValue('')
      onClose()
    } catch (x) {
      setErr((x as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const months = goal && mode === 'edit' && amount > 0 ? Math.ceil(goal.remaining_amount / amount) : null
  return (
    <Sheet open={open} onClose={() => { setValue(''); onClose() }} title={mode === 'add' ? 'Add money to goal' : 'Monthly saving'}>
      {goal && (
        <form onSubmit={save}>
          <div className="goal-sheet-head">
            <div className="t">{goal.name}</div>
            <div className="s num">{inr(goal.current_amount)} of {inr(goal.target_amount)} · {goal.progress_pct.toFixed(0)}%</div>
          </div>
          <label className="field">
            <span className="lbl">{mode === 'add' ? 'Amount (₹)' : 'Save every month (₹)'}</span>
            <input className="input num amount-input" type="number" min={mode === 'add' ? 1 : 0} step={100} required autoFocus
              value={value} onChange={e => setValue(e.target.value)} placeholder={mode === 'add' ? '5,000' : String(goal.monthly_contribution)} />
          </label>
          <div className="chips-row" style={{ marginTop: 10 }}>
            {presets.filter((p, i, a) => p > 0 && a.indexOf(p) === i).map(p => (
              <button type="button" key={p} className={`chip-btn ${amount === p ? 'on' : ''}`} onClick={() => setValue(String(Math.round(p)))}>
                {mode === 'edit' && p === goal.monthly_required ? `On-track ${inrShort(p)}` : `${mode === 'add' ? '+' : ''}${inrShort(p)}`}
              </button>
            ))}
          </div>
          {months !== null && (
            <div className="saarthi-strip" style={{ marginTop: 12 }}>
              <div className="t">
                <CalendarClock size={13} style={{ verticalAlign: -2 }} /> At {inr(amount)}/mo you reach {inr(goal.target_amount)} in about <b>{months} months</b>
                {amount >= goal.monthly_required ? ' - on time.' : `, ${months - Math.round(goal.months_remaining)} months after your target date.`}
              </div>
            </div>
          )}
          {err && <div className="form-err">{err}</div>}
          <button className="btn btn-primary" style={{ width: '100%', marginTop: 18 }} disabled={busy || !value}>
            {busy ? <Loader2 size={16} className="spin" /> : mode === 'add' ? `Add ${value ? inr(amount) : ''}` : 'Update monthly saving'}
          </button>
        </form>
      )}
    </Sheet>
  )
}
