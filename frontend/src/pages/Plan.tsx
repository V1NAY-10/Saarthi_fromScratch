import {
  AlertTriangle,
  Bot,
  Car,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Compass,
  Flame,
  FlaskConical,
  GraduationCap,
  History,
  Landmark,
  House,
  IndianRupee,
  Layers,
  Link as LinkIcon,
  Loader2,
  Pencil,
  PiggyBank,
  Plane,
  Plus,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
  Trash2,
  TrendingUp,
  Zap
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { HealthRing, Sheet, Skeleton, TopBar } from '../components/ui'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { dueLabel, inr, relDay } from '../services/format'
import { AttentionFeed, ForecastChart, GoalActionSheet, ProfileSheet, SafeToSpendCard } from '../features/planner/widgets'
import type {
  AffordabilityResult,
  PlannerAttentionCard,
  PlannerGoal,
  DebtPayoffResult,
  StressTestResult,
  WhatIfResult
} from '../services/types'

type SubTab = 'overview' | 'goals' | 'simulators' | 'advisor' | 'calendar'
type SimType = 'affordability' | 'whatif' | 'stresstest' | 'debt'

const GOAL_PRESETS = [
  { name: 'Emergency Cushion', category: 'emergency', target_amount: 300000, target_date: '2026-12-31', monthly: 25000 },
  { name: 'Dream Home Down Payment', category: 'home', target_amount: 1500000, target_date: '2029-06-30', monthly: 35000 },
  { name: 'Europe Vacation', category: 'travel', target_amount: 250000, target_date: '2027-05-31', monthly: 15000 },
  { name: 'Child Higher Education', category: 'education', target_amount: 2000000, target_date: '2032-03-31', monthly: 20000 },
  { name: 'Financial Freedom / Retirement', category: 'wealth', target_amount: 10000000, target_date: '2045-12-31', monthly: 30000 },
]

const GOAL_ICONS: Record<string, typeof Target> = {
  emergency: Shield, home: House, house: House, travel: Plane, education: GraduationCap, car: Car, vehicle: Car, wealth: Sparkles,
}

const monthYear = (iso: string) =>
  new Date(iso.slice(0, 10) + 'T00:00:00').toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })

// Real fund ids from the seeded catalogue
const GOAL_FUND_ID = 'f-nimbus-bluechip'
const LIQUID_FUND_ID = 'f-yamuna-debt'

const SCENARIOS = [
  { id: 1, label: '1. Cash-flow collision' },
  { id: 2, label: '2. Car goal behind' },
  { id: 6, label: '3. Active loan EMI' },
  { id: 7, label: '4. Verified salary slip' },
]

function daysUntil(iso: string): number {
  const d = new Date(iso.slice(0, 10) + 'T00:00:00')
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((d.getTime() - today.getTime()) / 86400000)
}

