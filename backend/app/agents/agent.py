"""Saarthi's recovery agent.

When a partner rejects something, the orchestrator starts an AgentRun. The agent
investigates with tools, builds recovery options, has each one classified by the
deterministic safety engine and submits a plan. Every step is written to the
run's trace as it happens, so the UI can show the agent working live.

Two planners drive the same tools:
  * Claude (claude-opus-5-5, manual tool-use loop) when an API key is configured
    and DEMO_MODE is off. Claude decides which tools to call and which plan to
    submit, and writes the customer explanation.
  * A deterministic planner otherwise, or if Claude fails mid-run. It calls the
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
                    "installment_amount, mandate_status, mandate_limit, pan_name, bank_record_name, name_similarity.",
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
    {"name": "search_policies",
     "description": "BM25 search over Saarthi's policies and requirements (money movement, retries, name match, "
                    "third-party payments, Account Aggregator consent, escalation).",
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
            raise _ToolError(f"No knowledge entry for {j['partner_id']}:{code}.")
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
        self.mem["ctx"] = self._ctx()
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

    def t_search_policies(self, args):
        hits = retrieval.retrieve_for(args.get("query", ""))
        self.mem.setdefault("knowledge", {})
        for h in hits:
            self.mem["knowledge"][h["id"]] = h
        return [{"id": h["id"], "title": h["title"], "body": h["body"], "score": h["score"]} for h in hits], \
            " · ".join(h["title"] for h in hits) or "No matching policy"

    def t_build_recovery_options(self, args):
        if "kb" not in self.mem:
            raise _ToolError("Look up the failure knowledge first.")
        k = self.mem["kb"]["data"]
        have = {e["key"] for e in self.mem.get("evidence", [])}
        missing = [x for x in k["evidence_required"] if x not in have]
        if missing:  # the knowledge entry is the contract - fetch what it demands
            self.t_collect_evidence({"keys": missing})
        ev = [e for e in self.mem["evidence"] if e["key"] in k["evidence_required"]]
        self.mem["ctx"] = self._ctx()
        analysis = diagnosis.analyze(k["failure_type"], self.mem["ctx"], ev, self.mem["perceived"]["pdiag"]["raw"])
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
        if "kb" not in self.mem:
            _, _, ok = self.call_tool("lookup_failure_knowledge",
                                      {"partner_code": self.mem["perceived"]["snap"]["normalized"]["raw_code"],
                                       "rationale": "Translate the bank's code into a standard failure."})
            if not ok:
                return
        k = self.mem["kb"]["data"]
        if not self.mem.get("evidence"):
            self.call_tool("collect_evidence", {"keys": k["evidence_required"],
                                                "rationale": "Collect exactly the evidence this failure requires."})
        ft = k["failure_type"]
        if ft in ("PAYMENT_FAILURE", "MANDATE_LIMIT"):
            self.call_tool("list_customer_accounts",
                           {"rationale": "See whether another of the customer's own accounts could help."})
        else:
            ev = {e["key"]: e for e in self.mem["evidence"]}
            self.call_tool("compare_names", {"name_a": ev["bank_record_name"]["value"] or "",
                                             "name_b": ev["pan_name"]["value"],
                                             "rationale": "Decide whether this is formatting or a different person."})
        self.call_tool("search_policies", {"query": f"{k['meaning']} {k['root_cause']} "
                                                    f"{' '.join(a.replace('_', ' ') for a in k['recovery_actions'])}",
                                           "rationale": "Check which policies constrain the fix."})
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
        from app.agents.llm import agent_client

        client = agent_client()
        j = self._ctx()["journey"]
        messages = [{"role": "user", "content":
                     f"Journey {j['id']} ('{j['title']}', partner ref {j['partner_ref']}) was just rejected by the "
                     f"partner with code {j['state'].get('failure_code')}. Investigate and submit a recovery plan."}]
        nudged = False
        for _ in range(MAX_TURNS):
            resp = client.beta.messages.create(
                model=config.SAARTHI_MODEL, max_tokens=16000, system=prompts.AGENT_SYSTEM, tools=TOOLS,
                messages=messages, output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
            if resp.stop_reason == "refusal":
                raise RuntimeError("Claude declined the request")
            messages.append({"role": "assistant", "content": resp.content})
            for b in resp.content:
                if b.type == "text" and b.text.strip():
                    self.thought(b.text.strip())
            uses = [b for b in resp.content if b.type == "tool_use"]
            if not uses:
                if self.mem.get("submitted") or nudged or resp.stop_reason == "max_tokens":
                    break
                nudged = True
                messages.append({"role": "user", "content": "Please finish by calling submit_plan."})
                continue
            results = []
            for u in uses:
                out, _, ok = self.call_tool(u.name, dict(u.input or {}))
                results.append({"type": "tool_result", "tool_use_id": u.id,
                                "content": json.dumps(out, ensure_ascii=False, default=str)[:8000],
                                **({} if ok else {"is_error": True})})
            messages.append({"role": "user", "content": results})
            if self.mem.get("submitted"):
                break

    # ------------------------------------------------------------------ finish
    def finalize(self) -> dict:
        """Fill any gap the planner left (so the result is always complete), then
        build the diagnosis record with every option classified."""
        if "diag" not in self.mem:
            self.thought("Completing the investigation steps that weren't run.")
            self.run_deterministic()
        if "diag" not in self.mem:  # code not in the knowledge base
            ctx = self.mem.get("ctx") or self._ctx()
            perceived = self.mem.get("perceived") or diagnosis.perceive(ctx)
            return diagnosis.unmapped(ctx, perceived)
        diag = self.mem["diag"]
        ctx = self._ctx()
        diag["knowledge"] = list(self.mem.get("knowledge", {}).values()) or \
            retrieval.retrieve_for(f"{diag['kb_entry']['title']} {diag['normalized']['meaning']}")
        diag["decisions"] = decision.decide_all(diag, ctx, self.mem.get("chosen"))
        diag["explanation"] = self._explanation(ctx, diag)
        diag["agent"] = {"run_id": self.run_id, "mode": self.mode,
                         "chosen_by": "claude" if self.mode == "llm" and self.mem.get("chosen") else "planner"}
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
            log.warning("Agent LLM run failed (%r) - continuing with deterministic planner", e, exc_info=True)
            run.mode = "llm+fallback"
            run.thought("Claude was unavailable, so I'm continuing with Saarthi's deterministic planner.")
    if not run.mem.get("submitted"):
        run.run_deterministic()
    return run.finalize(), run
