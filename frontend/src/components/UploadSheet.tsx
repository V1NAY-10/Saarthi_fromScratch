import { FileUp, FlaskConical, Loader2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { useApp } from '../hooks/useApp'
import { api } from '../services/api'
import type { VaultDocument } from '../services/types'
import { Sheet } from './ui'

export const DOC_TYPES: [string, string][] = [
  ['', 'Detect automatically'], ['BANK_STATEMENT', 'Bank statement'], ['SALARY_SLIP', 'Salary slip'], ['PAN', 'PAN card'],
  ['AADHAAR', 'Aadhaar card'], ['DRIVING_LICENCE', 'Driving licence'], ['MEDICAL_REPORT', 'Medical report'],
  ['FORM16', 'Form 16'], ['ADDRESS_PROOF', 'Address proof'], ['CANCELLED_CHEQUE', 'Cancelled cheque'],
]

const SAMPLE_FOR: Record<string, string[]> = {
  BANK_STATEMENT: ['bank_statement_3m', 'bank_statement_1m', 'statement_other_person', 'unreadable_scan'],
  SALARY_SLIP: ['salary_slip'],
  IDENTITY: ['aadhaar', 'pan_card', 'aadhaar_wrong_dob', 'driving_licence_expired'],
  MEDICAL_REPORT: ['medical_report'],
}
const LABELS: Record<string, string> = {
  bank_statement_1m: 'Bank statement · 1 month', bank_statement_3m: 'Bank statement · 3 months', salary_slip: 'Salary slip',
  pan_card: 'PAN card', aadhaar: 'Aadhaar', aadhaar_wrong_dob: 'Aadhaar · wrong DOB', driving_licence_expired: 'Driving licence · expired',
  medical_report: 'Medical report', statement_other_person: "Someone else's statement", unreadable_scan: 'Scanned statement (no text)',
}

/** Upload a document into the vault: a real file, or a generated synthetic sample, through the same pipeline. */
export function UploadSheet({ open, onClose, want, replaceId, onDone }: {
  open: boolean; onClose: () => void; want?: string; replaceId?: string; onDone?: (d: VaultDocument) => void
}) {
  const { bump, showToast } = useApp()
  const input = useRef<HTMLInputElement>(null)
  const [docType, setDocType] = useState(want && want !== 'IDENTITY' ? want : '')
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const samples = want ? (SAMPLE_FOR[want] ?? []) : Object.keys(LABELS)

  async function send(blob: Blob, name: string, hint?: string) {
    setErr(null)
    try {
      const d = await api.uploadDocument(blob, name, hint || docType || undefined, replaceId)
      showToast(d.duplicate ? `${d.name} is already in your vault` : `${d.name} v${d.latest_version} added · ${d.status.toLowerCase().replace('_', ' ')}`)
      bump(); onDone?.(d); onClose()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }

  async function pickFile(f: File | undefined) {
    if (!f) return
    setBusy('file')
    await send(f, f.name)
  }

  async function sample(kind: string) {
    setBusy(kind)
    try {
      const { blob, name } = await api.sampleBlob(kind)
      await send(blob, name, kind.includes('statement') || kind === 'unreadable_scan' ? 'BANK_STATEMENT' : undefined)
    } catch (e) { setErr((e as Error).message); setBusy(null) }
  }

  return (
    <Sheet open={open} onClose={onClose} title={replaceId ? 'Upload a new version' : 'Add to Document Vault'}>
      <label className="field" style={{ marginTop: 0 }}>
        <span className="lbl">Document type</span>
        <select className="input" value={docType} onChange={e => setDocType(e.target.value)}>
          {DOC_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      <input ref={input} type="file" accept="application/pdf,image/png,image/jpeg,text/plain" hidden onChange={e => pickFile(e.target.files?.[0])} />
      <button className="btn btn-primary btn-lg btn-block" style={{ marginTop: 14 }} disabled={!!busy} onClick={() => input.current?.click()}>
        {busy === 'file' ? <><Loader2 size={18} className="spin" /> Reading document…</> : <><FileUp size={18} /> Choose a file</>}
      </button>
      <div className="hint">PDF, PNG, JPG or text · up to 5 MB. Text is read from the PDF itself; photos are stored but can't be read.</div>
      {samples.length > 0 && (
        <div className="sandbox">
          <div className="sandbox-tag"><FlaskConical size={12} /> Sandbox · synthetic sample documents</div>
          <div className="hint" style={{ marginTop: 6 }}>Generated for your name, then uploaded through the same pipeline as a real file.</div>
          <div className="chips-row">
            {samples.map(k => (
              <button key={k} className="chip-btn" disabled={!!busy} onClick={() => sample(k)}>
                {busy === k ? <Loader2 size={12} className="spin" /> : null} {LABELS[k]}
              </button>
            ))}
          </div>
        </div>
      )}
      {err && <div className="form-err">{err}</div>}
    </Sheet>
  )
}