export function Plan() {
  const { push, bump, showToast } = useApp()
  const [subtab, setSubtab] = useState<SubTab>('overview')
  const [simType, setSimType] = useState<SimType>('affordability')

  const { data: plan, reload: reloadPlanOverview } = useData(() => api.plannerOverview())
  const { data: changelog, reload: reloadChangelog } = useData(() => api.plannerChangelog(10))
  const reloadPlan = () => { reloadPlanOverview(); reloadChangelog() }

  // Goal Creation Sheet state
  const [showAddGoal, setShowAddGoal] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [goalSheet, setGoalSheet] = useState<{ goal: PlannerGoal; mode: 'add' | 'edit' } | null>(null)
  const [newGoalName, setNewGoalName] = useState('')
  const [newGoalCategory, setNewGoalCategory] = useState('custom')
  const [newGoalTarget, setNewGoalTarget] = useState('')
  const [newGoalCurrent, setNewGoalCurrent] = useState('')
  const [newGoalDate, setNewGoalDate] = useState('2028-12-31')
  const [newGoalMonthly, setNewGoalMonthly] = useState('')
  const [creatingGoal, setCreatingGoal] = useState(false)

  // Affordability state
  const [affordAmount, setAffordAmount] = useState('75000')
  const [affordRecurring, setAffordRecurring] = useState(false)
  const [affordResult, setAffordResult] = useState<AffordabilityResult | null>(null)
  const [checkingAfford, setCheckingAfford] = useState(false)

  // What-If state
  const [incomeDelta, setIncomeDelta] = useState(0)
  const [sipDelta, setSipDelta] = useState(5000)
  const [expenseDelta, setExpenseDelta] = useState(0)
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult | null>(null)
  const [simulatingWhatIf, setSimulatingWhatIf] = useState(false)

  // Stress Test state
  const [stressScenario, setStressScenario] = useState('INCOME_DROP_20')
  const [stressResult, setStressResult] = useState<StressTestResult | null>(null)
  const [runningStress, setRunningStress] = useState(false)

  // Debt Payoff state
  const [extraPayment, setExtraPayment] = useState(5000)
  const [debtResult, setDebtResult] = useState<DebtPayoffResult | null>(null)
  const [runningDebt, setRunningDebt] = useState(false)

  // AI Chat state
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<{ role: 'user' | 'assistant'; text: string }[]>([
    { role: 'assistant', text: 'Hello! I am your Saarthi Financial Planning Advisor. Ask me anything about your emergency runway, goals, affordability, or investment strategies.' },
  ])
  const [sendingChat, setSendingChat] = useState(false)

  // Scenario loading state
  const [loadingScenario, setLoadingScenario] = useState<number | null>(null)

  // (Re)run the simulators with the current inputs whenever the plan data changes
  useEffect(() => {
    if (!plan) return
    runAffordabilityCheck(affordAmount, affordRecurring, affordRecurring ? 'monthly' : 'one_time', 'general')
    runWhatIfSimulation(incomeDelta, sipDelta, expenseDelta)
    runStressTestSimulation(stressScenario)
    runDebtSimulation(extraPayment)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan])

  async function handleLoadScenario(id: number) {
    setLoadingScenario(id)
    try {
      const res = await api.plannerLoadScenario(id)
      bump()
      reloadPlan()
      showToast(`Loaded: ${res.title}`)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      setLoadingScenario(null)
    }
  }

  function afterSave(msg: string) {
    bump()
    reloadPlan()
    showToast(msg)
  }

  function handleAttention(c: PlannerAttentionCard) {
    if (c.action_type === 'NAVIGATE_TAB') setSubtab(c.action_target as SubTab)
    else if (c.action_type === 'OPEN_JOURNEY') push({ name: 'journey', id: c.action_target })
    else if (c.action_type === 'SIMULATE') push({ name: 'fund', id: LIQUID_FUND_ID })
    else if (c.action_type === 'EDIT_GOAL') {
      const g = plan?.goals.find(x => x.id === c.action_target)
      if (g) setGoalSheet({ goal: g, mode: 'edit' })
    }
  }

  async function handleCreateGoal(e: React.FormEvent) {
    e.preventDefault()
    if (!newGoalName || !newGoalTarget) return
    setCreatingGoal(true)
    try {
      await api.plannerCreateGoal({
        name: newGoalName,
        category: newGoalCategory,
        target_amount: parseFloat(newGoalTarget),
        current_amount: parseFloat(newGoalCurrent || '0'),
        target_date: newGoalDate,
        monthly_contribution: parseFloat(newGoalMonthly || '0'),
      })
      bump()
      reloadPlan()
      setShowAddGoal(false)
      resetGoalForm()
      showToast('Goal created successfully!')
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      setCreatingGoal(false)
    }
  }

  function resetGoalForm() {
    setNewGoalName('')
    setNewGoalCategory('custom')
    setNewGoalTarget('')
    setNewGoalCurrent('')
    setNewGoalMonthly('')
  }

  function pickPreset(preset: typeof GOAL_PRESETS[0]) {
    setNewGoalName(preset.name)
    setNewGoalCategory(preset.category)
    setNewGoalTarget(String(preset.target_amount))
    setNewGoalDate(preset.target_date)
    setNewGoalMonthly(String(preset.monthly))
  }

  async function handleDeleteGoal(goalId: string, name: string) {
    if (!window.confirm(`Delete goal "${name}"?`)) return
    try {
      await api.plannerDeleteGoal(goalId)
      bump()
      reloadPlan()
      showToast('Goal removed')
    } catch (e) {
      showToast((e as Error).message)
    }
  }

  async function runAffordabilityCheck(amountStr: string, isRec: boolean, freq: string, cat: string) {
    const amt = parseFloat(amountStr)
    if (isNaN(amt) || amt <= 0) return
    setCheckingAfford(true)
    try {
      const res = await api.plannerAffordability({
        amount: amt,
        is_recurring: isRec,
        frequency: freq,
        category: cat,
      })
      setAffordResult(res)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      setCheckingAfford(false)
    }
  }

  async function runWhatIfSimulation(incDelta: number, sDelta: number, expDelta: number) {
    setSimulatingWhatIf(true)
    try {
      const res = await api.plannerWhatIf({
        income_delta_pct: incDelta,
        sip_delta_abs: sDelta,
        expense_delta_abs: expDelta,
      })
      setWhatIfResult(res)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      setSimulatingWhatIf(false)
    }
  }

  async function runStressTestSimulation(type: string) {
    setRunningStress(true)
    try {
      const res = await api.plannerStressTest({ stress_type: type })
      setStressResult(res)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      setRunningStress(false)
    }
  }

  async function runDebtSimulation(extra: number) {
    setRunningDebt(true)
    try {
      const res = await api.plannerDebtPayoff({ extra_monthly_payment: extra })
      setDebtResult(res)
    } catch (e) {
      showToast((e as Error).message)
    } finally {
      setRunningDebt(false)
    }
  }

  async function handleSendChat(textToSend?: string) {
    const text = textToSend || chatInput
    if (!text.trim() || sendingChat) return
    const userMsg = text.trim()
    setChatMessages(prev => [...prev, { role: 'user', text: userMsg }])
    if (!textToSend) setChatInput('')
    setSendingChat(true)
    try {
      const res = await api.plannerChat(userMsg)
      setChatMessages(prev => [...prev, { role: 'assistant', text: res.reply }])
    } catch (e) {
      setChatMessages(prev => [...prev, { role: 'assistant', text: `Sorry, I encountered an issue: ${(e as Error).message}` }])
    } finally {
      setSendingChat(false)
    }
  }

  if (!plan) {
    return (
      <div>
        <TopBar title="Financial Plan" sub="Loading command center..." />
        <div className="page">
          <Skeleton h={180} />
          <Skeleton h={120} mt={14} />
          <Skeleton h={200} mt={14} />
        </div>
      </div>
    )
  }

  const ef = plan.emergency_fund
  const cf = plan.cash_flow
  const nw = plan.net_worth
  const score = plan.health_score.overall
  const runwayPct = Math.min(100, Math.round((ef.current_runway_months / Math.max(1, ef.target_runway_months)) * 100))
  const pctOfIncome = (v: number) => (cf.income > 0 ? (v / cf.income) * 100 : 0)
  const collision30 = plan.collisions.windows['30d']
  const obligations30 = plan.obligations.filter(o => daysUntil(o.due) <= 30)

  return (
    <div>
      <TopBar
        title="Money Plan"
        sub={`${plan.profile.income_verified ? 'Verified income' : 'Estimated income'} ${inr(plan.profile.monthly_income)}/mo · payday ${plan.profile.salary_day}${plan.profile.salary_day === 1 ? 'st' : plan.profile.salary_day === 2 ? 'nd' : plan.profile.salary_day === 3 ? 'rd' : 'th'}`}
        right={
          <button className="icon-btn" aria-label="Edit income and expenses" onClick={() => setShowProfile(true)}>
            <Pencil size={16} />
          </button>
        }
      />

      <div className="page page-tight">
        {/* Navigation Tabs */}
        <div className="subtab-nav">
          <button className={`subtab-btn ${subtab === 'overview' ? 'active' : ''}`} onClick={() => setSubtab('overview')}>
            <span className="row" style={{ gap: 5 }}><Layers size={14} /> Overview</span>
          </button>
          <button className={`subtab-btn ${subtab === 'goals' ? 'active' : ''}`} onClick={() => setSubtab('goals')}>
            <span className="row" style={{ gap: 5 }}><Target size={14} /> Goals ({plan.goals.length})</span>
          </button>
          <button className={`subtab-btn ${subtab === 'simulators' ? 'active' : ''}`} onClick={() => setSubtab('simulators')}>
            <span className="row" style={{ gap: 5 }}><Zap size={14} /> Simulators</span>
          </button>
          <button className={`subtab-btn ${subtab === 'advisor' ? 'active' : ''}`} onClick={() => setSubtab('advisor')}>
            <span className="row" style={{ gap: 5 }}><Sparkles size={14} /> AI Advisor</span>
          </button>
          <button className={`subtab-btn ${subtab === 'calendar' ? 'active' : ''}`} onClick={() => setSubtab('calendar')}>
            <span className="row" style={{ gap: 5 }}><Calendar size={14} /> Cash Flow</span>
          </button>
        </div>

        {/* ───────────── OVERVIEW TAB ───────────── */}
        {subtab === 'overview' && (
          <div className="stack" style={{ gap: 14 }}>
            <SafeToSpendCard pulse={plan.pulse} onOpen={() => setSubtab('calendar')} />

            {plan.attention_cards.length > 0 && (
              <div>
                <div className="section-head"><div className="section-title">Needs your attention</div></div>
                <AttentionFeed cards={plan.attention_cards} onAction={handleAttention} />
              </div>
            )}

            {/* Hero Health Card */}
            <div className="planner-hero">
              <div className="between">
                <div>
                  <div className="eyebrow" style={{ color: 'rgba(255,255,255,0.75)' }}>FINANCIAL HEALTH INDEX</div>
                  <div className="amt" style={{ fontSize: 28, fontWeight: 800, marginTop: 2 }}>
                    {plan.health_score.band}
                  </div>
                </div>
                <HealthRing score={score} size={68} stroke={6.5} label="INDEX" />
              </div>

              <div className="planner-score-row">
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, opacity: 0.8 }}>Survival Runway</div>
                  <div style={{ fontWeight: 800, fontSize: 16 }}>{ef.current_runway_months.toFixed(1)} mo</div>
                  <div style={{ fontSize: 10, opacity: 0.7 }}>Target {ef.target_runway_months} mo</div>
                </div>
                <div style={{ width: 1, height: 32, background: 'rgba(255,255,255,0.2)' }} />
                <div style={{ flex: 1, paddingLeft: 6 }}>
                  <div style={{ fontSize: 11, opacity: 0.8 }}>Savings Rate</div>
                  <div style={{ fontWeight: 800, fontSize: 16 }}>{cf.savings_rate_pct.toFixed(0)}%</div>
                  <div style={{ fontSize: 10, opacity: 0.7 }}>Surplus {inr(cf.estimated_surplus)}</div>
                </div>
                <div style={{ width: 1, height: 32, background: 'rgba(255,255,255,0.2)' }} />
                <div style={{ flex: 1, paddingLeft: 6 }}>
                  <div style={{ fontSize: 11, opacity: 0.8 }}>Net Worth</div>
                  <div style={{ fontWeight: 800, fontSize: 16 }}>{inr(nw.net_worth)}</div>
                  <div style={{ fontSize: 10, opacity: 0.7 }}>Assets {inr(nw.total_assets)}</div>
                </div>
              </div>
            </div>

            {/* Health Factors Pill Breakdown */}
            <div className="card card-pad">
              <div className="between">
                <div className="card-title">Score Drivers</div>
                <span className="muted" style={{ fontSize: 11 }}>Real-time evaluation</span>
              </div>
              <div className="planner-factors">
                {plan.health_score.factors.map(f => (
                  <div key={f.key} className="planner-factor-item">
                    <div className="between">
                      <span style={{ fontWeight: 600 }}>{f.name}</span>
                      <span className={`pill ${f.status === 'EXCELLENT' ? 'pill-ok' : f.status === 'GOOD' ? 'pill-info' : f.status === 'NEEDS_WORK' ? 'pill-warn' : 'pill-bad'}`} style={{ height: 18, fontSize: 9.5 }}>
                        {f.score}/{f.max_score}
                      </span>
                    </div>
                    <div className="muted" style={{ fontSize: 10.5, marginTop: 4, lineHeight: 1.3 }}>
                      {f.comment}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Emergency Runway Buffer */}
            <div className="card card-pad">
              <div className="between">
                <div className="row">
                  <Shield size={18} style={{ color: 'var(--brand)' }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>Emergency Cushion</div>
                    <div className="muted" style={{ fontSize: 11.5 }}>
                      {ef.status === 'ADEQUATE' ? 'Well defended against shocks' : `Shortfall of ${inr(ef.gap)}`}
                    </div>
                  </div>
                </div>
                <span className={`pill ${ef.status === 'ADEQUATE' ? 'pill-ok' : 'pill-warn'}`}>
                  {ef.status_label}
                </span>
              </div>

              <div className="meter-container" style={{ height: 10, marginTop: 12 }}>
                <div
                  className={`meter-fill ${ef.status === 'ADEQUATE' ? 'green' : 'amber'}`}
                  style={{ width: `${runwayPct}%` }}
                />
              </div>

              <div className="between" style={{ marginTop: 8, fontSize: 12 }}>
                <div>
                  <span className="muted">Liquid cash: </span>
                  <b>{inr(ef.current_liquid)}</b>
                </div>
                <div>
                  <span className="muted">Required ({ef.target_runway_months} mo): </span>
                  <b>{inr(ef.recommended_corpus)}</b>
                </div>
              </div>

              {ef.gap > 0 && (
                <div className="saarthi-strip" style={{ marginTop: 12 }}>
                  <div className="t">
                    <b>Saarthi Insight:</b> Allocating {inr(ef.gap / 6)}/mo to liquid funds fills this safety gap in 6 months.
                  </div>
                </div>
              )}
            </div>

            {/* 50-30-20 Cash Flow & Budget */}
            <div className="card card-pad">
              <div className="between">
                <div>
                  <div className="card-title">Monthly Cash Flow</div>
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    Total Inflow: {inr(cf.income)} ·{' '}
                    <button style={{ color: 'var(--brand)', fontWeight: 600, fontSize: 11.5 }} onClick={() => setShowProfile(true)}>Edit</button>
                  </div>
                </div>
                <span className={`pill ${plan.auto_budget.compliant ? 'pill-ok' : 'pill-warn'}`}>
                  {plan.auto_budget.compliant ? '50-30-20 Compliant' : 'Overspending Risk'}
                </span>
              </div>

              {/* Segmented Bar for 50-30-20 */}
              <div style={{ marginTop: 14 }}>
                <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', gap: 2 }}>
                  <div
                    style={{ width: `${plan.auto_budget.needs_pct}%`, background: '#3b82f6', borderRadius: 4 }}
                    title={`Needs: ${plan.auto_budget.needs_pct.toFixed(0)}%`}
                  />
                  <div
                    style={{ width: `${plan.auto_budget.wants_pct}%`, background: '#f59e0b', borderRadius: 4 }}
                    title={`Wants: ${plan.auto_budget.wants_pct.toFixed(0)}%`}
                  />
                  <div
                    style={{ width: `${plan.auto_budget.savings_pct}%`, background: '#10b981', borderRadius: 4 }}
                    title={`Savings: ${plan.auto_budget.savings_pct.toFixed(0)}%`}
                  />
                </div>
                <div className="between" style={{ marginTop: 6, fontSize: 11 }}>
                  <span style={{ color: '#2563eb', fontWeight: 600 }}>Needs {plan.auto_budget.needs_pct.toFixed(0)}% (rec. 50%)</span>
                  <span style={{ color: '#d97706', fontWeight: 600 }}>Wants {plan.auto_budget.wants_pct.toFixed(0)}% (rec. 30%)</span>
                  <span style={{ color: '#059669', fontWeight: 600 }}>Savings {plan.auto_budget.savings_pct.toFixed(0)}% (rec. 20%)</span>
                </div>
              </div>

              <div className="facts" style={{ marginTop: 14 }}>
                <div className="fact">
                  <div className="k">Fixed + EMI</div>
                  <div className="v">{inr(cf.essential_expenses + cf.emis)}</div>
                  <div className="src">{pctOfIncome(cf.essential_expenses + cf.emis).toFixed(0)}% of income</div>
                </div>
                <div className="fact">
                  <div className="k">SIPs / Invested</div>
                  <div className="v">{inr(cf.sips)}</div>
                  <div className="src">{cf.sips > 0 ? `${pctOfIncome(cf.sips).toFixed(0)}% invested` : 'None active'}</div>
                </div>
                <div className="fact emph" style={{ background: cf.free_cash_flow >= 0 ? 'var(--ok-soft)' : 'var(--bad-soft)', borderColor: cf.free_cash_flow >= 0 ? '#bbf7d0' : '#fecaca' }}>
                  <div className="k" style={{ color: cf.free_cash_flow >= 0 ? 'var(--ok)' : 'var(--bad)' }}>Free Cash Flow</div>
                  <div className="v" style={{ color: cf.free_cash_flow >= 0 ? 'var(--ok)' : 'var(--bad)' }}>{inr(cf.free_cash_flow)}</div>
                  <div className="src">Unallocated</div>
                </div>
              </div>
            </div>

            {/* Net Worth Split */}
            <div className="card card-pad">
              <div className="between">
                <div>
                  <div className="card-title">Balance Sheet</div>
                  <div className="muted" style={{ fontSize: 11.5 }}>Assets vs Liabilities</div>
                </div>
                <span className="pill pill-info">{inr(nw.net_worth)} Net</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
                <div style={{ background: 'var(--surface-2)', padding: 10, borderRadius: 12, border: '1px solid var(--line-2)' }}>
                  <div className="between">
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--ok)' }}>ASSETS</span>
                    <span style={{ fontWeight: 800, fontSize: 13 }}>{inr(nw.total_assets)}</span>
                  </div>
                  <div className="stack" style={{ gap: 4, marginTop: 6, fontSize: 11 }}>
                    <div className="between"><span className="muted">Liquid cash</span><span>{inr(nw.asset_breakdown.liquid_cash)}</span></div>
                    <div className="between"><span className="muted">Investments</span><span>{inr(nw.asset_breakdown.investments)}</span></div>
                    <div className="between"><span className="muted">Other assets</span><span>{inr(nw.asset_breakdown.other_assets)}</span></div>
                  </div>
                </div>

                <div style={{ background: 'var(--surface-2)', padding: 10, borderRadius: 12, border: '1px solid var(--line-2)' }}>
                  <div className="between">
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--bad)' }}>DEBT</span>
                    <span style={{ fontWeight: 800, fontSize: 13 }}>{inr(nw.total_liabilities)}</span>
                  </div>
                  <div className="stack" style={{ gap: 4, marginTop: 6, fontSize: 11 }}>
                    <div className="between"><span className="muted">Loans</span><span>{inr(nw.liability_breakdown.loans)}</span></div>
                    <div className="between"><span className="muted">Credit cards</span><span>{inr(nw.liability_breakdown.credit_cards)}</span></div>
                    <div className="between"><span className="muted">Other liabilities</span><span>{inr(nw.liability_breakdown.other_liabilities)}</span></div>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Demo Scenario Switcher */}
            <div className="sandbox">
              <div className="between">
                <div className="sandbox-tag"><FlaskConical size={12} /> Test Demo Profiles</div>
                {loadingScenario && <Loader2 size={14} className="spin" />}
              </div>
              <div className="hint">Simulate different financial profiles instantly to observe engine recalculations:</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, marginTop: 8 }}>
                {SCENARIOS.map(s => (
                  <button
                    key={s.id}
                    className="btn btn-ghost"
                    style={{ height: 32, fontSize: 11 }}
                    disabled={loadingScenario !== null}
                    onClick={() => handleLoadScenario(s.id)}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ───────────── GOALS TAB ───────────── */}
        {subtab === 'goals' && (
          <div className="stack" style={{ gap: 14 }}>
            <div className="between">
              <div>
                <div className="section-title">Your Goals</div>
                <div className="muted" style={{ fontSize: 11.5 }}>
                  {plan.goals.length} target{plan.goals.length === 1 ? '' : 's'} linked to live assets
                </div>
              </div>
              <button className="btn btn-primary" style={{ height: 34, fontSize: 12 }} onClick={() => setShowAddGoal(true)}>
                <Plus size={15} /> Add Goal
              </button>
            </div>

            {plan.goals.length === 0 ? (
              <div className="card card-pad" style={{ textAlign: 'center', padding: '36px 20px' }}>
                <Target size={36} className="muted" style={{ margin: '0 auto 10px' }} />
                <div style={{ fontWeight: 700 }}>No goals defined yet</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                  Add a target like Home Down Payment, Vacation, or Emergency Fund.
                </div>
                <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => setShowAddGoal(true)}>
                  Create Your First Goal
                </button>
              </div>
            ) : (
              plan.goals.map(g => {
                const prog = Math.min(100, g.progress_pct)
                const GoalIcon = GOAL_ICONS[g.category] ?? Target
                return (
                  <div key={g.id} className="goal-card">
                    <div className="goal-header">
                      <div className="row">
                        <div className="goal-icon">
                          <GoalIcon size={18} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: 14 }}>{g.name}</div>
                          <div className="muted" style={{ fontSize: 11.5 }}>
                            By {monthYear(g.target_date)} · {Math.max(0, Math.round(g.months_remaining))} months left
                          </div>
                        </div>
                      </div>
                      <button
                        className="icon-btn"
                        style={{ width: 28, height: 28, boxShadow: 'none' }}
                        onClick={() => handleDeleteGoal(g.id, g.name)}
                        aria-label="Delete goal"
                      >
                        <Trash2 size={14} className="muted" />
                      </button>
                    </div>

                    <div className="meter-container" style={{ height: 8, marginTop: 12 }}>
                      <div
                        className={`meter-fill ${g.on_track ? 'green' : 'amber'}`}
                        style={{ width: `${prog}%` }}
                      />
                    </div>

                    <div className="between" style={{ marginTop: 8, fontSize: 12 }}>
                      <div>
                        <span className="muted">Saved: </span>
                        <b>{inr(g.current_amount)}</b>
                        <span className="muted" style={{ fontSize: 10.5 }}> ({prog.toFixed(0)}%)</span>
                      </div>
                      <div>
                        <span className="muted">Target: </span>
                        <b>{inr(g.target_amount)}</b>
                      </div>
                    </div>

                    <div className="between" style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed var(--line-2)', fontSize: 11.5 }}>
                      <div>
                        <span className="muted">Current Contribution: </span>
                        <b>{inr(g.monthly_contribution)}/mo</b>
                      </div>
                      <span className={`pill ${g.on_track ? 'pill-ok' : 'pill-warn'}`} style={{ height: 20 }}>
                        {g.on_track ? 'On Track' : `Need ${inr(g.monthly_required)}/mo`}
                      </span>
                    </div>

                    {g.linked_investments && g.linked_investments.length > 0 && (
                      <div className="row" style={{ marginTop: 6, flexWrap: 'wrap' }}>
                        {g.linked_investments.map((link, idx) => (
                          <span key={idx} className="goal-linked-tag">
                            <LinkIcon size={10} /> Linked SIP: {inr(link.allocated_amount)}/mo
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="goal-actions">
                      <button className="btn btn-soft" onClick={() => setGoalSheet({ goal: g, mode: 'add' })}>
                        <PiggyBank size={14} /> Add money
                      </button>
                      <button className="btn btn-ghost" onClick={() => setGoalSheet({ goal: g, mode: 'edit' })}>
                        <Pencil size={13} /> Monthly saving
                      </button>
                    </div>
                  </div>
                )
              })
            )}

            {/* Quick Action Button to Invest */}
            <div className="card card-pad" style={{ background: 'linear-gradient(135deg, #f0f7ff, #e5f2ff)', borderColor: '#bfdbfe' }}>
              <div className="between">
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--brand-ink)' }}>Accelerate your goal funding</div>
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>Explore top-rated mutual funds to match your goal horizon</div>
                </div>
                <button className="btn btn-primary" style={{ height: 32, fontSize: 11.5 }} onClick={() => push({ name: 'fund', id: GOAL_FUND_ID })}>
                  Explore Funds
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ───────────── SIMULATORS TAB ───────────── */}
        {subtab === 'simulators' && (
          <div className="stack" style={{ gap: 14 }}>
            {/* Simulator Switcher Segment */}
            <div className="seg">
              <button className={simType === 'affordability' ? 'active' : ''} onClick={() => setSimType('affordability')}>
                {simType === 'affordability' && <span className="seg-bg" />}
                Affordability
              </button>
              <button className={simType === 'whatif' ? 'active' : ''} onClick={() => setSimType('whatif')}>
                {simType === 'whatif' && <span className="seg-bg" />}
                What-If Lab
              </button>
              <button className={simType === 'stresstest' ? 'active' : ''} onClick={() => setSimType('stresstest')}>
                {simType === 'stresstest' && <span className="seg-bg" />}
                Stress Test
              </button>
              <button className={simType === 'debt' ? 'active' : ''} onClick={() => setSimType('debt')}>
                {simType === 'debt' && <span className="seg-bg" />}
                Debt Payoff
              </button>
            </div>

            {/* 1. Affordability Engine */}
            {simType === 'affordability' && (
              <div className="sim-box">
                <div className="row">
                  <IndianRupee size={18} style={{ color: 'var(--brand)' }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>Can I Afford It?</div>
                    <div className="muted" style={{ fontSize: 11.5 }}>Test major purchases against your liquid runway & goals</div>
                  </div>
                </div>

                <div className="field">
                  <label className="lbl">Purchase Amount (₹)</label>
                  <input
                    className="input"
                    type="number"
                    value={affordAmount}
                    onChange={e => setAffordAmount(e.target.value)}
                    placeholder="e.g. 75000"
                  />
                </div>

                <div className="row" style={{ marginTop: 10, gap: 12 }}>
                  <label className="row" style={{ gap: 6, fontSize: 12, cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="recur"
                      checked={!affordRecurring}
                      onChange={() => setAffordRecurring(false)}
                    />
                    One-Time Purchase
                  </label>
                  <label className="row" style={{ gap: 6, fontSize: 12, cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="recur"
                      checked={affordRecurring}
                      onChange={() => setAffordRecurring(true)}
                    />
                    Monthly Recurring
                  </label>
                </div>

                <div className="chips-row" style={{ marginTop: 10 }}>
                  {[
                    { label: 'Laptop (₹75k)', amt: '75000', rec: false },
                    { label: 'iPhone (₹1.2L)', amt: '120000', rec: false },
                    { label: 'Car EMI (₹18k/mo)', amt: '18000', rec: true },
                    { label: 'Luxury Trip (₹2.5L)', amt: '250000', rec: false },
                  ].map(p => (
                    <button
                      key={p.label}
                      className="chip-btn"
                      onClick={() => {
                        setAffordAmount(p.amt)
                        setAffordRecurring(p.rec)
                        runAffordabilityCheck(p.amt, p.rec, p.rec ? 'monthly' : 'one_time', 'electronics')
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                <button
                  className="btn btn-primary"
                  style={{ width: '100%', marginTop: 14 }}
                  disabled={checkingAfford}
                  onClick={() => runAffordabilityCheck(affordAmount, affordRecurring, affordRecurring ? 'monthly' : 'one_time', 'general')}
                >
                  {checkingAfford ? <Loader2 size={16} className="spin" /> : 'Evaluate Affordability'}
                </button>

                {affordResult && (
                  <div
                    className={`verdict-card ${
                      affordResult.verdict_tone === 'SAFE'
                        ? 'verdict-safe'
                        : affordResult.verdict_tone === 'CAUTION'
                        ? 'verdict-caution'
                        : 'verdict-danger'
                    }`}
                  >
                    <div className="between">
                      <div className="row" style={{ gap: 6 }}>
                        {affordResult.verdict_tone === 'SAFE' ? (
                          <CheckCircle2 size={18} />
                        ) : (
                          <AlertTriangle size={18} />
                        )}
                        <b style={{ fontSize: 14 }}>{affordResult.verdict_label}</b>
                      </div>
                      <span className="pill" style={{ background: 'rgba(0,0,0,0.06)', fontSize: 10 }}>
                        {affordResult.verdict_tone}
                      </span>
                    </div>

                    <div style={{ marginTop: 8, fontSize: 12 }}>
                      Runway impact: <b>{affordResult.impact_on_runway.runway_before_months.toFixed(1)} mo</b> →{' '}
                      <b>{affordResult.impact_on_runway.runway_after_months.toFixed(1)} mo</b>
                    </div>

                    {affordResult.impact_on_goals.affected_goals.length > 0 && (
                      <div style={{ marginTop: 6, fontSize: 11.5 }}>
                        ⚠️ Affects goal: {affordResult.impact_on_goals.affected_goals.map(g => `${g.goal_name} (+${g.delay_months} mo delay)`).join(', ')}
                      </div>
                    )}

                    {affordResult.recommendations.length > 0 && (
                      <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed rgba(0,0,0,0.1)', fontSize: 11.5 }}>
                        <b>Saarthi Advice:</b> {affordResult.recommendations.join(' ')}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 2. What-If Scenario Lab */}
            {simType === 'whatif' && (
              <div className="sim-box">
                <div className="row">
                  <Compass size={18} style={{ color: 'var(--brand)' }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>What-If Simulation Lab</div>
                    <div className="muted" style={{ fontSize: 11.5 }}>Move sliders to test potential changes to salary, SIPs, or expenses</div>
                  </div>
                </div>

                <div className="slider-group">
                  <div className="slider-label">
                    <span>Income Adjustment</span>
                    <b>{incomeDelta >= 0 ? `+${incomeDelta}%` : `${incomeDelta}%`}</b>
                  </div>
                  <input
                    type="range"
                    min="-30"
                    max="50"
                    step="5"
                    className="sim-range"
                    value={incomeDelta}
                    onChange={e => {
                      const v = parseInt(e.target.value)
                      setIncomeDelta(v)
                      runWhatIfSimulation(v, sipDelta, expenseDelta)
                    }}
                  />
                </div>

                <div className="slider-group">
                  <div className="slider-label">
                    <span>Monthly SIP Change</span>
                    <b>{sipDelta >= 0 ? `+${inr(sipDelta)}/mo` : `${inr(sipDelta)}/mo`}</b>
                  </div>
                  <input
                    type="range"
                    min="-10000"
                    max="30000"
                    step="2500"
                    className="sim-range"
                    value={sipDelta}
                    onChange={e => {
                      const v = parseInt(e.target.value)
                      setSipDelta(v)
                      runWhatIfSimulation(incomeDelta, v, expenseDelta)
                    }}
                  />
                </div>

                <div className="slider-group">
                  <div className="slider-label">
                    <span>Monthly Expense Change</span>
                    <b>{expenseDelta >= 0 ? `+${inr(expenseDelta)}/mo` : `${inr(expenseDelta)}/mo`}</b>
                  </div>
                  <input
                    type="range"
                    min="-15000"
                    max="20000"
                    step="2500"
                    className="sim-range"
                    value={expenseDelta}
                    onChange={e => {
                      const v = parseInt(e.target.value)
                      setExpenseDelta(v)
                      runWhatIfSimulation(incomeDelta, sipDelta, v)
                    }}
                  />
                </div>

                {whatIfResult && (
                  <div className="card card-pad" style={{ marginTop: 14, background: 'var(--surface-2)' }}>
                    <div className="between">
                      <span className="eyebrow">Simulated Outcome</span>
                      {simulatingWhatIf && <Loader2 size={12} className="spin" />}
                    </div>

                    <div className="facts" style={{ marginTop: 8 }}>
                      <div className="fact">
                        <div className="k">New Surplus</div>
                        <div className="v">{inr(whatIfResult.simulated.surplus)}</div>
                        <div className="src">{whatIfResult.delta.surplus_change >= 0 ? `+${inr(whatIfResult.delta.surplus_change)}` : inr(whatIfResult.delta.surplus_change)}</div>
                      </div>
                      <div className="fact">
                        <div className="k">Runway</div>
                        <div className="v">{whatIfResult.simulated.runway_months.toFixed(1)} mo</div>
                        <div className="src">{whatIfResult.delta.runway_change >= 0 ? `+${whatIfResult.delta.runway_change.toFixed(1)} mo` : `${whatIfResult.delta.runway_change.toFixed(1)} mo`}</div>
                      </div>
                      <div className="fact">
                        <div className="k">Savings Rate</div>
                        <div className="v">{whatIfResult.simulated.savings_rate_pct.toFixed(0)}%</div>
                        <div className="src">{whatIfResult.delta.savings_rate_change >= 0 ? `+${whatIfResult.delta.savings_rate_change.toFixed(0)}%` : `${whatIfResult.delta.savings_rate_change.toFixed(0)}%`}</div>
                      </div>
                    </div>

                    {whatIfResult.goal_impacts.length > 0 && (
                      <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed var(--line)' }}>
                        <div style={{ fontWeight: 600, fontSize: 12 }}>Goal Timelines Impact:</div>
                        <div className="stack" style={{ gap: 4, marginTop: 4 }}>
                          {whatIfResult.goal_impacts.map(gi => (
                            <div key={gi.goal_id} className="between" style={{ fontSize: 11.5 }}>
                              <span>{gi.goal_name}</span>
                              <span className={`pill ${gi.status === 'ACCELERATED' ? 'pill-ok' : gi.status === 'DELAYED' ? 'pill-bad' : 'pill-neutral'}`} style={{ height: 18, fontSize: 10 }}>
                                {gi.status === 'ACCELERATED' ? `Reached ${gi.delta_months} mo earlier` : gi.status === 'DELAYED' ? `Delayed by ${Math.abs(gi.delta_months)} mo` : 'Unchanged'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 3. Stress Testing Engine */}
            {simType === 'stresstest' && (
              <div className="sim-box">
                <div className="row">
                  <ShieldAlert size={18} style={{ color: 'var(--bad)' }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>Crisis Stress-Test</div>
                    <div className="muted" style={{ fontSize: 11.5 }}>Test how your plan withstands emergency shocks & market crises</div>
                  </div>
                </div>

                <div className="chips-row" style={{ marginTop: 12 }}>
                  {[
                    { id: 'INCOME_DROP_20', label: '20% Salary Cut' },
                    { id: 'INCOME_ZERO', label: 'Complete Job Loss' },
                    { id: 'UNEXPECTED_EXPENSE_1L', label: '₹1L Medical Emergency' },
                    { id: 'EMI_HIKE_15', label: 'Interest / EMI Hike 15%' },
                  ].map(s => (
                    <button
                      key={s.id}
                      className={`chip-btn ${stressScenario === s.id ? 'on' : ''}`}
                      onClick={() => {
                        setStressScenario(s.id)
                        runStressTestSimulation(s.id)
                      }}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>

                {stressResult && (
                  <div className="card card-pad" style={{ marginTop: 14 }}>
                    <div className="between">
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 14 }}>{stressResult.stress_name}</div>
                        <div className="muted" style={{ fontSize: 11.5 }}>Survival Runway: {stressResult.survival_runway_months.toFixed(1)} Months</div>
                      </div>
                      <div className="row" style={{ gap: 6 }}>
                        {runningStress && <Loader2 size={13} className="spin" />}
                        <span className={`pill ${stressResult.risk_level === 'LOW' ? 'pill-ok' : stressResult.risk_level === 'MODERATE' ? 'pill-warn' : 'pill-bad'}`}>
                          {stressResult.risk_level} RISK
                        </span>
                      </div>
                    </div>

                    <div className="facts" style={{ marginTop: 10 }}>
                      <div className="fact">
                        <div className="k">Test Income</div>
                        <div className="v">{inr(stressResult.test_income)}</div>
                      </div>
                      <div className="fact">
                        <div className="k">Surplus / Deficit</div>
                        <div className="v" style={{ color: stressResult.surplus_deficit < 0 ? 'var(--bad)' : 'var(--ok)' }}>
                          {inr(stressResult.surplus_deficit)}
                        </div>
                      </div>
                      <div className="fact">
                        <div className="k">Survival Runway</div>
                        <div className="v">{stressResult.survival_runway_months.toFixed(1)} mo</div>
                      </div>
                    </div>

                    <div style={{ marginTop: 14 }}>
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>
                        Automated AI Recovery Playbook:
                      </div>
                      <div className="stack" style={{ gap: 6 }}>
                        {stressResult.recovery_playbook.map(p => (
                          <div key={p.step} className="playbook-step">
                            <span className="playbook-num">{p.step}</span>
                            <div className="grow">
                              <div style={{ fontWeight: 600 }}>{p.action}</div>
                              <div className="muted" style={{ fontSize: 11 }}>
                                {p.savings_potential > 0 && <>Saves ~{inr(p.savings_potential)}/mo · </>}Priority: {p.priority}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 4. Debt Payoff Simulator */}
            {simType === 'debt' && (
              <div className="sim-box">
                <div className="row">
                  <Flame size={18} style={{ color: 'var(--brand)' }} />
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>Debt Prepayment Accelerator</div>
                    <div className="muted" style={{ fontSize: 11.5 }}>See how an extra ₹5,000/mo collapses loan tenure & interest</div>
                  </div>
                </div>

                <div className="slider-group">
                  <div className="slider-label">
                    <span>Extra Monthly Prepayment</span>
                    <b>+{inr(extraPayment)}/mo</b>
                  </div>
                  <input
                    type="range"
                    min="1000"
                    max="20000"
                    step="1000"
                    className="sim-range"
                    value={extraPayment}
                    onChange={e => {
                      const v = parseInt(e.target.value)
                      setExtraPayment(v)
                      runDebtSimulation(v)
                    }}
                  />
                </div>

                {debtResult && (
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 10 }}>
                    {debtResult.is_illustrative
                      ? `You have no active loans - showing a sample ${inr(debtResult.outstanding_balance)} loan at ${inr(debtResult.current_emi)}/mo EMI.`
                      : `${debtResult.liability_name}: ${inr(debtResult.outstanding_balance)} outstanding at ${inr(debtResult.current_emi)}/mo EMI.`}
                  </div>
                )}

                {debtResult && !debtResult.amortizes && (
                  <div className="saarthi-strip" style={{ marginTop: 10 }}>
                    <div className="t">The current EMI doesn't cover the monthly interest, so this loan never pays down. Talk to your lender about restructuring.</div>
                  </div>
                )}

                {debtResult && debtResult.amortizes && (
                  <div className="card card-pad" style={{ marginTop: 14, background: 'var(--surface-2)' }}>
                    <div className="between">
                      <span className="eyebrow">Debt Free Sooner</span>
                      <div className="row" style={{ gap: 6 }}>
                        {runningDebt && <Loader2 size={13} className="spin" />}
                        <span className="pill pill-ok">Save {inr(debtResult.savings.interest_saved)}</span>
                      </div>
                    </div>

                    <div className="facts" style={{ marginTop: 8 }}>
                      <div className="fact">
                        <div className="k">Time Saved</div>
                        <div className="v" style={{ color: 'var(--ok)' }}>{debtResult.savings.time_saved_months} mo</div>
                        <div className="src">({debtResult.savings.time_saved_years.toFixed(1)} years sooner)</div>
                      </div>
                      <div className="fact">
                        <div className="k">Interest Saved</div>
                        <div className="v" style={{ color: 'var(--ok)' }}>{inr(debtResult.savings.interest_saved)}</div>
                        <div className="src">Direct savings</div>
                      </div>
                      <div className="fact">
                        <div className="k">New Payoff</div>
                        <div className="v">{debtResult.with_extra.payoff_months} mo</div>
                        <div className="src">vs {debtResult.baseline.payoff_months} mo normal</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ───────────── ADVISOR TAB ───────────── */}
        {subtab === 'advisor' && (
          <div className="stack" style={{ gap: 14 }}>
            {/* Proactive Recommendations */}
            <div>
              <div className="section-head">
                <div className="section-title">Saarthi AI Recommendations</div>
                <span className="muted" style={{ fontSize: 11 }}>Prioritized actions</span>
              </div>
              <div className="stack" style={{ gap: 8 }}>
                {plan.recommendations.map(r => (
                  <div key={r.id} className={`rec-card ${r.urgency.toLowerCase()}`}>
                    <div className="between">
                      <span className="eyebrow" style={{ fontSize: 10 }}>{r.category}</span>
                      <span className={`pill ${r.urgency === 'HIGH' ? 'pill-bad' : r.urgency === 'MEDIUM' ? 'pill-warn' : 'pill-ok'}`} style={{ height: 18, fontSize: 9.5 }}>
                        {r.urgency} PRIORITY
                      </span>
                    </div>
                    <div style={{ fontWeight: 700, fontSize: 13.5, marginTop: 4 }}>{r.title}</div>
                    <div className="muted" style={{ fontSize: 12, marginTop: 3, lineHeight: 1.4 }}>{r.description}</div>
                    <div className="between" style={{ marginTop: 8, paddingTop: 6, borderTop: '1px dashed var(--line-2)' }}>
                      <span style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--brand)' }}>{r.impact_summary}</span>
                      <button
                        className="btn btn-soft"
                        style={{ height: 26, fontSize: 11, padding: '0 8px' }}
                        onClick={() => {
                          if (r.actionable_journey === 'invest') push({ name: 'fund', id: r.id === 'rec-runway' ? LIQUID_FUND_ID : GOAL_FUND_ID })
                          else if (r.actionable_journey === 'loan') { setSubtab('simulators'); setSimType('debt') }
                          else showToast(`Action initiated: ${r.suggested_action}`)
                        }}
                      >
                        Act Now <ChevronRight size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Interactive Ask Saarthi AI Drawer */}
            <div className="card card-pad">
              <div className="row" style={{ gap: 8 }}>
                <Bot size={18} style={{ color: 'var(--brand)' }} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>Ask Saarthi Planner</div>
                  <div className="muted" style={{ fontSize: 11.5 }}>Deep financial reasoning backed by deterministic models</div>
                </div>
              </div>

              {/* Sample Prompts */}
              <div className="chips-row" style={{ marginTop: 10 }}>
                {[
                  'How to retire by 45?',
                  'Can I afford a ₹1.5L vacation?',
                  'Should I pay off personal loan or invest in SIPs?',
                  'How to boost my health score to 90?',
                ].map(p => (
                  <button key={p} className="chip-btn" onClick={() => handleSendChat(p)}>
                    {p}
                  </button>
                ))}
              </div>

              {/* Chat Thread */}
              <div
                style={{
                  maxHeight: 220,
                  overflowY: 'auto',
                  marginTop: 12,
                  padding: '8px 10px',
                  background: 'var(--surface-2)',
                  borderRadius: 12,
                  border: '1px solid var(--line-2)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                {chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    style={{
                      alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      background: msg.role === 'user' ? 'var(--brand)' : '#ffffff',
                      color: msg.role === 'user' ? '#ffffff' : 'var(--ink)',
                      padding: '8px 12px',
                      borderRadius: 12,
                      maxWidth: '85%',
                      fontSize: 12,
                      lineHeight: 1.45,
                      boxShadow: 'var(--sh-1)',
                    }}
                  >
                    {msg.text}
                  </div>
                ))}
                {sendingChat && (
                  <div style={{ alignSelf: 'flex-start', background: '#ffffff', padding: '6px 10px', borderRadius: 10, fontSize: 11 }}>
                    <Loader2 size={12} className="spin" style={{ display: 'inline', marginRight: 4 }} /> Saarthi is evaluating your finances...
                  </div>
                )}
              </div>

              {/* Chat Input */}
              <div className="row" style={{ marginTop: 10, gap: 6 }}>
                <input
                  className="input"
                  style={{ height: 38, fontSize: 13 }}
                  placeholder="Ask a question about your plan..."
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleSendChat()}
                />
                <button
                  className="btn btn-primary"
                  style={{ width: 38, height: 38, padding: 0 }}
                  disabled={sendingChat || !chatInput.trim()}
                  onClick={() => handleSendChat()}
                >
                  <Send size={15} />
                </button>
              </div>
            </div>

            {/* Plan Changelog / Audit Trail */}
            {changelog && changelog.length > 0 && (
              <div className="card card-pad">
                <div className="between">
                  <div className="row" style={{ gap: 6 }}>
                    <History size={15} className="muted" />
                    <span style={{ fontWeight: 700, fontSize: 13 }}>Plan Evolution Trail</span>
                  </div>
                  <span className="muted" style={{ fontSize: 11 }}>Latest revisions</span>
                </div>
                <div className="stack" style={{ gap: 6, marginTop: 8 }}>
                  {changelog.map(c => (
                    <div key={c.id} className="between" style={{ fontSize: 11.5, padding: '4px 0', borderBottom: '1px solid var(--line-2)', gap: 8 }}>
                      <div>
                        <b>{c.reason}</b>
                        <div className="muted" style={{ fontSize: 10.5 }}>{c.previous_val} → {c.new_val} · {c.impact_summary}</div>
                      </div>
                      <span className="muted" style={{ fontSize: 10, whiteSpace: 'nowrap' }}>{relDay(c.ts)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ───────────── CALENDAR TAB ───────────── */}
        {subtab === 'calendar' && (
          <div className="stack" style={{ gap: 14 }}>
            <div className="card card-pad">
              <div className="between" style={{ marginBottom: 10 }}>
                <div>
                  <div className="card-title">Balance forecast</div>
                  <div className="muted" style={{ fontSize: 11.5 }}>Next 30 days · salary, debits and usual spending</div>
                </div>
              </div>
              <ForecastChart forecast={plan.forecast} />
            </div>

            <div className="between">
              <div>
                <div className="section-title">Upcoming Obligations</div>
                <div className="muted" style={{ fontSize: 11.5 }}>Next 30 days commitments vs liquid buffer</div>
              </div>
              {collision30.has_collision
                ? <span className="pill pill-bad">{inr(collision30.shortfall)} short</span>
                : <span className="pill pill-ok">Buffer Protected</span>}
            </div>

            <div className="card">
              {obligations30.length === 0 ? (
                <div style={{ padding: 20, textAlign: 'center', color: 'var(--ink-3)', fontSize: 13 }}>
                  No obligations scheduled in the next 30 days.
                </div>
              ) : (
                obligations30.map(o => (
                  <div key={o.id} className="list-row">
                    <div className="cat-icon cat-investment" style={{ width: 34, height: 34, fontSize: 14 }}>
                      {o.category === 'sip' ? <TrendingUp size={16} /> : o.category === 'emi' ? <Landmark size={16} /> : <ShieldCheck size={16} />}
                    </div>
                    <div className="grow">
                      <div className="t">{o.title}</div>
                      <div className="s">{dueLabel(o.due)} · {o.recipient || o.source || 'Direct debit'}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 700, fontSize: 13.5 }}>{inr(o.amount)}</div>
                      <span className="pill pill-neutral" style={{ height: 18, fontSize: 9.5 }}>{o.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="saarthi-strip">
              <div className="t">
                <b>Total 30-Day Commitments:</b> {inr(collision30.total_obligations)}.{' '}
                {collision30.has_collision
                  ? `Your liquid balance of ${inr(ef.current_liquid)} falls ${inr(collision30.shortfall)} short - top up or reschedule before the due dates.`
                  : `Your liquid balance of ${inr(ef.current_liquid)} covers them in full.`}
              </div>
            </div>
          </div>
        )}
      </div>

      <ProfileSheet key={plan.profile.monthly_income + ':' + plan.profile.salary_day} open={showProfile}
        onClose={() => setShowProfile(false)} profile={plan.profile} onSaved={afterSave} />
      <GoalActionSheet goal={goalSheet?.goal ?? null} mode={goalSheet?.mode ?? 'add'} onClose={() => setGoalSheet(null)} onSaved={afterSave} />

      {/* ───────────── ADD GOAL MODAL SHEET ───────────── */}
      <Sheet open={showAddGoal} onClose={() => setShowAddGoal(false)} title="Create Financial Goal">
        <form onSubmit={handleCreateGoal}>
          {/* Presets */}
          <div className="muted" style={{ fontSize: 11.5, marginBottom: 6 }}>Popular Goal Presets:</div>
          <div className="chips-row">
            {GOAL_PRESETS.map(p => (
              <button key={p.name} type="button" className="chip-btn" onClick={() => pickPreset(p)}>
                {p.name}
              </button>
            ))}
          </div>

          <div className="field">
            <label className="lbl">Goal Name</label>
            <input
              className="input"
              required
              value={newGoalName}
              onChange={e => setNewGoalName(e.target.value)}
              placeholder="e.g. Electric Vehicle Down Payment"
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="field">
              <label className="lbl">Target Amount (₹)</label>
              <input
                className="input"
                type="number"
                required
                value={newGoalTarget}
                onChange={e => setNewGoalTarget(e.target.value)}
                placeholder="500000"
              />
            </div>
            <div className="field">
              <label className="lbl">Initial Amount (₹)</label>
              <input
                className="input"
                type="number"
                value={newGoalCurrent}
                onChange={e => setNewGoalCurrent(e.target.value)}
                placeholder="50000"
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div className="field">
              <label className="lbl">Target Date</label>
              <input
                className="input"
                type="date"
                required
                value={newGoalDate}
                onChange={e => setNewGoalDate(e.target.value)}
              />
            </div>
            <div className="field">
              <label className="lbl">Monthly Contribution (₹)</label>
              <input
                className="input"
                type="number"
                value={newGoalMonthly}
                onChange={e => setNewGoalMonthly(e.target.value)}
                placeholder="10000"
              />
            </div>
          </div>

          <div className="row" style={{ marginTop: 20, justifyContent: 'flex-end', gap: 10 }}>
            <button type="button" className="btn btn-ghost" onClick={() => setShowAddGoal(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={creatingGoal || !newGoalName || !newGoalTarget}>
              {creatingGoal ? <Loader2 size={16} className="spin" /> : 'Save Goal'}
            </button>
          </div>
        </form>
      </Sheet>
    </div>
  )
}
