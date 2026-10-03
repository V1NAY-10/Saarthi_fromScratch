import { motion } from 'framer-motion'
import {
  ArrowRight, BookOpen, CheckCircle2, ChevronDown, ChevronUp, Database, FileWarning, Headset, ShieldCheck, Sparkles, XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { CheckRow, JsonView, SaarthiMark, TierBadge } from '../../components/ui'
import { TIER_TEXT, dateTime, inr } from '../../services/format'
import type { Action, AgentRun, Decision, Diagnosis, JourneyView } from '../../services/types'

const fade = (i: number) => ({ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { delay: 0.05 + i * 0.07 } })

/* ── What happened ───────────────────────────── */
export function WhatHappened({ d, run }: { d: Diagnosis; run?: AgentRun | null }) {
  const e = d.explanation
  return (
    <motion.div className="card card-saarthi what" {...fade(0)}>
      <div className="row" style={{ marginBottom: 10 }}>
        <SaarthiMark size={20} />
        <span className="eyebrow" style={{ color: 'var(--brand)' }}>What happened?</span>
      </div>
      <h3>{e.headline}</h3>
      <p>{e.summary}</p>
      <div className="facts">
        {d.facts.map(f => (
          <div key={f.label} className={`fact ${f.emphasis ? 'emph' : ''}`}>
            <div className="k">{f.label}</div>
            <div className="v num">{f.value}</div>
            <div className="src">{f.source}</div>
          </div>
        ))}
      </div>
      <div className="safe-note"><ShieldCheck size={16} style={{ flexShrink: 0, marginTop: 1 }} /><span>{e.safety_note}</span></div>
      <div className="source-tag">
        <Database size={11} />
        {run ? `Investigated in ${run.trace.filter(t => t.type === 'tool').length} agent steps` : 'Built'} from {d.partner.partner_name}'s response · {d.evidence.length} evidence sources · {d.knowledge.length + 1} knowledge entries
        {e.source === 'llm' && <> · <Sparkles size={11} /> written by Claude, {e.grounding.numbers_checked} numbers grounding-checked</>}
        {e.llm_rejected && <> · Claude's wording failed the grounding check, so the verified template is shown</>}
      </div>
    </motion.div>
  )
}

/* ── Partner status → Saarthi understanding ───────────────────────────── */
export function Normalization({ d }: { d: Diagnosis }) {
  const [raw, setRaw] = useState(false)
  const n = d.normalized
  const rows: [string, React.ReactNode][] = [
    ['Failure type', <>{n.meaning} <span className="muted mono" style={{ fontSize: 11 }}>{n.standard_code}</span></>],
    ['Root cause', <>{n.root_cause} {d.root_cause_confirmed ? <CheckCircle2 size={13} color="var(--ok)" style={{ verticalAlign: -2 }} /> : <span className="pill pill-warn" style={{ height: 18 }}>unconfirmed</span>}</>],
    ['Evidence', d.evidence.map(e => e.label).join(' · ')],
    ['Recovery', d.options.find(o => o.recommended)?.effects.label ?? '—'],
    ['Outcome', n.expected_outcome],
  ]
  return (
    <motion.div className="card norm" {...fade(1)}>
      <div className="between">
        <div className="card-title">Partner said → Saarthi understood</div>
        <button className="section-link" onClick={() => setRaw(r => !r)} style={{ fontSize: 12 }}>{raw ? 'Hide' : 'Raw'} response</button>
      </div>
      <div className="norm-arrow" style={{ marginTop: 10 }}>
        <span className="chip">{d.partner.partner_name}</span>
        <span className="code-chip">{n.partner_code}</span>
        <ArrowRight size={14} className="muted" />
        <span className="pill pill-info">{n.meaning}</span>
      </div>
      {raw && (
        <div style={{ marginBottom: 8 }}>
          <div className="muted mono" style={{ fontSize: 10.5 }}>{d.partner_endpoints?.join('  ·  ')}</div>
          <JsonView data={d.partner_raw} />
        </div>
      )}
      {rows.map(([k, v]) => (
        <div key={k} className="norm-row"><div className="k">{k}</div><div className="v">{v}</div></div>
      ))}
      {n.equivalents.length > 1 && (
        <div className="muted" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.45 }}>
          Same failure across partners: {n.equivalents.map(x => x.code).join(', ')} — normalized to <span className="mono">{n.standard_code}</span>.
        </div>
      )}
    </motion.div>
  )
}

