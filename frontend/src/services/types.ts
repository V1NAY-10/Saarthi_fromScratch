export type Tier = 'TIER_1' | 'TIER_2' | 'TIER_3'
export type JourneyStatus = 'ATTENTION' | 'RESOLVED' | 'ESCALATED' | 'ON_TRACK' | 'COMPLETE'

export interface Band { key: 'healthy' | 'watch' | 'risk' | 'critical'; label: string }

export interface Profile {
  id: string; name: string; phone: string; email: string; dob: string; pan_masked: string; kyc_status: string; created_at: string
}

export interface Account {
  id: string; user_id: string; partner_id: string; bank: string; masked: string; ifsc: string; holder_name: string
  balance: number; status: 'VERIFYING' | 'VERIFIED' | 'UNVERIFIED'; bank_name_on_record: string | null
  name_match: number | null; journey_id: string | null; created_at: string
}

export interface Fund {
  id: string; name: string; amc: string; category: string; risk: string; nav: number
  returns_1y: number; returns_3y: number; returns_5y: number; min_sip: number; expense_ratio: number; aum_cr: number
}

export interface Mandate { id: string; account_id: string; umrn: string; max_amount: number; status: string }

export interface Sip {
  id: string; fund_id: string; amount: number; sip_day: number; account_id: string; mandate_id: string; status: string
  journey_id: string; installments_paid: number; units: number; invested: number; next_due: string; created_at: string
  fund: Fund; mandate: Mandate; account: { id: string; bank: string; masked: string; balance: number }
  current_value: number; journey_status: JourneyStatus
}

export interface SipStartResult {
  sip: Sip; journey_id: string
  installment: { status: 'SUCCESS' | 'FAILED'; journey_id: string; code?: string; message?: string; transaction?: { units: number; nav: number; bank_ref: string } }
}

export interface Journey {
  id: string
  category: 'investment' | 'bank_account' | 'loan' | 'insurance' | 'kyc'
  title: string
  subtitle: string
  partner_id: string
  partner_name: string
  partner_ref: string
  amount: number
  status: JourneyStatus
  stage: string
  state: Record<string, any>
  health_score: number
  band?: Band
  agent_status?: 'RUNNING' | 'DONE' | 'FAILED' | null
  created_at: string
  updated_at: string
  saarthi?: { headline: string; summary: string; tier: Tier | null; partner_code: string; meaning: string; failure_type: string }
}

export interface HealthFactor { key: string; label: string; impact: number; detail: string }
export interface Health { score: number; base: number; band: Band; factors: HealthFactor[] }

export interface Evidence {
  key: string; label: string; value: any; display: string; source: string; verified: boolean; note?: string | null
}
export interface Fact { label: string; value: string; source: string; emphasis?: boolean }
export interface Check { id: string; label: string; passed: boolean; detail: string; blocking?: boolean }

export interface RecoveryOption {
  id: string; action_type: string; title: string; description: string; params: Record<string, any>
  recommended: boolean
  effects: { moves_money: boolean; shares_data: boolean; reversible: boolean; changes_identity: boolean; changes_terms: boolean; label: string }
}

export interface Decision {
  id?: string; option_id: string; action_type: string; tier: Tier; tier_label: string
  checks: Check[]; reasons: string[]; confidence: number
}

export interface KnowledgeHit { id: string; kind: string; title: string; body: string; score: number; engine?: 'cognee' | 'bm25'; source?: string }

export interface Lesson {
  partner: string; partner_code: string; failure_type: string; diagnosis: string; action: string; outcome: string
  resolution_seconds: number
  before: { occurrences: number; resolved: number; success_rate: number | null; avg_resolution_s: number }
  after: { occurrences: number; resolved: number; success_rate: number; avg_resolution_s: number }
}

export interface NameMatch { score: number; verdict: 'match' | 'partial' | 'different'; reasons: string[]; pairs: { token: string; matched: string | null; kind: string }[] }

export interface Diagnosis {
  journey_id: string
  status: 'DIAGNOSED' | 'UNMAPPED'
  partner: { partner_id: string; partner_name: string; state: string; raw_code: string; raw_message: string }
  partner_raw: Record<string, any>
  partner_diagnose_raw?: Record<string, any>
  partner_endpoints?: string[]
  normalized: {
    partner_code: string; failure_type: string; standard_code: string; meaning: string; root_cause: string
    evidence_required: string[]; retry_allowed: boolean; policy_tier: Tier; expected_outcome: string
    analyzer?: string | null; risk_level?: string; possible_causes?: string[]; escalation_conditions?: string[]
    equivalents: { partner_id: string; code: string }[]
  }
  kb_entry: { id: string; title: string; body: string; source?: string; data: Record<string, any> } | null
  evidence: Evidence[]
  facts: Fact[]
  metrics: Record<string, any>
  name_match?: NameMatch | null
  risk_signal: boolean
  root_cause_confirmed: boolean
  missing: string[]
  options: RecoveryOption[]
  confidence: number
  learned: { occurrences: number; resolved: number; success_rate: number; avg_resolution_s: number } | null
  knowledge: KnowledgeHit[]
  steps: Check[]
  headline: string; summary: string; safety_note: string
  explanation: { headline: string; summary: string; safety_note: string; source: 'llm' | 'deterministic'; grounding: { passed: boolean; numbers_checked: number; unsupported: string[] }; llm_rejected?: boolean }
  decisions: { by_option: Record<string, Decision>; primary_option_id: string | null; primary: Decision | null }
  agent?: { run_id: string; mode: string; chosen_by: 'claude' | 'planner' }
  unknown?: boolean
  document_evidence?: DocumentEvidence | null
  pending_action_id?: string
  lesson?: Lesson
  health_transition?: { before: number; after: number }
}

