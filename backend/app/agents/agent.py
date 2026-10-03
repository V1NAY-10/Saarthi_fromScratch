"""Saarthi's recovery agent.

When a partner rejects something, the orchestrator starts an AgentRun. The agent
investigates with tools, builds recovery options, has each one classified by the
deterministic safety engine and submits a plan. Every step is written to the
run's trace as it happens, so the UI can show the agent working live.

Two planners drive the same tools:
  * Gemini (gemini-2.5-flash, manual tool-use loop) when GEMINI_API_KEY is
    configured and DEMO_MODE is false. Gemini decides which tools to call and
    which plan to submit, and writes the customer explanation. It handles ALL
    failure types: payment failures, mandate issues, name/doc/identity mismatches,
    transient errors, monitoring states, and unknown codes.
  * A deterministic planner otherwise, or if Gemini fails mid-run. It calls the
    tools in a fixed investigative order and picks the analyzer's recommendation.

Either way the agent can only *propose*: tiers come from decision.py, and
nothing executes except through actions.py.
"""
import json
import logging
import uuid

from app import config
from app.agents import context, decision, diagnosis, evidence, explanation, prompts
from app.database import db
from app.knowledge import retrieval
from app.services import namematch
from app.services.fmt import inr

log = logging.getLogger("saarthi.agent")
MAX_TURNS = 14

