import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertTriangle, BookOpen, Brain, Database, FileSearch, Landmark, Loader2, Route, Scale, Send, ShieldCheck, Sparkles, UserCheck, Wallet,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { JsonView } from '../../components/ui'
import type { AgentRun, TraceStep } from '../../services/types'

const TOOL: Record<string, [string, typeof Brain]> = {
  get_journey_context: ['Read the journey', FileSearch],
  query_partner_status: ["Called the bank's API", Landmark],
  lookup_failure_knowledge: ['Looked up the failure code', BookOpen],
  collect_evidence: ['Collected evidence', Database],
  list_customer_accounts: ['Checked your accounts', Wallet],
  compare_names: ['Compared names', UserCheck],
  search_policies: ['Retrieved policies', Scale],
  build_recovery_options: ['Built recovery options', Route],
  evaluate_option: ['Safety engine classified an option', ShieldCheck],
  submit_plan: ['Submitted a plan', Send],
}

/** Reveals trace steps one by one while the agent is (or just was) running, so the
 *  reasoning reads as it happened. Already-finished runs render instantly. */
function useReveal(total: number, animate: boolean) {
  const [shown, setShown] = useState(animate ? 0 : total)
  useEffect(() => {
    if (!animate) { setShown(total); return }
    if (shown >= total) return
    const t = window.setTimeout(() => setShown(s => s + 1), shown === 0 ? 150 : 380)
    return () => window.clearTimeout(t)
  }, [total, shown, animate])
  return shown
}

export function AgentTrace({ run, compact = false, replay = false, onDone }: { run: AgentRun; compact?: boolean; replay?: boolean; onDone?: () => void }) {
  const wasRunning = useRef(run.status === 'RUNNING' || replay)
  if (run.status === 'RUNNING') wasRunning.current = true
  const shown = useReveal(run.trace.length, wasRunning.current)
  const steps = run.trace.slice(0, shown)
  const working = run.status === 'RUNNING' || shown < run.trace.length
  useEffect(() => {
    if (!working && onDone) { const t = window.setTimeout(onDone, 700); return () => window.clearTimeout(t) }
  }, [working, onDone])
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => { if (compact) bottom.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }, [shown, compact])

  return (
    <div className="trace">
      <AnimatePresence initial={false}>
        {steps.map((s, i) => <Step key={i} s={s} compact={compact} />)}
      </AnimatePresence>
      {working && (
        <div className="trace-step">
          <span className="trace-ic run"><Loader2 size={14} className="spin" /></span>
          <div className="trace-why" style={{ paddingTop: 4 }}>{run.mode.startsWith('llm') ? 'Gemini is reasoning…' : 'Working…'}</div>
        </div>
      )}
      {run.status === 'FAILED' && <div className="form-err">The agent stopped: {run.error}</div>}
      <div ref={bottom} />
    </div>
  )
}

function Step({ s, compact }: { s: TraceStep; compact: boolean }) {
  const [open, setOpen] = useState(false)
  if (s.type === 'thought') {
    return (
      <motion.div className="trace-step" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <span className="trace-ic thought"><Brain size={14} /></span>
        <div className="trace-thought">{s.text}</div>
      </motion.div>
    )
  }
  const [label, Icon] = TOOL[s.tool ?? ''] ?? [s.tool ?? 'tool', Sparkles]
  return (
    <motion.div className="trace-step" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <span className={`trace-ic ${s.ok ? '' : 'err'}`}>{s.ok ? <Icon size={14} /> : <AlertTriangle size={14} />}</span>
      <div style={{ minWidth: 0 }}>
        <div className="between" style={{ gap: 8 }}>
          <div style={{ fontWeight: 700, fontSize: 13 }}>{label}</div>
          {!compact && <span className="trace-tool">{s.tool}()</span>}
        </div>
        {s.rationale && <div className="trace-why">{s.rationale}</div>}
        {s.summary && (
          <button className="trace-out" style={{ display: 'block', width: '100%', textAlign: 'left' }} onClick={() => !compact && setOpen(o => !o)}>
            {s.summary}
          </button>
        )}
        {open && s.data && <JsonView data={s.data} />}
      </div>
    </motion.div>
  )
}

export function AgentBadge({ run }: { run: AgentRun }) {
  const isLlm = run.mode === 'llm'
  return (
    <span className={`pill ${isLlm ? 'pill-info' : 'pill-neutral'}`}>
      {isLlm ? <><Sparkles size={11} /> Gemini agent</> : run.mode === 'llm+fallback' ? 'Gemini → planner fallback' : 'Deterministic planner'}
    </span>
  )
}