/* ── Name match intelligence ───────────────────────────── */
export function NameMatch({ d }: { d: Diagnosis }) {
  const m = d.name_match
  if (!m) return null
  const pan = d.facts.find(f => f.label === 'Name on PAN')?.value
  const bank = d.facts.find(f => f.label === 'Name at bank')?.value
  const own = d.metrics.ownership_check as string | null
  return (
    <motion.div className="card card-pad" {...fade(2)}>
      <div className="row"><FileWarning size={17} color="var(--warn)" /><div className="card-title">Name match, token by token</div></div>
      <div className="namecmp">
        <div className="nb"><div className="k">PAN (KYC)</div><div className="v">{pan}</div></div>
        <div className="nb" style={{ borderColor: m.verdict === 'different' ? '#f4c7c1' : '#f3d9a6' }}><div className="k">Bank record</div><div className="v">{bank}</div></div>
      </div>
      <div style={{ marginTop: 10 }}>
        {m.pairs.map((p, i) => <span key={i} className={`tok ${p.kind}`}>{p.token}{p.matched && p.matched !== p.token ? ` ↔ ${p.matched}` : ''} · {p.kind}</span>)}
      </div>
      <div className="conf" style={{ marginTop: 12 }}>
        <span>Match score</span><span className="bar"><i style={{ width: `${m.score * 100}%`, background: m.score >= 0.85 ? 'var(--ok)' : m.score >= 0.5 ? 'var(--warn)' : 'var(--bad)' }} /></span>
        <b className="num">{m.score.toFixed(2)}</b>
      </div>
      <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }}>0.85 passes automatically · {m.reasons.join(' · ')}</div>
      {own && (
        <div className="saarthi-strip" style={{ marginTop: 10 }}>
          {own === 'PAN_MATCH' ? <CheckCircle2 size={18} color="var(--ok)" /> : <XCircle size={18} color="var(--bad)" />}
          <div className="t">Account Aggregator check: the bank's record carries {own === 'PAN_MATCH' ? <b>your PAN</b> : <b>a different PAN</b>}.</div>
        </div>
      )}
    </motion.div>
  )
}

/* ── Saarthi found the cause (document & identity failures) ───────────────────────────── */
export function FoundTheCause({ d, decision }: { d: Diagnosis; decision: Decision | null }) {
  const ev = d.document_evidence
  if (!ev) return null
  const engine = d.knowledge[0]?.engine
  return (
    <motion.div className="card card-pad card-saarthi" {...fade(1)}>
      <div className="row"><SaarthiMark size={20} /><span className="eyebrow" style={{ color: 'var(--brand)' }}>Saarthi found the cause</span></div>
      <div style={{ fontWeight: 800, fontSize: 16, marginTop: 8 }}>{d.normalized.meaning}</div>
      <div className="eyebrow" style={{ marginTop: 12 }}>Evidence</div>
      <div className="match" style={{ marginTop: 6 }}>
        <div className="doc good"><div className="k">{d.partner.partner_name.split(' (')[0]} requires</div><div className="v" style={{ fontSize: 12.5 }}>{ev.required}</div></div>
        <div style={{ textAlign: 'center' }}><ArrowRight size={18} className="muted" /></div>
        <div className="doc bad"><div className="k">Your {ev.doc_label.toLowerCase()}</div><div className="v" style={{ fontSize: 12.5 }}>{ev.found}</div>
          {ev.submitted && <div className="s">{ev.submitted.name} v{ev.submitted.version}</div>}</div>
      </div>
      {ev.candidates.length > 0 && <>
        <div className="eyebrow" style={{ marginTop: 14 }}>Saarthi checked your Document Vault</div>
        {ev.candidates.map(c => (
          <div key={c.version_id} className="cand">
            <div className="grow">
              <div style={{ fontWeight: 600 }}>{c.name} v{c.version}{c.already_submitted ? ' · submitted' : ''}</div>
              <div className="muted" style={{ fontSize: 11 }}>{c.summary}{!c.ok && c.issues[0] ? ` · ${c.issues[0]}` : ''}</div>
            </div>
            <span className={`mini-flag ${c.ok ? 'ok' : 'no'}`}>{c.ok ? '✓ meets rule' : '✗ fails rule'}</span>
          </div>
        ))}
      </>}
      <div className="kv" style={{ marginTop: 14 }}>
        <span className="k">Knowledge source</span>
        <span className="v">{d.kb_entry?.source ? <span className="mono" style={{ fontSize: 11 }}>knowledge/{d.kb_entry.source}</span> : 'Partner rule'}{engine ? ` · ${engine === 'cognee' ? 'Cognee' : 'BM25'}` : ''}</span>
        {decision && <><span className="k">Decision</span><span className="v">{TIER_TEXT[decision.tier].short} · {TIER_TEXT[decision.tier].long}</span></>}
      </div>
    </motion.div>
  )
}

