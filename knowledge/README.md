# Saarthi knowledge base

Synthetic partner knowledge for the Saarthi sandbox. **Nothing here is a real bank, lender, insurer or registry policy.** Real bank names (Axis, ICICI, HDFC, SBI) appear only as labels for sandbox simulators; their codes and rules are invented.

```
knowledge/
  banks/        sandbox bank error codes (SIP autopay, mandates, account verification)
  loans/        sandbox lenders: document requirements + application error codes
  insurance/    sandbox insurer: identity/medical requirements + error codes
  kyc/          sandbox KYC registry error codes
  investments/  cross-cutting Saarthi policies (money movement, tiers, identity, escalation)
  schemas/      the failure knowledge schema
```

How it is used:

1. **Registry (deterministic):** on startup the backend parses every fenced `yaml` block. Error-code entries become the failure registry (exact partner + code lookup); `profile: true` blocks become partner document requirements used by both the sandbox partner and Saarthi's checks.
2. **RAG (semantic):** every `##` section is a retrievable chunk. With Cognee installed, chunks are ingested with `cognee.remember()` and retrieved with `cognee.recall()`. Otherwise a BM25 index over the same chunks is used, and the app says so.

To add a failure: add a `##` section with prose and a `yaml` block following `schemas/failure_schema.md`, then restart the backend (or call `POST /api/knowledge/reingest`).