TOOLS = [
    {"name": "get_journey_context",
     "description": "Read the journey: what the customer was doing, the account and SIP involved, the incident and "
                    "recent timeline events.",
     "input_schema": {"type": "object", "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
    {"name": "query_partner_status",
     "description": "Call the partner bank's own APIs for this journey (status + diagnose). Returns the raw response "
                    "in the bank's dialect and Saarthi's normalized view.",
     "input_schema": {"type": "object", "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
    {"name": "lookup_failure_knowledge",
     "description": "Look up a partner code in the failure knowledge graph: standard failure, root cause, the evidence "
                    "required, allowed recovery actions, equivalent codes at other banks and learned outcomes.",
     "input_schema": {"type": "object", "properties": {"partner_code": {"type": "string"},
                                                       "rationale": {"type": "string"}},
                      "required": ["partner_code", "rationale"]}},
    {"name": "collect_evidence",
     "description": "Run evidence collectors against the system of record. Valid keys: mandate_account_balance, "
                    "installment_amount, mandate_status, mandate_limit, pan_name, bank_record_name, name_similarity, "
                    "document_requirement, attached_document, vault_candidates, kyc_identity, submitted_identity, "
                    "partner_status, retry_history, time_with_partner, paying_account_balance, payment_amount, "
                    "paying_account, verified_accounts. The knowledge entry's evidence_required says which apply.",
     "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}},
                                                       "rationale": {"type": "string"}},
                      "required": ["keys", "rationale"]}},
    {"name": "list_customer_accounts",
     "description": "List the customer's linked bank accounts with live balances and verification status.",
     "input_schema": {"type": "object", "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
    {"name": "compare_names",
     "description": "Explainable name match between two person names (score 0..1, 0.85 passes).",
     "input_schema": {"type": "object", "properties": {"name_a": {"type": "string"}, "name_b": {"type": "string"},
                                                       "rationale": {"type": "string"}},
                      "required": ["name_a", "name_b", "rationale"]}},
    {"name": "check_document_vault",
     "description": "Check the customer's Document Vault against the partner's document rule: which documents could "
                    "satisfy it, and why each does or doesn't. Use for document and identity failures.",
     "input_schema": {"type": "object", "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
    {"name": "search_knowledge",
     "description": "Semantic retrieval (RAG) over Saarthi's Markdown knowledge base: partner rules, document "
                    "requirements, resolution procedures, retry and escalation policies. Returns only relevant sections.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "rationale": {"type": "string"}},
                      "required": ["query", "rationale"]}},
    {"name": "build_recovery_options",
     "description": "Have the backend analyse the failure and compute the concrete recovery options from live data. "
                    "Requires lookup_failure_knowledge and collect_evidence first.",
     "input_schema": {"type": "object", "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
    {"name": "evaluate_option",
     "description": "Ask the deterministic safety engine to classify one recovery option into TIER_1/2/3 with the "
                    "checks it ran.",
     "input_schema": {"type": "object", "properties": {"option_id": {"type": "string"}, "rationale": {"type": "string"}},
                      "required": ["option_id", "rationale"]}},
    {"name": "submit_plan",
     "description": "Submit the recommended recovery option and the customer-facing explanation. Call exactly once, "
                    "last.",
     "input_schema": {"type": "object", "properties": {
         "option_id": {"type": "string"},
         "headline": {"type": "string", "description": "One line: what happened."},
         "summary": {"type": "string", "description": "Why it happened, with the verified numbers."},
         "safety_note": {"type": "string", "description": "What is safe / unaffected."},
         "rationale": {"type": "string", "description": "Why this option over the others."}},
         "required": ["option_id", "headline", "summary", "safety_note", "rationale"]}},
]


class _ToolError(Exception):
    pass


class AgentRun:
    def __init__(self, journey_id: str, run_id: str):
        self.jid, self.run_id = journey_id, run_id
        self.trace: list[dict] = []
        self.mem: dict = {}
        self.mode = "deterministic"

    # ------------------------------------------------------------------ trace
    def _flush(self, **extra):
        db.update("agent_runs", "id", self.run_id, {"trace": self.trace, **extra})

    def thought(self, text: str):
        self.trace.append({"type": "thought", "text": text, "ts": db.now_iso()})
        self._flush()

    def _record_tool(self, name, args, summary, ok=True, data=None):
        self.trace.append({"type": "tool", "tool": name, "rationale": args.get("rationale", ""),
                           "input": {k: v for k, v in args.items() if k != "rationale"}, "summary": summary,
                           "ok": ok, "data": data, "ts": db.now_iso()})
        self._flush()

    # ------------------------------------------------------------------ tools
    def _ctx(self):
        return context.build(self.jid)

    def t_get_journey_context(self, args):
        ctx = self._ctx()
        self.mem["ctx"] = ctx
        out = context.summary_for_agent(ctx)
        j = out["journey"]
        return out, f"{j['title']} · {j['stage']} · partner {j['partner']} · code {j['failure_code']}"

    def t_query_partner_status(self, args):
        ctx = self.mem.get("ctx") or self._ctx()
        self.mem["ctx"] = ctx
        p = diagnosis.perceive(ctx)
        self.mem["perceived"] = p
        n = p["snap"]["normalized"]
        out = {"normalized": n, "raw_status": p["snap"]["raw"], "raw_diagnose": p["pdiag"]["raw"],
               "endpoints": [p["snap"]["endpoint"], p["pdiag"]["endpoint"]]}
        return out, f"{n['partner_name']} says {n['state']} · {n['raw_code'] or 'no code'} · {n['raw_message'] or ''}"

    def t_lookup_failure_knowledge(self, args):
        if "perceived" not in self.mem:
            raise _ToolError("Query the partner status first.")
        j = self.mem["ctx"]["journey"]
        code = args.get("partner_code") or self.mem["perceived"]["snap"]["normalized"]["raw_code"]
        kb = diagnosis.knowledge(j["partner_id"], code)
        if not kb:
            # Unknown code: prepare a human-review diagnosis. Never invent a meaning.
            self.mem["unknown"] = code
            self.mem["diag"] = diagnosis.unmapped(self.mem["ctx"], self.mem["perceived"])
            raise _ToolError(f"No knowledge entry for {j['partner_id']}:{code}. Do not guess its meaning. Search the "
                             "knowledge base; if nothing reliably describes this exact code, submit the escalation "
                             "option (opt-escalate_to_specialist).")
        self.mem["kb"] = kb
        k = kb["data"]
        stats = diagnosis.learned_stats(j["partner_id"], code)
        out = {"title": kb["title"], "body": kb["body"], **k,
               "equivalent_codes": retrieval.equivalent_codes(k["standard_code"]),
               "learned_outcomes": stats or "No outcomes recorded for this code yet"}
        learned = f" · learned {stats['resolved']}/{stats['occurrences']} resolved" if stats else " · no history yet"
        return out, f"{code} → {k['standard_code']} ({k['meaning']}){learned}"

    def t_collect_evidence(self, args):
        if "perceived" not in self.mem:
            raise _ToolError("Query the partner status first.")
        keys = [k for k in args.get("keys", []) if k in evidence.COLLECTORS]
        if not keys:
            raise _ToolError(f"Unknown evidence keys. Valid: {', '.join(evidence.COLLECTORS)}")
        self.mem["ctx"] = self._with_kb(self._ctx())
        p = self.mem["perceived"]
        got = evidence.collect(keys, self.mem["ctx"], p["snap"]["raw"], p["pdiag"]["raw"])
        have = {e["key"]: e for e in self.mem.get("evidence", [])}
        have.update({e["key"]: e for e in got})
        self.mem["evidence"] = list(have.values())
        return got, " · ".join(f"{e['label']}: {e['display']}{'' if e['verified'] else ' (unverified)'}" for e in got)

    def t_list_customer_accounts(self, args):
        ctx = self.mem.get("ctx") or self._ctx()
        out = [{"id": a["id"], "bank": a["bank"], "masked": a["masked"], "balance": a["balance"],
                "status": a["status"]} for a in ctx["accounts"]]
        return out, " · ".join(f"{a['bank']} {a['masked']} {inr(a['balance'])} ({a['status'].lower()})" for a in out)

    def t_compare_names(self, args):
        m = namematch.score(args.get("name_a", ""), args.get("name_b", ""))
        return m, f"'{args.get('name_a')}' vs '{args.get('name_b')}' → {m['score']:.2f} {m['verdict']}" + \
            (f" ({'; '.join(m['reasons'])})" if m["reasons"] else "")

    def _with_kb(self, ctx):
        ctx["kb_entry"] = (self.mem.get("kb") or {}).get("data")
        return ctx

    def t_search_knowledge(self, args):
        q = args.get("query", "")
        pid = (self.mem.get("ctx") or self._ctx())["journey"]["partner_id"]
        hits = retrieval.retrieve_for(q, k=4, partner_id=pid)
        self.mem.setdefault("knowledge", {})
        for h in hits:
            self.mem["knowledge"][h["id"]] = h
            db.insert("knowledge_refs", {"journey_id": self.jid, "run_id": self.run_id, "chunk_id": h["id"],
                                         "engine": h["engine"], "score": h["score"], "ts": db.now_iso()})
        if self.mem.get("unknown"):
            code = self.mem["unknown"]
            reliable = [h for h in hits if h.get("code") == code or code in (h.get("body") or "")]
            self.mem["diag"]["knowledge"] = hits
            note = (f"Found knowledge describing {code}." if reliable else
                    f"Nothing retrieved describes {code}; the closest sections are about other codes, so they can't be "
                    "relied on.")
            return {"hits": hits, "reliable_match": bool(reliable), "note": note}, \
                f"{len(hits)} section(s) via {hits[0]['engine'] if hits else 'retrieval'} · " + \
                ("reliable match" if reliable else f"none describe {code}")
        engine = hits[0]["engine"] if hits else "retrieval"
        return [{"id": h["id"], "title": h["title"], "body": h["body"], "score": h["score"], "source": h["source"]}
                for h in hits], f"{len(hits)} section(s) via {engine}: " + (" · ".join(h["title"] for h in hits) or "none")

    t_search_policies = t_search_knowledge  # older tool name

    def t_check_document_vault(self, args):
        if "kb" not in self.mem:
            raise _ToolError("Look up the failure knowledge first.")
        ctx = self._with_kb(self._ctx())
        p = self.mem["perceived"]
        ftype = self.mem["kb"]["data"]["analyzer"]
        if ftype == "identity_mismatch":
            from app.services import docintel
            docs = [d for d in ctx["vault"] if d["doc_type"] in docintel.IDENTITY_TYPES]
            out = [{"name": d["name"], "version": d["version"], "status": d["status"],
                    "summary": docintel.summary(d["doc_type"], d["fields"])} for d in docs]
            return out, f"{len(out)} identity document(s): " + (" · ".join(f"{o['name']} v{o['version']} ({o['status'].lower()})" for o in out) or "none")
        e = evidence.collect(["vault_candidates", "attached_document"], ctx, p["snap"]["raw"], p["pdiag"]["raw"])
        cands = e[0]["value"] or []
        lines = [f"{c['name']} v{c['version']} ({c['summary']}): " + ("satisfies the rule" + (" (already submitted)" if c["already_submitted"] else "")
                 if c["ok"] else "; ".join(c["issues"])) for c in cands]
        return {"submitted": e[1]["display"], "candidates": cands}, " · ".join(lines) or "No matching documents in the vault"

    def t_build_recovery_options(self, args):
        if "kb" not in self.mem:
            raise _ToolError("Look up the failure knowledge first.")
        k = self.mem["kb"]["data"]
        have = {e["key"] for e in self.mem.get("evidence", [])}
        missing = [x for x in k["evidence_required"] if x not in have]
        if missing:  # the knowledge entry is the contract - fetch what it demands
            self.t_collect_evidence({"keys": missing})
        ev = [e for e in self.mem["evidence"] if e["key"] in k["evidence_required"]]
        self.mem["ctx"] = self._with_kb(self._ctx())
        analysis = diagnosis.analyze(k, self.mem["ctx"], ev, self.mem["perceived"]["pdiag"]["raw"])
        self.mem["analysis"] = analysis
        self.mem["diag"] = diagnosis.assemble(self.mem["ctx"], self.mem["perceived"], self.mem["kb"], ev, analysis,
                                              list(self.mem.get("knowledge", {}).values()))
        out = {"facts": analysis["facts"], "root_cause_confirmed": analysis["confirmed"],
               "risk_signal": analysis.get("risk_signal", False), "confidence": self.mem["diag"]["confidence"],
               "missing_information": analysis["missing"],
               "options": [{"option_id": o["id"], "title": o["title"], "description": o["description"],
                            "effects": o["effects"], "backend_recommends": o["recommended"]} for o in analysis["options"]],
               "draft_explanation": {"headline": analysis["headline"], "summary": analysis["summary"],
                                     "safety_note": analysis["safety_note"]}}
        return out, f"{len(analysis['options'])} option(s): " + " | ".join(o["title"] for o in analysis["options"]) + \
            f" · confidence {self.mem['diag']['confidence']:.0%}"

    def t_evaluate_option(self, args):
        if "diag" not in self.mem:
            raise _ToolError("Build the recovery options first.")
        opt = next((o for o in self.mem["diag"]["options"] if o["id"] == args.get("option_id")), None)
        if not opt:
            raise _ToolError(f"Unknown option. Valid: {', '.join(o['id'] for o in self.mem['diag']['options'])}")
        d = decision.decide(self.mem["diag"], opt, self.mem["ctx"])
        self.mem.setdefault("evaluated", {})[opt["id"]] = d
        failed = [c["label"] for c in d["checks"] if not c["passed"] and c["id"] != "recovery"]
        out = {"tier": d["tier"], "tier_label": d["tier_label"], "reasons": d["reasons"], "failed_checks": failed}
        return out, f"{opt['title']} → {d['tier']} ({'; '.join(d['reasons'])})"

    def t_submit_plan(self, args):
        if "diag" not in self.mem:
            raise _ToolError("Build the recovery options first.")
        opt = next((o for o in self.mem["diag"]["options"] if o["id"] == args.get("option_id")), None)
        if not opt:
            raise _ToolError(f"Unknown option. Valid: {', '.join(o['id'] for o in self.mem['diag']['options'])}")
        self.mem["chosen"] = opt["id"]
        self.mem["explanation"] = {k: args.get(k) for k in ("headline", "summary", "safety_note")}
        self.mem["submitted"] = True
        return {"accepted": True, "note": "Plan recorded. The safety engine's tier decides what happens next."}, \
            f"Recommended: {opt['title']}"

    def call_tool(self, name: str, args: dict) -> tuple[dict | list, str, bool]:
        fn = getattr(self, f"t_{name}", None)
        if not fn:
            return {"error": f"Unknown tool {name}"}, f"Unknown tool {name}", False
        try:
            out, summary = fn(args)
            self._record_tool(name, args, summary, True, _preview(out))
            return out, summary, True
        except _ToolError as e:
            self._record_tool(name, args, str(e), False)
            return {"error": str(e)}, str(e), False

    # ------------------------------------------------------------------ planners
    def run_deterministic(self):
        """A fixed investigative order over the same tools. Steps the LLM already
        completed (if it failed mid-run) are not repeated."""
        ctx = self._ctx()
        j = ctx["journey"]
        code = j["state"].get("failure_code")
        if "ctx" not in self.mem:
            self.thought(f"{ctx['partner']['name']} rejected {j['partner_ref']} with {code}. "
                         "I'll read the journey before touching anything.")
            self.call_tool("get_journey_context", {"rationale": "Understand what the customer was doing."})
        if "perceived" not in self.mem:
            self.call_tool("query_partner_status",
                           {"rationale": "Get the bank's own view instead of trusting our cached status."})
        if self.mem["perceived"]["snap"]["normalized"]["state"] in ("SUCCESS", "VERIFIED"):
            self.thought("The partner now reports success: the problem cleared on the partner's side before I acted. "
                         "Nothing to fix; I'll record it.")
            self.mem["self_resolved"] = True
            return
        if "kb" not in self.mem and not self.mem.get("unknown"):
            self.call_tool("lookup_failure_knowledge",
                           {"partner_code": self.mem["perceived"]["snap"]["normalized"]["raw_code"],
                            "rationale": "Translate the partner's code into a standard failure."})
        if self.mem.get("unknown"):
            code = self.mem["unknown"]
            self.thought(f"{code} isn't in my knowledge base. I'll search for anything that describes it before deciding.")
            _, summary, _ = self.call_tool("search_knowledge", {"query": f"{code} {ctx['partner']['name']} error",
                                                                "rationale": "Look for reliable knowledge about this exact code."})
            self.thought("Nothing I retrieved describes this exact code, so I won't guess a fix. A specialist should "
                         "review it with the partner.")
            self.call_tool("evaluate_option", {"option_id": "opt-escalate_to_specialist",
                                               "rationale": "Confirm the safe path with the safety engine."})
            d = self.mem["diag"]
            self.call_tool("submit_plan", {"option_id": "opt-escalate_to_specialist", "headline": d["headline"],
                                           "summary": d["summary"], "safety_note": d["safety_note"],
                                           "rationale": "Unknown codes are never acted on."})
            return
        k = self.mem["kb"]["data"]
        if not self.mem.get("evidence"):
            self.call_tool("collect_evidence", {"keys": k["evidence_required"],
                                                "rationale": "Collect exactly the evidence this failure requires."})
        an = k["analyzer"]
        if an in ("insufficient_funds", "mandate_limit", "debit_inference", "payment_retry", "account_unverified"):
            self.call_tool("list_customer_accounts",
                           {"rationale": "See whether another of the customer's own accounts could help."})
        elif an == "name_mismatch":
            ev = {e["key"]: e for e in self.mem["evidence"]}
            self.call_tool("compare_names", {"name_a": ev["bank_record_name"]["value"] or "",
                                             "name_b": ev["pan_name"]["value"],
                                             "rationale": "Decide whether this is formatting or a different person."})
        elif an in ("document_requirement", "identity_mismatch"):
            self.call_tool("check_document_vault",
                           {"rationale": "Before asking for an upload, check whether a vault document already satisfies the rule."})
        self.call_tool("search_knowledge", {"query": f"{k['error_code']} {k['customer_meaning']} {k['root_cause']} "
                                                     f"{' '.join(a.replace('_', ' ') for a in k['resolution_options'])}",
                                            "rationale": "Retrieve the partner rule and policies that constrain the fix."})
        self.call_tool("build_recovery_options", {"rationale": "Compute concrete options from live balances and limits."})
        for o in self.mem["diag"]["options"]:
            self.call_tool("evaluate_option", {"option_id": o["id"],
                                               "rationale": f"Classify '{o['title']}' with the safety engine."})
        rec = next(o for o in self.mem["diag"]["options"] if o["recommended"])
        tier = self.mem["evaluated"][rec["id"]]["tier"]
        self.thought(f"Recommending '{rec['title']}' ({tier}). " + {
            "TIER_1": "It's safe and reversible, so I can do it right away.",
            "TIER_2": "It resolves the problem but needs the customer's approval first.",
            "TIER_3": "Automation isn't safe here, so a human should take over with my findings."}[tier])
        a = self.mem["analysis"]
        self.call_tool("submit_plan", {"option_id": rec["id"], "headline": a["headline"], "summary": a["summary"],
                                       "safety_note": a["safety_note"], "rationale": "Least risky option that resolves it."})

    def run_llm(self):
        """RAG-first Gemini tool-use loop. Knowledge is retrieved before the model reasons,
        and every tool result comes from the backend; tiers come only from the safety engine.
        Handles all failure types: payment, mandate, name mismatch, document, identity,
        transient, monitor, human-only, and unknown codes."""
        from app.agents import llm

        ctx = self._ctx()
        self.mem["ctx"] = ctx
        j = ctx["journey"]
        code = j["state"].get("failure_code")
        self.thought(f"{ctx['partner']['name']} returned {code}. First I'll retrieve what the knowledge base says about it.")
        rag, _, _ = self.call_tool("search_knowledge", {
            "query": f"{code} {ctx['partner']['name']} {j['category']} {j['title']}",
            "rationale": "Ground the investigation in the partner's published rules before reasoning."})
        hits = rag.get("hits", rag) if isinstance(rag, dict) else rag
        grounding = "\n".join(f"- [{h.get('source', '')}] {h['title']}: {h['body'][:400]}" for h in (hits or [])[:4]) \
            or "- (nothing retrieved)"
        loop = llm.tool_loop(prompts.AGENT_SYSTEM, TOOLS)
        texts, calls = loop.send(user_text=(
            f"Journey {j['id']} ('{j['title']}', partner ref {j['partner_ref']}) was just rejected or held by "
            f"{ctx['partner']['name']} with code {code}.\n\nRetrieved knowledge (RAG over Saarthi's knowledge base, "
            f"most relevant first):\n{grounding}\n\nInvestigate with the tools and submit a recovery plan. If none "
            "of the retrieved knowledge describes this exact code, do not guess."))
        nudged = False
        for _ in range(MAX_TURNS):
            for t in texts:
                self.thought(t.strip())
            if not calls:
                if self.mem.get("submitted") or nudged:
                    break
                nudged = True
                texts, calls = loop.send(user_text="Please finish by calling submit_plan.")
                continue
            results = []
            for c in calls:
                out, _, ok = self.call_tool(c["name"], c["args"])
                results.append({"id": c["id"], "name": c["name"], "output": out, "error": not ok})
            if self.mem.get("submitted"):
                break
            texts, calls = loop.send(results=results)

    # ------------------------------------------------------------------ finish
    def finalize(self) -> dict:
        """Fill any gap the planner left (so the result is always complete), then
        build the diagnosis record with every option classified."""
        if "diag" not in self.mem and not self.mem.get("self_resolved"):
            self.thought("Completing the investigation steps that weren't run.")
            self.run_deterministic()
        if self.mem.get("self_resolved"):
            return {"journey_id": self.jid, "status": "SELF_RESOLVED", "partner": self.mem["perceived"]["snap"]["normalized"],
                    "agent": {"run_id": self.run_id, "mode": self.mode, "chosen_by": "planner"}}
        if "diag" not in self.mem:  # partner unreachable or code unknown without a diagnosis
            ctx = self.mem.get("ctx") or self._ctx()
            perceived = self.mem.get("perceived") or diagnosis.perceive(ctx)
            self.mem["diag"] = diagnosis.unmapped(ctx, perceived)
        diag = self.mem["diag"]
        ctx = self._ctx()
        if not diag.get("unknown"):
            diag["knowledge"] = list(self.mem.get("knowledge", {}).values()) or \
                retrieval.retrieve_for(f"{diag['kb_entry']['title']} {diag['normalized']['meaning']}")
        diag["decisions"] = decision.decide_all(diag, ctx, self.mem.get("chosen"))
        diag["explanation"] = self._explanation(ctx, diag)
        diag["agent"] = {"run_id": self.run_id, "mode": self.mode, "provider": config.LLM_PROVIDER,
                         "chosen_by": config.LLM_PROVIDER if self.mode == "llm" and self.mem.get("chosen") else "planner"}
        return diag

    def _explanation(self, ctx, diag) -> dict:
        template = {"headline": diag["headline"], "summary": diag["summary"], "safety_note": diag["safety_note"],
                    "source": "deterministic", "grounding": {"passed": True, "numbers_checked": 0, "unsupported": []}}
        out = self.mem.get("explanation")
        fields = ("headline", "summary", "safety_note")
        if self.mode != "llm" or not out or not all(isinstance(out.get(k), str) and out[k] for k in fields):
            return template
        g = explanation.grounding_check(" ".join(out[k] for k in ("headline", "summary", "safety_note")),
                                        {"diag": explanation.llm_context(ctx, diag), "trace": self.trace})
        if not g["passed"]:
            self.thought(f"My draft explanation mentioned numbers I couldn't trace to verified data "
                         f"({', '.join(g['unsupported'])}), so I'm using the verified template instead.")
            return {**template, "grounding": g, "llm_rejected": True}
        return {**out, "source": "llm", "grounding": g}


def _preview(out):
    s = json.dumps(out, ensure_ascii=False, default=str)
    return out if len(s) <= 2500 else {"truncated": s[:2500]}


def new_run(journey_id: str) -> str:
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    mode = "llm" if config.llm_enabled() else "deterministic"
    db.insert("agent_runs", {"id": run_id, "journey_id": journey_id, "status": "RUNNING", "mode": mode,
                             "model": config.SAARTHI_MODEL if mode == "llm" else None, "trace": [], "error": None,
                             "started_at": db.now_iso(), "finished_at": None})
    return run_id


def execute(journey_id: str, run_id: str) -> tuple[dict, "AgentRun"]:
    run = AgentRun(journey_id, run_id)
    if config.llm_enabled():
        run.mode = "llm"
        try:
            run.run_llm()
        except Exception as e:  # never let the LLM break a financial flow
            log.warning("Agent Gemini run failed (%r) - continuing with deterministic planner", e, exc_info=True)
            run.mode = "llm+fallback"
            run.thought("Gemini was unavailable, so I'm continuing with Saarthi's deterministic planner.")
    if not run.mem.get("submitted") and not run.mem.get("self_resolved"):
        run.run_deterministic()
    return run.finalize(), run
