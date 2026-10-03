import { AlertTriangle, BadgeCheck, Clock, ExternalLink, FileText, History, Link2, Plus, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { UploadSheet } from '../components/UploadSheet'
import { Sheet, Skeleton, TopBar } from '../components/ui'
import { useApp, useData } from '../hooks/useApp'
import { api } from '../services/api'
import { dateTime } from '../services/format'
import type { VaultDocument } from '../services/types'

export const DOC_STATUS: Record<string, [string, string]> = {
  VERIFIED: ['Verified', 'pill-ok'], AVAILABLE: ['Available', 'pill-info'], EXPIRING_SOON: ['Expiring soon', 'pill-warn'],
  EXPIRED: ['Expired', 'pill-bad'], MISMATCH: ['Name mismatch', 'pill-bad'], NEEDS_REVIEW: ['Needs review', 'pill-warn'],
  UNREADABLE: ['Unreadable', 'pill-bad'], FAILED: ['Failed', 'pill-bad'],
}

export function DocStatus({ status }: { status: string }) {
  const [label, cls] = DOC_STATUS[status] ?? [status, 'pill-neutral']
  return <span className={`pill ${cls}`}>{label}</span>
}

export function Vault() {
  const { push, overview } = useApp()
  const { data } = useData(() => api.documents())
  const [upload, setUpload] = useState(false)
  const [open, setOpen] = useState<VaultDocument | null>(null)
  const issues = data?.filter(d => ['EXPIRED', 'MISMATCH', 'UNREADABLE', 'EXPIRING_SOON', 'NEEDS_REVIEW'].includes(d.status)) ?? []
  return (
    <div>
      <TopBar title="Document Vault" sub="Upload once, reuse across every journey"
        right={<button className="icon-btn" onClick={() => setUpload(true)} aria-label="Add document"><Plus size={18} /></button>} />
      <div className="page">
        <div className="card card-pad card-saarthi row" style={{ gap: 12 }}>
          <ShieldCheck size={22} color="var(--brand)" />
          <div className="grow ink2" style={{ fontSize: 12.5, lineHeight: 1.45 }}>
            <b>{data?.length ?? 0} documents</b> · read by Saarthi, masked before display. Loans, insurance and KYC reuse them, and each journey records the exact version it used.
            <div className="muted" style={{ fontSize: 11, marginTop: 3 }}>Files stored in {overview?.system.storage?.backend === 'cloudinary' ? 'Cloudinary (private)' : 'local sandbox storage'} · metadata in the app database</div>
          </div>
        </div>
        {issues.length > 0 && (
          <div className="section">
            <div className="section-head"><div className="section-title">Needs attention</div></div>
            <div className="card card-saarthi">
              {issues.map(d => (
                <button key={d.id} className="insight" style={{ width: '100%', textAlign: 'left' }} onClick={() => setOpen(d)}>
                  <AlertTriangle size={17} color="var(--warn)" />
                  <div className="t"><b>{d.name}</b>: {DOC_STATUS[d.status]?.[0].toLowerCase()}{d.meta.summary ? ` · ${d.meta.summary}` : ''}</div>
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="section">
          <div className="section-head"><div className="section-title">Your documents</div></div>
          {!data ? <Skeleton h={240} /> : !data.length ? (
            <div className="card empty">
              No documents yet.
              <button className="btn btn-primary btn-block" style={{ marginTop: 12 }} onClick={() => setUpload(true)}><Plus size={16} /> Add your first document</button>
            </div>
          ) : (
            <div className="stack">
              {data.map(d => (
                <button key={d.id} className="card card-pad row tap" style={{ alignItems: 'flex-start', gap: 12, textAlign: 'left', width: '100%' }} onClick={() => setOpen(d)}>
                  <div className="cat-icon" style={{ width: 36, height: 36, background: 'var(--surface-2)', color: 'var(--brand)' }}><FileText size={17} /></div>
                  <div className="grow" style={{ minWidth: 0 }}>
                    <div className="between" style={{ gap: 8 }}><div style={{ fontWeight: 700, fontSize: 13.5 }}>{d.name}</div><DocStatus status={d.status} /></div>
                    {d.meta.summary && <div className="ink2" style={{ fontSize: 12, marginTop: 3 }}>{d.meta.summary}</div>}
                    <div className="muted row" style={{ fontSize: 11, marginTop: 4, gap: 5, flexWrap: 'wrap' }}>
                      <Clock size={11} /> {dateTime(d.updated_at)} · v{d.latest_version}
                      {d.versions.length > 1 && <span>· {d.versions.length} versions</span>}
                      {d.used_by.length > 0 && <span>· used by {d.used_by.length} journey{d.used_by.length > 1 ? 's' : ''}</span>}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <UploadSheet open={upload} onClose={() => setUpload(false)} />
      <DocSheet doc={open} onClose={() => setOpen(null)} onOpenJourney={id => { setOpen(null); push({ name: 'journey', id }) }} />
    </div>
  )
}

const FIELD_LABEL: Record<string, string> = {
  name: 'Name', dob: 'Date of birth', account_masked: 'Account', bank: 'Bank', period_label: 'Statement period', months: 'Months covered',
  issued_on: 'Issued on', salary_credits: 'Salary credits', employer: 'Employer', pay_month: 'Pay month', net_pay: 'Net pay',
  pan_masked: 'PAN', number_masked: 'Number', expiry_date: 'Valid till',
}

function DocSheet({ doc, onClose, onOpenJourney }: { doc: VaultDocument | null; onClose: () => void; onOpenJourney: (id: string) => void }) {
  const { showToast } = useApp()
  const [replace, setReplace] = useState(false)
  async function view(vid: string) {
    try { const { url } = await api.documentUrl(vid); window.open(url, '_blank', 'noopener') } catch (e) { showToast((e as Error).message) }
  }
  return (
    <>
      <Sheet open={!!doc && !replace} onClose={onClose} title={doc?.name ?? ''}>
        {doc && <>
          <div className="row" style={{ gap: 8 }}><DocStatus status={doc.status} /><span className="muted" style={{ fontSize: 12 }}>v{doc.latest_version} · {doc.source}</span></div>
          <div className="eyebrow" style={{ marginTop: 14 }}>What Saarthi read (masked)</div>
          <div className="kv" style={{ marginTop: 6 }}>
            {Object.entries(doc.versions[0]?.fields ?? {}).filter(([k]) => FIELD_LABEL[k]).map(([k, v]) => (
              <span key={k} style={{ display: 'contents' }}><span className="k">{FIELD_LABEL[k]}</span><span className="v">{k === 'net_pay' ? `₹${Number(v).toLocaleString('en-IN')}` : String(v)}</span></span>
            ))}
          </div>
          {doc.used_by.length > 0 && <>
            <div className="eyebrow" style={{ marginTop: 14 }}><Link2 size={11} /> Used by</div>
            {doc.used_by.map(u => (
              <button key={u.journey_id + u.role} className="list-row tap" style={{ width: '100%', textAlign: 'left', padding: '8px 0' }} onClick={() => onOpenJourney(u.journey_id)}>
                <div className="grow"><div className="t">{u.title}</div><div className="s">as {u.role.replace('_', ' ')} · version {doc.versions.find(v => v.id === u.version_id)?.version ?? '?'}</div></div>
              </button>
            ))}
          </>}
          <div className="eyebrow" style={{ marginTop: 14 }}><History size={11} /> Versions</div>
          {doc.versions.map(v => (
            <div key={v.id} className="between" style={{ padding: '8px 0', borderTop: '1px solid var(--line-2)' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>v{v.version} {v.version === doc.latest_version && <span className="pill pill-info" style={{ height: 18 }}>latest</span>}</div>
                <div className="muted" style={{ fontSize: 11 }}>{dateTime(v.uploaded_at)} · {v.storage}{v.size ? ` · ${(v.size / 1024).toFixed(0)} KB` : ''} · {v.status.toLowerCase()}</div>
              </div>
              {v.has_file && <button className="btn btn-ghost btn-sm" onClick={() => view(v.id)}><ExternalLink size={13} /> View</button>}
            </div>
          ))}
          {doc.source !== 'registry' && <button className="btn btn-soft btn-block" style={{ marginTop: 14 }} onClick={() => setReplace(true)}><BadgeCheck size={15} /> Upload a new version</button>}
          <div className="hint" style={{ textAlign: 'center' }}>Old versions are kept for audit. Links expire after 5 minutes.</div>
        </>}
      </Sheet>
      <UploadSheet open={replace} onClose={() => { setReplace(false); onClose() }} replaceId={doc?.id} want={doc?.doc_type} />
    </>
  )
}
