import type {
  Account, AuditEntry, ChatReply, Decision, Fund, Journey, JourneyView, KnowledgeEntry, Overview, PartnerOffer, Precheck,
  Profile, Scenario, Sip, SipStartResult, SystemInfo, VaultDocument,
} from './types'

let userId: string | null = null
export function setApiUser(id: string | null) { userId = id }

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(userId ? { 'X-User-Id': userId } : {}), ...(init?.headers || {}) },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map((d: any) => d.msg).join(', ') : detail
    } catch { /* ignore */ }
    const err = new Error(detail) as Error & { status?: number }
    err.status = res.status
    throw err
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body: unknown = {}) => req<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  // onboarding
  register: (b: { name: string; phone: string; email: string; dob: string; pan: string }) => post<Profile>('/api/users/register', b),
  profiles: () => req<Profile[]>('/api/users'),
  me: () => req<Profile>('/api/me'),
  // banking
  accounts: () => req<Account[]>('/api/accounts'),
  linkAccount: (b: { bank: string; account_no: string; holder_name: string; opening_balance: number; owner: 'self' | 'other' }) => post<Account>('/api/accounts', b),
  adjustBalance: (id: string, delta: number) => post<Account>(`/api/accounts/${id}/balance`, { delta }),
  // investing
  funds: () => req<Fund[]>('/api/funds'),
  fund: (id: string) => req<Fund>(`/api/funds/${id}`),
  sips: () => req<Sip[]>('/api/sips'),
  startSip: (b: { fund_id: string; amount: number; sip_day: number; account_id: string; mandate_limit: number }) => post<SipStartResult>('/api/sips', b),
  runInstallment: (id: string) => post<SipStartResult['installment']>(`/api/sips/${id}/run`),
  updateSip: (id: string, amount: number) => req<Sip>(`/api/sips/${id}`, { method: 'PATCH', body: JSON.stringify({ amount }) }),
  // saarthi
  overview: () => req<Overview>('/api/overview'),
  journeys: () => req<Journey[]>('/api/journeys'),
  journey: (id: string) => req<JourneyView>(`/api/journeys/${id}`),
  diagnose: (id: string) => post<JourneyView>(`/api/journeys/${id}/diagnose`),
  decide: (id: string, option_id?: string) => post<Decision>(`/api/journeys/${id}/decide`, { option_id }),
  recover: (id: string, option_id?: string) =>
    post<{ outcome: string; decision: Decision; action: { id: string }; view: JourneyView }>(`/api/journeys/${id}/recover`, { option_id }),
  approve: (id: string, action_id: string) => post<JourneyView>(`/api/journeys/${id}/approve`, { action_id }),
  escalate: (id: string) => post<JourneyView>(`/api/journeys/${id}/escalate`),
  documents: () => req<VaultDocument[]>('/api/documents'),
  knowledge: () => req<KnowledgeEntry[]>('/api/knowledge'),
  audit: (limit = 40) => req<AuditEntry[]>(`/api/audit?limit=${limit}`),
  chat: (message: string, journey_id?: string) => post<ChatReply>('/api/chat', { message, journey_id }),
  system: () => req<SystemInfo>('/api/system'),
  // vault
  uploadDocument: async (file: Blob, filename: string, docType?: string, replaceId?: string) => {
    const fd = new FormData()
    fd.append('file', file, filename)
    if (docType) fd.append('doc_type', docType)
    if (replaceId) fd.append('replace_document_id', replaceId)
    const res = await fetch('/api/documents', { method: 'POST', body: fd, headers: userId ? { 'X-User-Id': userId } : {} })
    if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d } catch { /* ignore */ } throw new Error(d) }
    return res.json() as Promise<VaultDocument>
  },
  documentUrl: (versionId: string) => req<{ url: string }>(`/api/documents/versions/${versionId}/url`),
  sampleBlob: async (kind: string) => {
    const res = await fetch(`/api/samples/${kind}`, { headers: userId ? { 'X-User-Id': userId } : {} })
    if (!res.ok) throw new Error('Could not generate sample')
    const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? `${kind}.pdf`
    return { blob: await res.blob(), name }
  },
  samples: () => req<{ kind: string; label: string }[]>('/api/samples'),
  // applications
  catalog: (kind: string) => req<PartnerOffer[]>(`/api/applications/catalog/${kind}`),
  startApplication: (b: { partner_id: string; amount?: number; tenure_months?: number; monthly_income?: number; account_id?: string }) =>
    post<Precheck>('/api/applications', b),
  precheck: (jid: string) => req<Precheck>(`/api/applications/${jid}/precheck`),
  submitApplication: (jid: string, selections: Record<string, string>) =>
    post<{ status: string; journey_id: string; code?: string }>(`/api/applications/${jid}/submit`, { selections }),
  // demo
  scenarios: () => req<Scenario[]>('/api/demo/scenarios'),
  runScenario: (id: string) => post<{ journey_id: string }>(`/api/demo/scenarios/${id}`),
  reset: () => post<{ ok: boolean }>('/api/demo/reset'),
}