export function UnknownCard({ d }: { d: Diagnosis }) {
  if (!d.unknown) return null
  return (
    <motion.div className="card card-pad" style={{ borderColor: '#f3d9a6', background: 'var(--warn-soft)' }} {...fade(0)}>
      <div className="row"><FileWarning size={20} color="var(--warn)" /><div style={{ fontWeight: 800, fontSize: 15 }}>Saarthi couldn't confidently identify this issue</div></div>
      <div className="kv" style={{ marginTop: 12 }}>
        <span className="k">Partner</span><span className="v">{d.partner.partner_name}</span>
        <span className="k">Code</span><span className="v mono">{d.partner.raw_code}</span>
        <span className="k">Knowledge found</span><span className="v">Nothing that reliably describes this code</span>
        <span className="k">Action</span><span className="v">Human review required</span>
      </div>
      <p className="ink2" style={{ fontSize: 12.5, lineHeight: 1.5, marginTop: 10 }}>Saarthi doesn't guess. Unknown partner codes are never acted on automatically.</p>
    </motion.div>
  )
}

/* ── Decision: why Saarthi decided this ───────────────────────────── */
export function DecisionCard({ d, decision, view }: { d: Diagnosis; decision: Decision; view: JourneyView }) {
  const [showAll, setShowAll] = useState(false)
  const option = d.options.find(o => o.id === decision.option_id)!
  const approved = view.actions.find(a => a.action_type === option.action_type && a.status === 'COMPLETED')
  const checks = decision.checks.filter(c => c.id !== 'classified')
  const failed = checks.filter(c => !c.passed)
  const visible = showAll ? checks : [...failed, ...checks.filter(c => c.passed)].slice(0, failed.length ? Math.max(failed.length + 2, 6) : 7)
  const t = decision.tier.slice(-1)
  return (
    <motion.div className="card card-pad" {...fade(3)}>
      <div className="between">
        <div className="card-title">{decision.tier === 'TIER_3' ? 'Why Saarthi paused' : 'Why Saarthi decided this'}</div>
        <TierBadge tier={decision.tier} />
      </div>
      <div className="conf" style={{ marginTop: 10 }}>
        <span>Confidence</span><span className="bar"><i style={{ width: `${decision.confidence * 100}%` }} /></span>
        <b className="num">{Math.round(decision.confidence * 100)}%</b>
      </div>
      <div className="checks" style={{ marginTop: 8 }}>
        {visible.map(c => <CheckRow key={c.id} passed={c.passed} label={c.label} detail={c.detail} />)}
      </div>
      {checks.length > visible.length || showAll ? (
        <button className="section-link row" style={{ gap: 4, marginTop: 4 }} onClick={() => setShowAll(s => !s)}>
          {showAll ? <>Show fewer <ChevronUp size={14} /></> : <>All {checks.length} checks <ChevronDown size={14} /></>}
        </button>
      ) : null}
      <div className={`verdict t${t}`}>
        <ArrowRight size={16} />
        <span>{approved ? 'Approved by you · executed & verified' : decision.tier === 'TIER_3' ? 'TIER 3 — HUMAN ESCALATION' : decision.tier === 'TIER_2' ? 'USER APPROVAL REQUIRED' : 'SAFE TO AUTO-RUN'}</span>
      </div>
      {decision.tier === 'TIER_3' && (
        <p style={{ fontSize: 13, lineHeight: 1.5, marginTop: 10, color: 'var(--ink-2)' }}>
          “I can't prove this is safe to fix automatically, so I won't try. I've prepared everything a specialist needs.”
        </p>
      )}
      <div className="muted" style={{ fontSize: 11, marginTop: 10, lineHeight: 1.45 }}>
        Tier is computed by Saarthi's deterministic safety engine from these checks and partner policy ({d.normalized.policy_tier.replace('_', ' ')} floor). The AI cannot lower it.
      </div>
    </motion.div>
  )
}