export interface TraceStep {
  type: 'thought' | 'tool'; ts: string; text?: string
  tool?: string; rationale?: string; input?: Record<string, any>; summary?: string; ok?: boolean; data?: any
}

export interface AgentRun {
  id: string; journey_id: string; status: 'RUNNING' | 'DONE' | 'FAILED'; mode: string; model: string | null
  trace: TraceStep[]; error: string | null; started_at: string; finished_at: string | null
}

export interface TimelineEvent {
  id: number; journey_id: string; ts: string; kind: string; title: string; detail: string
  status: 'done' | 'failed' | 'info' | 'waiting'; actor: string; loop_stage: string; meta: Record<string, any>
}

export interface AuditEntry { id: number; ts: string; journey_id: string | null; actor: string; event_type: string; summary: string; data: Record<string, any> }

export interface ActionStep {
  label: string; ok: boolean; detail: string; ts: string; endpoint: string | null
  partner_raw: Record<string, any> | null; partner_normalized: Record<string, any> | null
}

export interface Action {
  id: string; journey_id: string; action_type: string; tier: Tier; status: string
  params: Record<string, any>
  result: { steps?: ActionStep[]; verification?: { endpoint: string; expected: string; observed: string; passed: boolean } | null; ok?: boolean }
  created_at: string; completed_at: string | null
}

export interface GraphNode { id: string; kind: string; label: string; sub?: string | null; state: string }
export interface GraphData { nodes: GraphNode[]; edges: { from: string; to: string; label: string }[] }

export interface DocVersion {
  id: string; version: number; status: string; uploaded_at: string; mime_type: string | null; size: number
  original_name: string | null; storage: string; fields: Record<string, any>; checks: Record<string, any>; has_file: boolean
}

export interface VaultDocument {
  id: string; doc_type: string; name: string; status: string; source: string; updated_at: string
  meta: Record<string, any>; latest_version: number; latest_version_id: string; expiry_date: string | null
  versions: DocVersion[]; used_by: { journey_id: string; role: string; version_id: string; title: string }[]
  duplicate?: boolean
}

export interface Candidate {
  document_id: string; version_id: string; version: number; name: string; summary: string; ok: boolean
  issues: string[]; already_submitted?: boolean; evidence?: { required: string; found: string }[]
}

export interface ChecklistItem { doc_type: string; role: string; label: string; requirement: string; candidates: Candidate[] }
export interface Precheck { journey_id: string; checklist: ChecklistItem[]; saarthi_note: string; problems: string[]; missing: string[] }

export interface PartnerOffer {
  partner_id: string; name: string; product: string; tagline?: string; rate?: number; max_amount?: number
  min_income?: number; plan?: string; cover?: number; premium_per_year?: number
  requirements: { doc_type: string; label: string }[]
}

export interface Scenario { id: string; title: string; family: string; what: string }

export interface DocumentEvidence {
  doc_type: string; doc_label: string; required: string; found: string; rule?: string
  submitted: { name: string; version: number; summary: string } | null; candidates: Candidate[]
}

export interface SupportCase { id: string; journey_id: string; created_at: string; priority: string; status: string; payload: Record<string, any> }

export interface LoopStage { stage: string; state: 'done' | 'current' | 'pending' | 'idle' }

export interface JourneyView {
  journey: Journey
  health: Health
  diagnosis: Diagnosis | null
  agent_run: AgentRun | null
  graph: GraphData | null
  timeline: TimelineEvent[]
  loop: LoopStage[]
  actions: Action[]
  documents: VaultDocument[]
  linked_account: Account | null
  sip: Sip | null
  mandate: Mandate | null
  fund: Fund | null
  support_case: SupportCase | null
  audit: AuditEntry[]
  action_result?: Action
}

export interface Overview {
  user: Profile
  accounts: Account[]
  cash: number; invested: number; portfolio_value: number; net_worth: number
  sips: Sip[]
  obligations: { title: string; amount: number; due: string; status: string; journey_id: string; sip_id: string }[]
  journeys: Journey[]
  attention: Journey[]
  overall_health: number
  intelligence: AuditEntry[]
  insights: { tone: 'ok' | 'warn' | 'info'; text: string; journey_id?: string }[]
  system: SystemInfo
}

export interface ChatCard {
  type: 'approval' | 'journey' | 'decision' | 'health' | 'escalate'
  journey_id: string; action_id?: string; title?: string; tier?: Tier; checks?: string[]
  reasons?: string[]; status?: string; score?: number
}
export interface ChatReply { journey_id?: string; intent: string; messages: string[]; cards: ChatCard[] }

export interface KnowledgeEntry {
  id: string; kind: string; partner_id: string | null; code: string | null; title: string; body: string
  data: Record<string, any>
  learned?: { occurrences: number; resolved: number; success_rate: number; avg_resolution_s: number; last_outcome: string | null }
}

export interface SystemInfo {
  demo_mode: boolean; llm_enabled: boolean; model: string; agent_mode: 'claude' | 'deterministic'
  knowledge?: { active_engine: 'cognee' | 'bm25'; cognee_state: string; reason: string; sections: number; failure_codes: number }
  storage?: { backend: string; cloudinary_configured: boolean }
}
