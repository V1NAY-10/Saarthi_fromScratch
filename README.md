# Saarthi
### An AI agent that un-sticks financial journeys

**From financial *status* to financial *resolution*.**

A customer starts a SIP in an investing app. The app hands the work to a bank: verify the account, register an autopay mandate, debit each installment. Then something gets rejected, and all the customer sees is `AUTOPAY_DEBIT_FAILED_07` or "account verification failed".

Saarthi is the layer that steps in when a bank rejects something. An agent investigates with tools, a deterministic safety engine decides what's allowed, the fix runs through the bank's APIs, the bank confirms it, and the outcome is learned:

```
PERCEIVE → DIAGNOSE → DECIDE → ACT → VERIFY → LEARN
```

> **Nothing is pre-scripted.** There is no demo user and no pre-broken journey. You register, link accounts and start SIPs yourself. Failures happen only when the sandbox banks reject something because of the state you created, and the agent works from that live state.

---

## Contents
1. [Quick start](#1-quick-start)
2. [The demo: three ways a SIP gets stuck](#2-the-demo-three-ways-a-sip-gets-stuck)
3. [What's real and what's simulated](#3-whats-real-and-whats-simulated)
4. [How the agent works](#4-how-the-agent-works)
5. [Safety model](#5-safety-model)
6. [Architecture & code map](#6-architecture--code-map)
7. [API](#7-api)
8. [Configuration](#8-configuration)
9. [Limitations](#9-limitations)
10. [FAQ for judges](#10-faq-for-judges)

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
cd backend
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt     # mac/linux: .venv/bin/pip
copy .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000

cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. On a desktop browser you see the phone app next to an **engine panel** that shows the live agent trace, the loop and the sandbox controls. Interactive API docs are at http://localhost:8000/docs.

> **Upgrading from the old seeded demo?** Restart the backend. On startup it detects the old database and replaces it with an empty sandbox. If the browser shows "Not Found" when you create an account, an old backend process is still running on port 8000.

**Reset:** use **Reset** in the engine panel, call `POST /api/demo/reset`, or delete `backend/saarthi.db`.

**Running against another backend port:** `SAARTHI_API=http://127.0.0.1:8010 npm run dev`.

---

## 2. The demo: three ways a SIP gets stuck

### Setup (about 1 minute)
1. **Create account:** name, PAN, date of birth, mobile and email. The sandbox PAN registry accepts any well-formed individual PAN (e.g. `ABCPV1234K`).
2. **KYC:** the PAN is verified and saved to your document vault.
3. **Link a bank account:** pick a bank and enter an account number. The dashed **Sandbox** box holds what the *bank* knows: the account-holder name on its record, whose PAN it has on file, and the balance. A Re 1 penny drop checks the bank's name against your PAN name.

### Scenario A: the debit bounces (insufficient funds)
| Do | What happens |
|---|---|
| Link **Axis** with ₹2,000, and **HDFC** with ₹1,00,000 | Both verified by penny drop |
| Invest → any fund → **Start SIP** of ₹5,000 from Axis | Mandate registered; the first debit is presented today |
| | Axis returns `AUTOPAY_DEBIT_FAILED_07`. The agent starts automatically |
| Watch the trace | It reads the journey, calls Axis's API, looks up the code, collects balance, amount and mandate evidence, checks your other accounts, retrieves policies, builds options and has each one classified |
| | Plan: **move exactly the ₹2,999 shortfall from HDFC and retry** → Tier 2 (moves money) |
| **Review & approve** | HDFC IMPS transfer → balance re-checked → Axis re-presents the debit → outcome verified with Axis → units allotted → learning recorded. Health 35 → 85 |

**Same failure, different plans:**
- **No account can cover the shortfall:** the agent picks *"watch the balance & remind me"* (Tier 1, runs automatically, no money moves).
- **Then add money** (Banks tab or engine panel): the agent re-plans on its own and proposes *"retry the debit now"*.
- **Link an SBI or ICICI account instead:** different bank codes (`NACH_RTN_51`, `ECS_BOUNCE_R03`) normalize to the same failure.

### Scenario B: SIP raised above the autopay limit
| Do | What happens |
|---|---|
| Invest → your SIP → **Amount** → ₹8,000 (limit is ₹5,000) | Saved. Saarthi warns on Home that the next debit will be refused |
| **Run next installment** (sandbox fast-forward) | Bank returns its mandate-limit code (`AUTOPAY_DEBIT_FAILED_12` at Axis) |
| | Plan: **raise the limit to ₹8,000 and retry** (Tier 2). The alternative, *bring the SIP back to ₹5,000*, is also offered |
| Approve | Mandate amended → retry. If the account is now short, the bank returns a *different* code; Saarthi records the first problem as solved, opens a new incident and the agent proposes the funding fix. Two chained failures, each handled from live state |

### Scenario C: bank account can't be verified (name mismatch)
| Bank record name | Whose PAN the bank holds | Result |
|---|---|---|
| `R K Verma` (initials) | Mine | Match 0.73 (< 0.85) → agent proposes an **Account Aggregator ownership check** (Tier 2, shares data) → the bank returns your PAN → **verified** |
| `R K Verma` | Someone else | Same proposal → the bank returns a **different PAN** → the agent re-assesses → **Tier 3, escalate** (SEBI bars third-party payments) |
| `Suresh Patel` | Someone else | Match 0.00 → **Tier 3 immediately**. Saarthi refuses to act and builds a support case |

The agent can't see whose PAN the bank holds. It only finds out by asking the bank via Account Aggregator, with your consent. That's why the same name can lead to two different outcomes.

### Also try
- **Chat** (Saarthi tab → Ask): "Why did my SIP fail?" or "Fix it". Fix returns an approval card and never acts directly.
- **Journey tabs:** Agent (full trace with tool inputs and outputs), Timeline, Graph (failure knowledge graph with equivalent codes at other banks) and Audit.
- **Profile → Failure knowledge:** the learned outcome counts start at zero and grow as you resolve incidents.

---

## 3. What's real and what's simulated

| Part | Status | Detail |
|---|---|---|
| Users, accounts, SIPs, journeys | 🟢 Created by you | Nothing is seeded except the fund catalog and the knowledge base |
| Banks (Axis, ICICI, HDFC, SBI), Account Aggregator, PAN registry | 🟡 Sandbox simulators | Stateful and rule-enforcing: debits check the mandate limit, then the balance; penny drop scores the name; AA returns the PAN the bank actually holds. Two wire dialects (NPCI-style flat fields vs JSON envelope) and four code vocabularies |
| Failures | 🟢 Emergent | Caused only by the state you set up (balance, limit, bank-record name) |
| Agent | 🟢 Real | Claude tool-use loop (`claude-opus-5-5` by default) when an API key is set; a deterministic planner calling the same tools otherwise |
| Diagnosis numbers, options, confidence | 🟢 Computed | From live balances, limits, other accounts and name-match tokens |
| Safety tiers | 🟢 Deterministic | 10+ auditable checks; the LLM cannot change them |
| Actions | 🟢 Executed | IMPS transfers move balances, mandates are amended, debits are re-presented and units are allotted |
| Verification | 🟢 Executed | The bank is re-queried after every action; the journey resolves only on the bank's confirmation |
| Learning | 🟢 Persisted | Per-code outcomes (resolved / failed / escalated, time to resolve) feed future confidence |
| Fund catalog | 🟡 Illustrative | Fictional fund houses, NAVs and returns |

**Sandbox controls** (clearly labelled in the UI) stand in for things that happen at the bank, outside the app: the name on the bank's record, whose PAN is on the account, balances, and "run next installment" to skip ahead to the debit date.

---

## 4. How the agent works

When a bank rejects something, `product/journeys.open_incident()` marks the journey and starts an **agent run** in the background. Every step is written to the run's trace as it happens, and the UI polls and renders it live.

**Tools** (`backend/app/agents/agent.py`):

| Tool | What it does |
|---|---|
| `get_journey_context` | Journey, SIP, mandate, account and recent events (PAN masked) |
| `query_partner_status` | Calls the bank's status + diagnose APIs; returns the raw dialect and the normalized view |
| `lookup_failure_knowledge` | Code → standard failure, root cause, required evidence, allowed actions, equivalent codes, learned outcomes |
| `collect_evidence` | Runs collectors (balance, installment, mandate status/limit, PAN name, bank-record name, name match) |
| `list_customer_accounts` | Live balances and verification status of every linked account |
| `compare_names` | Token-level, explainable name match |
| `search_policies` | BM25 over policies (money movement, retries, third-party payments, AA consent, etc.) |
| `build_recovery_options` | The backend computes concrete options from live data; amounts are never taken from the LLM |
| `evaluate_option` | The deterministic safety engine classifies an option into a tier |
| `submit_plan` | Choose an option and write the customer explanation |

**Two planners, same tools:**
- **Claude** (when `DEMO_MODE=false` and `ANTHROPIC_API_KEY` is set): a manual tool-use loop on the Messages API with server-side refusal fallbacks. Claude decides what to investigate, which option to recommend, and writes the explanation. Every tool call carries a one-line `rationale` that the user sees.
- **Deterministic planner** (default, works offline): calls the tools in a fixed investigative order and picks the analyzer's recommendation. It also takes over if Claude errors mid-run, skipping the steps Claude already completed.

**Guards on the LLM:**
- It can only propose. The tier comes from `decision.py`, and execution only happens through `actions.py`.
- Option parameters (amounts, accounts, limits) are computed server-side.
- Every number in Claude's explanation must appear in verified data or the trace, otherwise the template text is shown instead (`explanation.grounding_check`).
- If a run ends without a submitted plan, the remaining steps are filled in deterministically.

---

## 5. Safety model

```
TIER_1  Auto            reversible, no money moved, no data shared, every check passes
TIER_2  Your approval   every check passes, but it moves money, shares data or changes SIP/mandate terms
TIER_3  Escalate        any blocking check fails, or the action edits identity or can't be undone
```
Blocking checks: partner status identified, failure mapped, rule retrieved, required evidence verified, root cause confirmed, customer KYC verified, no risk signal, **confidence ≥ 75%**, action reversible, and for transfers, the source account can cover the amount.

The partner policy for each failure code sets a **minimum tier** for impactful actions, so Saarthi can be stricter than the policy but never looser. The server refuses to run Tier 3, and runs Tier 2 only with a recorded approval, whatever the UI sends.

**Confidence** = 0.5 × evidence coverage + 0.3 × root cause confirmed + 0.2 × learned success rate for this code (0.5 before any history).

**Health score** = 50 ± explainable rule factors (failure, shortfall, over-limit, unverified account, recovery available, KYC, and predictive warnings such as "next installment not covered").

---

## 6. Architecture & code map

```
 React app ─ onboarding · Home · Invest (funds, SIPs) · Banks · Saarthi · Profile · Chat
     │  /api/* (X-User-Id header)
 FastAPI
 ├─ product/        the fintech app: users+KYC, bank linking (penny drop), SIPs, mandates, installments
 │     └─ journeys.open_incident() ──► orchestrator.start_agent()   (background thread)
 ├─ agents/
 │   ├─ agent.py         tool-using agent: Claude loop or deterministic planner, live trace
 │   ├─ context.py       journey context from the system of record
 │   ├─ evidence.py      evidence collectors (each states its source)
 │   ├─ diagnosis.py     perceive / knowledge / analyzers per failure type / confidence
 │   ├─ decision.py      deterministic tiers + partner-policy floor
 │   ├─ catalog.py       action safety properties (moves_money, shares_data, changes_terms, ...)
 │   ├─ actions.py       plans executed via partner connectors, then verified
 │   ├─ orchestrator.py  loop, approvals, follow-up incidents, escalation, read models
 │   ├─ health.py · learning.py · graph.py · chat.py · explanation.py · llm.py · prompts.py
 ├─ partners/
 │   ├─ simulators.py    sandbox banks (2 dialects, 4 code sets), Account Aggregator, PAN registry
 │   └─ connectors.py    normalization layer + raw request/response log
 ├─ knowledge/           failure codes (4 banks × 3 failures) + policies, BM25 retrieval
 ├─ services/            name matcher, journal (timeline + audit), INR formatting
 └─ database/            SQLite schema; seed.py loads reference data only
```

Frontend highlights: `pages/Onboarding.tsx`, `components/LinkBankForm.tsx`, `pages/FundDetail.tsx` (start SIP), `pages/Invest.tsx` (SIP controls), `features/journey/AgentTrace.tsx` (live trace), `features/journey/JourneyScreen.tsx`, `pages/EnginePanel.tsx`.

---

## 7. API

Full interactive docs: http://localhost:8000/docs. Every user-scoped call sends `X-User-Id`.

| Area | Endpoints |
|---|---|
| Onboarding | `POST /api/users/register` · `GET /api/users` · `GET /api/me` |
| Banking | `GET/POST /api/accounts` · `POST /api/accounts/{id}/balance` (sandbox) |
| Investing | `GET /api/funds` · `GET /api/funds/{id}` · `GET/POST /api/sips` · `POST /api/sips/{id}/run` · `PATCH /api/sips/{id}` |
| Journeys | `GET /api/journeys` · `GET /api/journeys/{id}` · `GET /api/journeys/{id}/agent` · `POST …/diagnose` (re-run agent) · `POST …/decide` · `POST …/recover` · `POST …/approve` · `POST …/escalate` |
| Saarthi | `GET /api/overview` · `POST /api/chat` · `GET /api/audit` · `GET /api/knowledge` · `GET /api/knowledge/search?q=` · `GET /api/documents` · `GET /api/system` · `POST /api/demo/reset` |
| Sandbox partners (raw dialects) | `GET /partner/{pid}/journey/{ref}` · `POST /partner/{pid}/diagnose` · `POST /partner/{pid}/retry` · `POST /partner/{pid}/update-status` |

---

## 8. Configuration

`backend/.env`:

| Variable | Default | Meaning |
|---|---|---|
| `DEMO_MODE` | `true` | `true` uses the deterministic planner (offline, no key needed) |
| `ANTHROPIC_API_KEY` | empty | With `DEMO_MODE=false`, the agent runs on Claude |
| `SAARTHI_MODEL` | `claude-opus-5-5` | Claude model for the agent, explanations and chat |
| `SAARTHI_DB` | `backend/saarthi.db` | SQLite path |

The engine panel shows which planner is active. Any Claude error falls back to the deterministic planner mid-run, without losing completed steps.

---

## 9. Limitations

- **Sandbox banks only.** No real money, banks or personal data. Fund houses are fictional.
- **No real authentication.** The sandbox identifies the user with an `X-User-Id` header.
- **Three failure families are analyzed:** insufficient funds, mandate limit and name mismatch. Unknown codes are marked unmapped and left for a human.
- **Chat routing is keyword-based.** Claude only phrases the answers when enabled.
- **Not affiliated** with Paytm or any bank, and it doesn't reproduce their UI.

---

## 10. FAQ for judges

- **Is it hardcoded?** No. Every journey comes from a user action, every failure from sandbox state, and every plan from live data. Change the balance, the limit or the bank-record name and the diagnosis and plan change with it.
- **Where's the AI?** An agent that chooses its own investigation steps with tools, recommends a plan and explains it (Claude), on top of retrieval and a failure knowledge graph. Rules keep money safe.
- **What if the AI is wrong?** It can't move money or pick amounts. Tiers are deterministic, execution goes through guarded server code, every outcome is verified with the bank, and explanations are grounding-checked.
- **Can it act?** Yes: IMPS transfers, mandate amendments, debit re-presentation and Account Aggregator consent fetches. Each shows the raw bank response.
- **When does it refuse?** When ownership can't be proven, confidence is below 75%, or any blocking check fails. It then builds a structured case for a human.
- **Different banks?** Four banks, two API dialects and twelve codes, normalized to three standard failures.
- **How does it learn?** Each incident outcome is recorded per bank code, starting from zero, and the success rate feeds the next diagnosis's confidence.

**Tech:** React 18 · Vite · TypeScript · Framer Motion · FastAPI · SQLite · Anthropic SDK (Claude tool use) · BM25 in pure Python.
