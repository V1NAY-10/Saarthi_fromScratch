import { FlaskConical, Loader2, Play } from 'lucide-react'
import { useState } from 'react'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'

const FAMILY_TONE: Record<string, string> = {
  Document: 'pill-info', Identity: 'pill-warn', Unknown: 'pill-bad', Partner: 'pill-neutral', Payment: 'pill-neutral',
  Mandate: 'pill-neutral', 'Account verification': 'pill-warn',
}

/** One-click demo scenarios. Each runs ordinary user actions; the real pipeline produces the failure. */
export function DemoScenarios({ compact = false }: { compact?: boolean }) {
  const { push, bump, showToast } = useApp()
  const { data } = useData(() => api.scenarios())
  const [busy, setBusy] = useState<string | null>(null)

  async function run(id: string) {
    setBusy(id)
    try {
      const r = await api.runScenario(id)
      bump()
      push({ name: 'journey', id: r.journey_id })
    } catch (e) { showToast((e as Error).message) } finally { setBusy(null) }
  }

  return (
    <div>
      <div className="sandbox-tag"><FlaskConical size={12} /> Demo scenarios · real pipeline</div>
      {!compact && <div className="hint" style={{ marginTop: 4 }}>Each one links accounts, uploads sample documents or submits an application for you. The partner's own rules produce the failure.</div>}
      <div className="stack" style={{ marginTop: 8, gap: 6 }}>
        {data?.map((s, i) => (
          <button key={s.id} className="list-row tap card" style={{ width: '100%', textAlign: 'left', padding: compact ? '8px 10px' : undefined }} disabled={!!busy} onClick={() => run(s.id)}>
            <span className="attn-num" style={{ flexShrink: 0 }}>{i + 1}</span>
            <div className="grow">
              <div className="t" style={{ fontSize: compact ? 12.5 : undefined }}>{s.title}</div>
              {!compact && <div className="s">{s.what}</div>}
            </div>
            {!compact && <span className={`pill ${FAMILY_TONE[s.family] ?? 'pill-neutral'}`}>{s.family}</span>}
            {busy === s.id ? <Loader2 size={15} className="spin" /> : <Play size={14} className="muted" />}
          </button>
        ))}
      </div>
    </div>
  )
}
