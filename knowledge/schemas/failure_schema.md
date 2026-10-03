# Failure knowledge schema

> **Synthetic sandbox knowledge.** Field names describe Saarthi's own sandbox model.

Every partner error code is one `##` section in a partner file. The section has customer-readable prose (what RAG retrieves) and one fenced `yaml` block (what the deterministic registry loads). Sections whose YAML has `profile: true` describe a partner's document requirements instead of an error code.

## Fields

| Field | Meaning |
|---|---|
| `partner` / `partner_name` | Sandbox partner id and display name |
| `journey_type` | `investment`, `bank_account`, `loan`, `insurance`, `kyc` |
| `product` | Product the code appears in |
| `error_code` | The partner's own code, exactly as returned |
| `failure_type` | Saarthi's normalized failure, shared across partners |
| `standard_code` | Dotted normalized code, e.g. `PAY.INSUFFICIENT_FUNDS` |
| `analyzer` | Which generic analyzer interprets the evidence |
| `customer_meaning` | Plain-language meaning |
| `possible_causes` | Candidate root causes |
| `evidence_required` | Evidence collectors Saarthi must run |
| `relevant_documents` | Document types involved |
| `requirement` | Machine-checkable document rule (optional) |
| `resolution_options` | Allowed recovery actions |
| `automatic_action_allowed` | Whether Tier 1 is possible at all |
| `approval_required` | Whether the customer must approve |
| `risk_level` | `low`, `medium`, `high` |
| `reversible` | Whether the resolution can be undone |
| `escalation_conditions` | When to hand over to a human |
| `expected_outcome` | What success looks like |
| `retry_allowed` | Whether the partner allows a retry |
| `action_tier` | Partner-policy minimum tier for impactful actions |

## Analyzers

| Analyzer | Used for |
|---|---|
| `insufficient_funds` | Debit returned for low balance |
| `mandate_limit` | Debit above the mandate maximum |
| `mandate_invalid` | Mandate expired or cancelled |
| `debit_inference` | Generic debit failure; infers the cause from evidence or escalates |
| `name_mismatch` | Bank account name vs PAN |
| `document_requirement` | Any document rule: period, recency, readability, type, presence, income, salary credits |
| `identity_mismatch` | Name / date of birth / PAN on a submitted document vs KYC |
| `transient` | Outages, timeouts, temporary unavailability (Tier 1 retry) |
| `monitor` | Pending / delayed / under review (Tier 1 refresh, escalate after SLA) |
| `payment_retry` | Premium or one-off payment failures |
| `account_unverified` | Payout or payment account not verified |
| `human_only` | Rejections, other-person identity, duplicates (always Tier 3) |

Adding a failure type normally means adding one section with an existing analyzer. A new analyzer is only needed for genuinely new logic.
