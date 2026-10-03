# Saarthi
### An AI agent that un-sticks financial journeys

**From financial *status* to financial *resolution*.**

A customer starts a SIP in an investing app. The app hands the work to a bank: verify the account, register an autopay mandate, debit each installment. Then something gets rejected, and all the customer sees is `AUTOPAY_DEBIT_FAILED_07` or "account verification failed".

Saarthi is the layer that steps in when a bank rejects anything. An AI agent (powered by **Google Gemini**) investigates with tools, a deterministic safety engine decides what's allowed, the fix runs through the bank's APIs, the bank confirms it, and the outcome is learned:

```
PERCEIVE → DIAGNOSE → DECIDE → ACT → VERIFY → LEARN
```

> **Nothing is pre-scripted.** There is no demo user and no pre-broken journey. You register, link accounts and start SIPs yourself. Failures happen only when the sandbox banks reject something because of the state you created, and the agent works from that live state.

---

## Contents
1. [Quick start](#1-quick-start)
2. [Gemini API key setup](#2-gemini-api-key-setup)
3. [The demo: failure scenarios](#3-the-demo-failure-scenarios)
4. [What's real and what's simulated](#4-whats-real-and-whats-simulated)
5. [Failure engine — all failure types](#5-failure-engine--all-failure-types)
6. [How the agent works](#6-how-the-agent-works)
7. [Safety model](#7-safety-model)
8. [Architecture & code map](#8-architecture--code-map)
9. [API](#9-api)
10. [Configuration](#10-configuration)
11. [Limitations](#11-limitations)
12. [FAQ](#12-faq)

---

## 1. Quick start

**Requirements:** Python 3.10+, Node.js 18+.

```powershell
# Windows
.\start.ps1                     # if scripts are blocked: powershell -ExecutionPolicy Bypass -File .\start.ps1
```
```bash
# macOS / Linux / Git Bash
./start.sh
```

Or run each part yourself, in two terminals:
```powershell
# Terminal 1 — Backend
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then add your GEMINI_API_KEY (see section 2)
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000 --reload

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. On a desktop browser you see the phone app next to an **engine panel** that shows the live agent trace, the 6-stage loop and the sandbox controls. Interactive API docs are at http://localhost:8000/docs.

**Reset:** use **Reset** in the engine panel, call `POST /api/demo/reset`, or delete `backend/saarthi.db`.

---

## 2. Gemini API key setup

Saarthi uses **Google Gemini** (`gemini-2.5-flash`) as its AI backbone. Without a key it still works — the deterministic planner runs all 11 failure analyzers and produces correct plans. With a key, Gemini drives the investigation, writes the explanation and handles every failure type dynamically.

### Get a free key
1. Go to **https://aistudio.google.com/app/apikey**
2. Click **Create API key**
3. Copy the key

### Add it to the project
Open `backend/.env` and fill in:

```env
DEMO_MODE=false
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
LLM_PROVIDER=gemini
```

Restart the backend. The engine panel will show a green **"Gemini agent · gemini-2.5-flash"** pill confirming it's active.

### Two modes at a glance

| Mode | When | What runs |
|---|---|---|
| **Gemini agent** | `DEMO_MODE=false` + key set | Gemini tool-use loop: chooses investigation steps, writes explanation, handles all 11 failure types |
| **Deterministic planner** | No key, or `DEMO_MODE=true` | Fixed investigative order over the same tools; picks the analyzer's recommendation. Works offline. |

Either way, tiers and actions are always deterministic — Gemini can only *propose*.

---

## 3. The demo: failure scenarios

### Setup (about 1 minute)
1. **Create account:** name, PAN, date of birth, mobile and email. Any well-formed individual PAN works (e.g. `ABCPV1234K`).
2. **KYC:** the PAN is verified automatically.
3. **Link a bank account:** pick a bank and enter an account number. Set the name the bank holds and the balance in the **Sandbox** box. A Re 1 penny drop checks the bank's name against your PAN name.

---

### Scenario A — SIP debit bounces (insufficient funds)
| Do | What happens |
|---|---|
| Link **Axis** with ₹2,000 and **HDFC** with ₹1,00,000 | Both verified by penny drop |
| Invest → any fund → **Start SIP** of ₹5,000 from Axis | Mandate registered; first debit presented today |
| | Axis returns `AUTOPAY_DEBIT_FAILED_07`. Agent starts automatically |
| Watch the trace | Reads journey → calls Axis API → looks up code → collects balance, amount, mandate evidence → checks other accounts → retrieves policies → builds options → classifies each |
| | Plan: **move exactly the ₹2,999 shortfall from HDFC and retry** (Tier 2) |
| **Approve** | HDFC IMPS transfer → balance re-checked → Axis re-presents debit → outcome verified → units allotted → learning recorded. Health 35 → 85 |

**Same failure, different plans:**
- **No account can cover the shortfall:** picks *"watch the balance & remind me"* (Tier 1, automatic, no money moves).
- **Then add money** (engine panel): agent re-plans and proposes *"retry the debit now"*.
- **Link SBI or ICICI instead:** different codes (`NACH_RTN_51`, `ECS_BOUNCE_R03`) normalize to the same failure.

---

### Scenario B — SIP raised above the autopay limit (mandate limit)
| Do | What happens |
|---|---|
| Invest → your SIP → **Amount** → ₹8,000 (limit is ₹5,000) | Saarthi warns on Home that the next debit will be refused |
| **Run next installment** (sandbox) | Bank returns `AUTOPAY_DEBIT_FAILED_12` |
| | Plan: **raise limit to ₹8,000 and retry** (Tier 2). Alternatively: *bring SIP back to ₹5,000* |
| Approve | Mandate amended → retry. If the account is now short, the bank returns a *different* code. Saarthi records the first problem as solved, opens a new incident, and the agent proposes the funding fix |

---

### Scenario C — Bank account can't be verified (name mismatch)
| Bank record name | Whose PAN the bank holds | Result |
|---|---|---|
| `R K Verma` (initials) | Mine | Match 0.73 (< 0.85) → agent proposes **Account Aggregator ownership check** (Tier 2) → bank returns your PAN → **verified** |
| `R K Verma` | Someone else | Same proposal → bank returns a **different PAN** → agent re-assesses → **Tier 3, escalate** |
| `Suresh Patel` | Someone else | Match 0.00 → **Tier 3 immediately**. Saarthi refuses to act and builds a support case |

---

### Scenario D — Document rejected (document requirement)
| Do | What happens |
|---|---|
| Start a loan/insurance application | Partner checks income documents |
| Partner rejects the bank statement (wrong period, outdated, or unreadable) | Agent diagnoses `STATEMENT_PERIOD_INSUFFICIENT` or `DOCUMENT_UNREADABLE` |
| | Facts shown: what the partner requires vs. what was submitted |
| | Options: **submit a different document** (if one in vault satisfies the rule) or **upload a new one** or **escalate** |

---

### Scenario E — Identity document doesn't match KYC (identity mismatch)
| Situation | Result |
|---|---|
| Submitted document name/DOB doesn't match PAN registry | Agent shows the mismatch, checks vault for a document that matches KYC |
| Score < 0.5 or PAN on document belongs to someone else | High-risk flag → Tier 3, no automatic action |

---

### Also try
- **Chat** (Saarthi tab → Ask): *"Why did my SIP fail?"*, *"Is my money safe?"*, *"Fix it"*, *"Show me the history"*
- **Journey tabs:** Agent trace (full tool inputs/outputs), Timeline, Graph (failure knowledge graph with equivalent codes at other banks), Audit
- **Profile → Failure knowledge:** learned outcome counts start at zero and grow as you resolve incidents
- **Demo Scenarios** button in the engine panel: one-click setup for any scenario

---

## 4. What's real and what's simulated

| Part | Status | Detail |
|---|---|---|
| Users, accounts, SIPs, journeys | 🟢 Created by you | Nothing is seeded except the fund catalog and knowledge base |
| Banks (Axis, ICICI, HDFC, SBI), Account Aggregator, PAN registry | 🟡 Sandbox simulators | Stateful and rule-enforcing: debits check mandate limit then balance; penny drop scores the name; AA returns the PAN the bank actually holds. Two API dialects (NPCI-style flat fields vs JSON envelope) and four code vocabularies |
| Failures | 🟢 Emergent | Caused only by the state you set up (balance, limit, bank-record name, document content) |
| AI agent | 🟢 Real | Gemini tool-use loop (`gemini-2.5-flash`) when API key is set; a deterministic planner calling the same tools otherwise |
| Failure analysis | 🟢 Computed | 11 failure analyzers covering every rejection type a bank or partner can return |
| Diagnosis numbers, options, confidence | 🟢 Computed | From live balances, limits, other accounts and name-match tokens |
| Safety tiers | 🟢 Deterministic | 10+ auditable checks; the LLM cannot change them |
| Actions | 🟢 Executed | IMPS transfers move balances, mandates are amended, debits are re-presented and units are allotted |
| Verification | 🟢 Executed | Bank is re-queried after every action; journey resolves only on the bank's confirmation |
| Learning | 🟢 Persisted | Per-code outcomes (resolved / failed / escalated, time to resolve) feed future confidence |
| Fund catalog | 🟡 Illustrative | Fictional fund houses, NAVs and returns |

---

## 5. Failure engine — all failure types

Saarthi's diagnosis engine handles every kind of rejection a partner can return. Each failure type has its own analyzer that computes facts, metrics, and recovery options from live data.

| Failure type | What it means | Recovery options |
|---|---|---|
| `PAYMENT_FAILURE` | SIP debit / premium bounced — insufficient funds | Retry if balance now sufficient; fund from another account + retry; remind when topped up |
| `MANDATE_LIMIT` | SIP amount exceeds the autopay limit you approved | Raise mandate limit and retry; reduce SIP to fit the limit |
| `MANDATE_INVALID` | Autopay mandate is cancelled, expired, or revoked | Register a new mandate and retry |
| `NAME_MISMATCH` | Name on bank record doesn't match your PAN / KYC name | Prove ownership via Account Aggregator; escalate to specialist |
| `DOCUMENT_REQUIREMENT` | Partner rejected a document (wrong period, outdated, unreadable, wrong type) | Submit a satisfying document from vault; upload a new document; escalate |
| `IDENTITY_MISMATCH` | Name or DOB on submitted identity doc doesn't match KYC record | Submit a different identity document from vault that matches; escalate |
| `ACCOUNT_UNVERIFIED` | Bank account not verified for this journey | Switch to a verified account; escalate |
| `TRANSIENT` | Temporary network or bank error — safe to retry | Retry automatically (up to 2 times); escalate if retries exhausted |
| `MONITOR` | Partner is still processing — no action needed yet | Keep checking with the partner; escalate if too long |
| `HUMAN_ONLY` | Risk signal or compliance issue — automation not permitted | Escalate to specialist with full context |
| `UNKNOWN` | Partner error code not in Saarthi's knowledge base | Search knowledge base; escalate — Saarthi never guesses |

**Debit inference:** when a bank returns a generic failure code with no reason, Saarthi infers the cause from evidence (balance vs. amount vs. mandate limit) before committing to a plan.

**Chained failures:** when one fix uncovers a second problem (e.g. mandate limit fixed but balance short), Saarthi records the first as solved and opens a fresh incident for the second.

---

## 6. How the agent works

When a bank rejects something, `product/journeys.open_incident()` marks the journey and starts an **agent run** in the background. Every step is written to the run's trace as it happens, and the UI polls and renders it live.

**Tools** (`backend/app/agents/agent.py`):

| Tool | What it does |
|---|---|
| `get_journey_context` | Journey, SIP, mandate, account and recent events (PAN masked) |
| `query_partner_status` | Calls the bank's status + diagnose APIs; returns the raw dialect and the normalized view |
| `lookup_failure_knowledge` | Code → standard failure, root cause, required evidence, allowed actions, equivalent codes at other banks, learned outcomes |
| `collect_evidence` | Runs collectors: balance, installment, mandate status/limit, PAN name, bank-record name, name match, document requirement, attached document, retry history, time waiting, payment amount, verified accounts |
| `list_customer_accounts` | Live balances and verification status of every linked account |
| `compare_names` | Token-level, explainable name match (score 0–1, 0.85 passes) |
| `check_document_vault` | Checks vault documents against the partner's rule — which satisfy it and why |
| `search_knowledge` | BM25 retrieval over Saarthi's knowledge base: partner rules, document requirements, retry and escalation policies |
| `build_recovery_options` | Backend computes concrete options from live data; amounts are never taken from the LLM |
| `evaluate_option` | Deterministic safety engine classifies an option into Tier 1 / 2 / 3 |
| `submit_plan` | Choose an option and write the customer-facing explanation |

**Two planners, same tools:**
- **Gemini** (when `DEMO_MODE=false` and `GEMINI_API_KEY` is set): a RAG-first tool-use loop. Gemini retrieves relevant knowledge before reasoning, decides which tools to call, which option to recommend, and writes the explanation. Every tool call carries a one-line `rationale` the user sees. Handles all 11 failure types.
- **Deterministic planner** (default, works offline): calls the tools in a fixed investigative order and picks the analyzer's recommendation. Takes over if Gemini errors mid-run, skipping steps already completed.

**Guards on the LLM:**
- It can only *propose*. Tiers come from `decision.py`; execution only through `actions.py`.
- Option parameters (amounts, accounts, limits) are computed server-side.
- Every number in Gemini's explanation must appear in verified data or the trace, otherwise the template text is shown instead (`explanation.grounding_check`).
- If a run ends without a submitted plan, the remaining steps are filled in deterministically.
- On API overload (429/503), the LLM layer retries with exponential backoff (4s, 8s) before falling back to the deterministic planner.

---

## 7. Safety model

```
TIER_1  Auto            reversible, no money moved, no data shared, every check passes
TIER_2  Your approval   every check passes, but it moves money, shares data or changes SIP/mandate terms
TIER_3  Escalate        any blocking check fails, or the action edits identity or can't be undone
```

Blocking checks: partner status identified · failure mapped · rule retrieved · required evidence verified · root cause confirmed · customer KYC verified · no risk signal · **confidence ≥ 75%** · action reversible · for transfers: source account can cover the amount.

The partner policy for each failure code sets a **minimum tier** for impactful actions — Saarthi can be stricter but never looser. The server refuses to run Tier 3, and runs Tier 2 only with a recorded approval, whatever the UI sends.

**Confidence** = 0.5 × evidence coverage + 0.3 × root cause confirmed + 0.2 × learned success rate for this code (0.5 before any history).

**Health score** = 50 ± explainable rule factors (failure, shortfall, over-limit, unverified account, recovery available, KYC, predictive warnings such as "next installment not covered").

---

## 8. Architecture & code map

```
 React app ─ onboarding · Home · Invest (funds, SIPs) · Banks · Saarthi · Loans · Chat
     │  /api/* (X-User-Id header)
 FastAPI
 ├─ product/        the fintech app: users+KYC, bank linking (penny drop), SIPs, mandates, installments
 │     └─ journeys.open_incident() ──► orchestrator.start_agent()   (background thread)
 ├─ agents/
 │   ├─ agent.py         Gemini tool-use loop or deterministic planner, live trace
 │   ├─ context.py       journey context from the system of record
 │   ├─ evidence.py      evidence collectors (each states its source)
 │   ├─ diagnosis.py     perceive / knowledge / 11 analyzers per failure type / confidence
 │   ├─ decision.py      deterministic tiers + partner-policy floor
 │   ├─ catalog.py       action safety properties (moves_money, shares_data, changes_terms, ...)
 │   ├─ actions.py       plans executed via partner connectors, then verified
 │   ├─ orchestrator.py  loop, approvals, follow-up incidents, escalation, read models
 │   ├─ health.py · learning.py · graph.py · chat.py · explanation.py
 │   ├─ llm.py           Gemini client with retry/backoff on overload
 │   └─ prompts.py       system prompts covering all 11 failure types
 ├─ partners/
 │   ├─ simulators.py    sandbox banks (2 dialects, 4 code sets), Account Aggregator, PAN registry
 │   └─ connectors.py    normalization layer + raw request/response log
 ├─ knowledge/           failure codes (4 banks × 3 failures) + policies, BM25 retrieval
 ├─ services/            name matcher, journal (timeline + audit), INR formatting
 └─ database/            SQLite schema; seed.py loads reference data only
```

Frontend highlights: `pages/Onboarding.tsx` · `components/LinkBankForm.tsx` · `pages/FundDetail.tsx` (start SIP) · `pages/Invest.tsx` (SIP controls) · `features/journey/AgentTrace.tsx` (live trace) · `features/journey/JourneyScreen.tsx` · `features/journey/DiagnosisTab.tsx` · `pages/EnginePanel.tsx` · `pages/Chat.tsx`

---

## 9. API

Full interactive docs: http://localhost:8000/docs. Every user-scoped call sends `X-User-Id`.

| Area | Endpoints |
|---|---|
| Onboarding | `POST /api/users/register` · `GET /api/users` · `GET /api/me` |
| Banking | `GET/POST /api/accounts` · `POST /api/accounts/{id}/balance` (sandbox) |
| Investing | `GET /api/funds` · `GET /api/funds/{id}` · `GET/POST /api/sips` · `POST /api/sips/{id}/run` · `PATCH /api/sips/{id}` |
| Journeys | `GET /api/journeys` · `GET /api/journeys/{id}` · `GET /api/journeys/{id}/agent` · `POST …/diagnose` · `POST …/decide` · `POST …/recover` · `POST …/approve` · `POST …/escalate` |
| Saarthi | `GET /api/overview` · `POST /api/chat` · `GET /api/audit` · `GET /api/system` · `POST /api/demo/reset` |
| Knowledge | `GET /api/knowledge` · `GET /api/knowledge/search?q=` |
| Financial planner | `GET /api/planner/overview` · `POST /api/planner/profile` · `GET/POST /api/planner/goals` · `PUT/DELETE /api/planner/goals/{id}` · `POST /api/planner/affordability` · `POST /api/planner/what-if` · `POST /api/planner/stress-test` · `POST /api/planner/debt/extra-payment` · `POST /api/planner/chat` · `GET /api/planner/changelog` · `POST /api/planner/demo/scenario/{1-7}` |
| Partner sandbox | `GET /partner/{pid}/journey/{ref}` · `POST /partner/{pid}/diagnose` · `POST /partner/{pid}/retry` · `POST /partner/{pid}/update-status` |

---

## 10. Configuration

`backend/.env`:

| Variable | Default | Meaning |
|---|---|---|
| `DEMO_MODE` | `true` if unset (`.env.example` sets `false`) | `true` forces the deterministic planner (offline, no key needed) |
| `GEMINI_API_KEY` | empty | Required for the Gemini agent. Get one at https://aistudio.google.com/app/apikey |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model for the agent, explanations and chat |
| `LLM_PROVIDER` | `gemini` | Always `gemini` |
| `SAARTHI_DATA_DIR` | `backend/` | Writable state: SQLite DB, `uploads/`, signing secret. Mount a volume here in production |
| `SAARTHI_DB` | `$SAARTHI_DATA_DIR/saarthi.db` | SQLite path |
| `SAARTHI_STORAGE_SECRET` | generated into the data dir | HMAC secret for signed document URLs. Set it explicitly in production |
| `SAARTHI_FRONTEND_DIST` | `frontend/dist` | Built web app. When it exists the backend serves it at `/` |
| `CORS_ORIGINS` | `*` | Comma-separated origins, only needed when the frontend is hosted on another domain |
| `CLOUDINARY_URL` | empty | Store documents in Cloudinary instead of local disk (`pip install cloudinary`) |

Variables already set in the environment take precedence over `backend/.env`.

The engine panel shows which planner is active. Any Gemini error (including API overload) falls back to the deterministic planner mid-run without losing completed steps.

### Deploying

The repo ships a `Dockerfile` that builds the frontend and serves it together with the API from one container, so there is a single URL and no CORS setup:

```bash
docker build -t saarthi .
docker run -p 8000:8000 -v saarthi-data:/data \
  -e DEMO_MODE=false -e GEMINI_API_KEY=your_key -e SAARTHI_STORAGE_SECRET=$(openssl rand -hex 32) \
  saarthi
# open http://localhost:8000
```

This works on any Docker host (Render, Railway, Fly.io, Cloud Run, a VM). The container listens on `$PORT` (default 8000), exposes `/api/health` for health checks, and keeps all state in `/data`. Attach a persistent volume there, or the database and uploaded documents reset on every deploy. Run a single instance: the app uses SQLite and runs agent work in-process.

Without Docker: `cd frontend && npm ci && npm run build`, then `cd backend && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000`.

---

## 11. Limitations

- **Sandbox banks only.** No real money, banks or personal data. Fund houses are fictional.
- **No real authentication.** The sandbox identifies the user with an `X-User-Id` header.
- **Chat routing is keyword-based.** Gemini only phrases the answers when enabled.
- **Not affiliated** with Paytm, Google or any bank, and it doesn't reproduce their UI.
- **Gemini free tier** has rate limits. If you see overload errors, wait a moment — the backend will retry automatically and fall back to the deterministic planner if needed.

---

## 12. FAQ

- **Is it hardcoded?** No. Every journey comes from a user action, every failure from sandbox state, and every plan from live data. Change the balance, the limit or the bank-record name and the diagnosis and plan change with it.
- **Where's the AI?** Gemini drives the investigation: it picks which tools to call, interprets results, recommends a plan and writes the explanation — on top of a RAG retrieval step and a failure knowledge graph. Deterministic rules keep money safe.
- **What if the AI is wrong?** It can't move money or pick amounts. Tiers are deterministic, execution goes through guarded server code, every outcome is verified with the bank, and explanations are grounding-checked against verified numbers.
- **Which failure types does it handle?** All 11: payment failure, mandate limit, mandate invalid, name mismatch, document rejection, identity mismatch, account unverified, transient error, monitoring state, human-only cases, and unknown codes.
- **Can it act?** Yes: IMPS transfers, mandate amendments, debit re-presentation and Account Aggregator consent fetches. Each shows the raw bank response.
- **When does it refuse?** When ownership can't be proven, confidence is below 75%, or any blocking check fails. It then builds a structured case for a human specialist.
- **Different banks?** Four banks, two API dialects and twelve codes, normalized to standard failure types.
- **How does it learn?** Each incident outcome is recorded per bank code, starting from zero, and the success rate feeds the next diagnosis's confidence score.
- **What if I don't have a Gemini key?** The deterministic planner runs all 11 analyzers and produces correct plans. Add the key at any time and restart the backend to upgrade to AI mode.

**Tech stack:** React 18 · Vite · TypeScript · Framer Motion · FastAPI · SQLite · Google Gemini SDK (`google-genai`) · BM25 in pure Python