/* ── Recovery options ───────────────────────────── */
export function Options({ d, onPick }: { d: Diagnosis; onPick?: (id: string) => void }) {
  return (
    <motion.div className="card card-pad" {...fade(4)}>
      <div className="card-title" style={{ marginBottom: 10 }}>Recovery paths Saarthi found</div>
      <div className="stack">
        {d.options.map(o => {
          const dec = d.decisions.by_option[o.id]
          return (
            <div key={o.id} className={`option ${o.recommended ? 'rec' : ''}`}>
              <div className="between" style={{ alignItems: 'flex-start' }}>
                <div className="ot">{o.title}</div>
                {o.recommended && <span className="pill pill-info">Recommended</span>}
              </div>
              <div className="od">{o.description}</div>
              <div className="flags">
                {dec && <TierBadge tier={dec.tier} />}
                <span className="chip">{o.effects.moves_money ? 'Moves money' : 'No money moved'}</span>
                <span className="chip">{o.effects.reversible ? 'Reversible' : 'Irreversible'}</span>
                {o.effects.shares_data && <span className="chip">Shares data</span>}
              </div>
              {onPick && !o.recommended && dec?.tier === 'TIER_1' && (
                <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={() => onPick(o.id)}>Do this instead</button>
              )}
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}

/* ── Evidence + retrieved knowledge ───────────────────────────── */
export function EvidenceKnowledge({ d }: { d: Diagnosis }) {
  const [open, setOpen] = useState(false)
  return (
    <motion.div className="card card-pad" {...fade(5)}>
      <button className="between" style={{ width: '100%' }} onClick={() => setOpen(o => !o)}>
        <div className="row"><BookOpen size={16} color="var(--brand)" /><div className="card-title">Evidence & knowledge used</div></div>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div style={{ marginTop: 10 }}>
          <div className="eyebrow">Evidence (system of record)</div>
          {d.evidence.map(e => <CheckRow key={e.key} passed={e.verified} label={`${e.label}: ${e.display}`} detail={e.source + (e.note ? ` · ${e.note}` : '')} />)}
          <div className="eyebrow" style={{ marginTop: 12 }}>Retrieved knowledge ({d.knowledge[0]?.engine === 'cognee' ? 'Cognee' : 'BM25 fallback'})</div>
          {[...(d.kb_entry ? [{ id: d.kb_entry.id, title: d.kb_entry.title, score: 1, kind: 'partner rule · exact registry match' }] : []), ...d.knowledge].map(k => (
            <div key={k.id} className="between" style={{ padding: '7px 0', borderTop: '1px solid var(--line-2)' }}>
              <div className="grow">
                <div style={{ fontSize: 12.5, fontWeight: 600 }}>{k.title}</div>
                <div className="muted" style={{ fontSize: 10.5 }}>{k.kind.replace('_', ' ')} · {k.id}</div>
              </div>
              <span className="chip num">{k.score.toFixed(2)}</span>
            </div>
          ))}
          {d.missing.length > 0 && <>
            <div className="eyebrow" style={{ marginTop: 12 }}>Missing information</div>
            {d.missing.map(m => <div key={m} style={{ fontSize: 12.5, padding: '4px 0' }}>• {m}</div>)}
          </>}
        </div>
      )}
    </motion.div>
  )
}

/* ── Resolved ───────────────────────────── */
export function ResolvedCard({ view, action }: { view: JourneyView; action: Action }) {
  const d = view.diagnosis!
  const steps = action.result.steps ?? []
  const l = d.lesson
  const [raw, setRaw] = useState<number | null>(null)
  return (
    <>
      <motion.div className="card" {...fade(0)}>
        <div className="success-hero">
          <div className="success-badge"><CheckCircle2 size={34} /></div>
          <div className="display" style={{ fontSize: 20, fontWeight: 800 }}>
            {({ investment: 'Your installment went through', bank_account: 'Bank account verified', loan: 'Loan disbursed',
              insurance: 'Policy issued', kyc: 'Identity verified' } as Record<string, string>)[view.journey.category]}
          </div>
          <div className="muted" style={{ fontSize: 13, marginTop: 6 }}>
            {view.journey.category === 'investment'
              ? `${inr(view.journey.amount)} debited · Ref ${view.journey.state.bank_ref ?? ''} · units allotted`
              : view.journey.category === 'bank_account' ? `${view.journey.partner_name} confirmed ownership · ready for SIP autopay`
                : `${view.journey.partner_name.split(' (')[0]} accepted the documents · verified with the partner`}
          </div>
          {d.health_transition && (
            <div className="transition">
              <span className="display num" style={{ fontSize: 22, fontWeight: 800, color: 'var(--warn)' }}>{d.health_transition.before}</span>
              <ArrowRight size={18} className="muted" />
              <span className="display num" style={{ fontSize: 22, fontWeight: 800, color: 'var(--ok)' }}>{d.health_transition.after}</span>
              <span className="pill pill-ok">Journey health</span>
            </div>
          )}
        </div>
      </motion.div>
      <motion.div className="card card-pad" {...fade(1)}>
        <div className="between"><div className="card-title">What Saarthi did</div><TierBadge tier={action.tier} /></div>
        <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>{action.tier === 'TIER_1' ? 'Done automatically' : 'Approved by you'} · {action.completed_at && dateTime(action.completed_at)}</div>
        <div style={{ marginTop: 8 }}>
          {steps.map((s, i) => (
            <div key={i} className="exec-step" style={{ cursor: s.partner_raw ? 'pointer' : undefined }} onClick={() => setRaw(raw === i ? null : i)}>
              <span className={`exec-ic ${s.ok ? 'ok' : 'no'}`}>{s.ok ? <CheckCircle2 size={15} /> : <XCircle size={15} />}</span>
              <div className="grow">
                <div style={{ fontWeight: 600, fontSize: 13 }}>{s.label}</div>
                <div className="muted" style={{ fontSize: 11.5, marginTop: 1 }}>{s.detail}</div>
                {s.endpoint && <div className="mono muted" style={{ fontSize: 10, marginTop: 3 }}>{s.endpoint}</div>}
                {raw === i && s.partner_raw && <JsonView data={s.partner_raw} />}
              </div>
            </div>
          ))}
        </div>
      </motion.div>
      {l && (
        <motion.div className="card learn-card" {...fade(2)}>
          <div className="row"><SaarthiMark size={22} /><div className="card-title">Saarthi learned from this resolution</div></div>
          <div className="muted" style={{ fontSize: 12, marginTop: 6, lineHeight: 1.5 }}>
            Outcome recorded for <span className="mono">{l.partner_code}</span>. The next time any bank returns this failure, diagnosis confidence uses {l.after.resolved} of {l.after.occurrences} incidents resolved.
          </div>
          <div className="kv" style={{ marginTop: 10 }}>
            <span className="k">Resolution time (this journey)</span><span className="v num">{l.resolution_seconds < 3600 ? `${l.resolution_seconds}s` : `${(l.resolution_seconds / 3600).toFixed(1)}h`}</span>
            <span className="k">Recovery success rate</span><span className="v num">{l.before.success_rate === null ? 'no data' : `${(l.before.success_rate * 100).toFixed(0)}%`} → {(l.after.success_rate * 100).toFixed(0)}%</span>
            <span className="k">Incidents in pattern</span><span className="v num">{l.before.occurrences} → {l.after.occurrences}</span>
            <span className="k">Avg. resolution</span><span className="v num">{Math.round(l.before.avg_resolution_s)}s → {Math.round(l.after.avg_resolution_s)}s</span>
          </div>
        </motion.div>
      )}
    </>
  )
}

/* ── Escalation case ───────────────────────────── */
export function SupportCaseCard({ view }: { view: JourneyView }) {
  const c = view.support_case!
  const p = c.payload
  const [raw, setRaw] = useState(false)
  return (
    <>
      <motion.div className="card card-pad" {...fade(0)}>
        <div className="row" style={{ gap: 12 }}>
          <div className="cat-icon cat-kyc"><Headset size={20} /></div>
          <div className="grow">
            <div className="card-title">Escalated to a specialist</div>
            <div className="muted" style={{ fontSize: 12 }}>Case {c.id} · {p.priority}</div>
          </div>
          <span className="pill pill-warn">Open</span>
        </div>
        <div className="safe-note" style={{ marginTop: 12 }}><ShieldCheck size={16} style={{ flexShrink: 0, marginTop: 1 }} /><span>{p.customer_safety} {p.sla}.</span></div>
      </motion.div>
      <motion.div className="card card-pad" {...fade(1)}>
        <div className="eyebrow">Why escalation happened</div>
        {p.why_escalated.map((r: string) => <div key={r} style={{ fontSize: 13, padding: '5px 0', fontWeight: 600 }}>• {r}</div>)}
        <div className="eyebrow" style={{ marginTop: 12 }}>What Saarthi already checked</div>
        {p.checks_completed.slice(0, 6).map((ch: any) => <CheckRow key={ch.id} passed label={ch.label} detail={ch.detail} />)}
        {p.failed_checks.map((ch: any) => <CheckRow key={ch.id} passed={false} label={ch.label} detail={ch.detail} />)}
        <div className="eyebrow" style={{ marginTop: 12 }}>Evidence collected</div>
        {p.facts.map((f: any) => (
          <div key={f.label} className="between" style={{ padding: '5px 0', fontSize: 12.5 }}>
            <span className="muted">{f.label}</span><span style={{ fontWeight: 700 }}>{f.value}</span>
          </div>
        ))}
        <div className="eyebrow" style={{ marginTop: 12 }}>Partner response</div>
        <div className="norm-arrow" style={{ marginTop: 6 }}>
          <span className="code-chip">{p.partner_response.normalized.raw_code}</span>
          <span className="muted" style={{ fontSize: 12 }}>{p.partner_response.normalized.raw_message}</span>
        </div>
        <div className="eyebrow" style={{ marginTop: 12 }}>Recommended next action</div>
        <div style={{ fontSize: 13, lineHeight: 1.5, marginTop: 4 }}>{p.recommended_next_action}</div>
        {p.do_not.map((x: string) => <div key={x} style={{ fontSize: 12, color: 'var(--bad)', marginTop: 6, fontWeight: 600 }}>⛔ {x}</div>)}
        <button className="section-link" style={{ marginTop: 12 }} onClick={() => setRaw(r => !r)}>{raw ? 'Hide' : 'View'} structured case sent to support</button>
        {raw && <JsonView data={{ ...p, timeline: `${p.timeline.length} events`, partner_calls: `${p.partner_calls.length} calls` }} />}
      </motion.div>
    </>
  )
}

export function TierExplainer() {
  return (
    <div className="card card-pad" style={{ background: 'var(--surface-2)' }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>Saarthi's tiered autonomy</div>
      {(['TIER_1', 'TIER_2', 'TIER_3'] as const).map(t => (
        <div key={t} className="between" style={{ padding: '4px 0' }}>
          <TierBadge tier={t} /><span className="muted" style={{ fontSize: 12 }}>{TIER_TEXT[t].long}</span>
        </div>
      ))}
    </div>
  )
}
