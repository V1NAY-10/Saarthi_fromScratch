"""Saarthi orchestrator - runs the loop

    PERCEIVE -> DIAGNOSE -> DECIDE -> ACT -> VERIFY -> LEARN

A partner rejection opens an incident (product/journeys.open_incident), which
calls start_agent(). The agent investigates in a background thread and its
plan is persisted here: Tier 1 runs immediately, Tier 2 waits for the user's
approval, Tier 3 is refused and offered for escalation. After an action runs,
the outcome is verified with the partner, the journey is resolved (or a new
incident is opened if the partner now reports a different problem), and the
outcome is learned."""
import logging
import threading
import uuid

from app.agents import actions, agent, context, decision, graph, health, learning
from app.database import db
from app.partners import connectors
from app.services import journal
from app.services.fmt import inr

log = logging.getLogger("saarthi.orchestrator")
LOOP = ["perceive", "diagnose", "decide", "act", "verify", "learn"]
SIP_ACTIONS = {"fund_and_retry", "retry_debit", "raise_mandate_limit_and_retry", "reduce_sip_to_limit"}

_running: set[str] = set()
_running_lock = threading.Lock()


# ------------------------------------------------------------------ storage
def _store(jid: str, payload: dict) -> None:
    db.insert("diagnoses", {"journey_id": jid, "payload": payload, "created_at": db.now_iso()})


def stored(jid: str) -> dict | None:
    row = db.query_one("SELECT * FROM diagnoses WHERE journey_id=?", (jid,))
    return row["payload"] if row else None


def latest_run(jid: str) -> dict | None:
    return db.query_one("SELECT * FROM agent_runs WHERE journey_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
                        (jid,))


# ------------------------------------------------------------------ agent lifecycle
def start_agent(jid: str, reason: str = "", wait: bool = False) -> str | None:
    with _running_lock:
        if jid in _running:
            return None
        _running.add(jid)
    run_id = agent.new_run(jid)
    journal.audit(jid, "saarthi", "PERCEIVE", f"Agent started · {reason}" if reason else "Agent started",
                  {"run_id": run_id})
    journal.add_event(jid, "saarthi", "Saarthi started investigating", reason, stage="perceive")
    t = threading.Thread(target=_agent_job, args=(jid, run_id), daemon=True)
    t.start()
    if wait:
        t.join()
    return run_id


def _agent_job(jid: str, run_id: str) -> None:
    try:
        diag, run = agent.execute(jid, run_id)
        persist(jid, diag)
        db.update("agent_runs", "id", run_id, {"status": "DONE", "mode": run.mode, "trace": run.trace,
                                               "finished_at": db.now_iso()})
    except Exception as e:
        log.exception("Agent run %s failed", run_id)
        db.update("agent_runs", "id", run_id, {"status": "FAILED", "error": str(e), "finished_at": db.now_iso()})
    finally:
        with _running_lock:
            _running.discard(jid)


def reopen(jid: str, reason: str) -> None:
    """Re-run the agent on the same incident with fresh evidence."""
    db.execute("DELETE FROM diagnoses WHERE journey_id=?", (jid,))
    db.execute("UPDATE actions SET status='SUPERSEDED' WHERE journey_id=? AND status IN "
               "('PENDING_APPROVAL','AUTO','BLOCKED')", (jid,))
    start_agent(jid, reason)


def resume_stale() -> None:
    """After a restart: mark interrupted runs failed and re-investigate open incidents."""
    db.execute("UPDATE agent_runs SET status='FAILED', error='Server restarted' WHERE status='RUNNING'")
    for j in db.query("SELECT id FROM journeys WHERE status='ATTENTION'"):
        if not stored(j["id"]):
            start_agent(j["id"], "Resuming after restart")


def persist(jid: str, diag: dict) -> None:
    if diag.get("status") != "DIAGNOSED":
        _store(jid, diag)
        journal.add_event(jid, "saarthi", "Saarthi couldn't map this failure", diag.get("summary", ""),
                          status="waiting", stage="diagnose")
        return
    code = diag["partner"]["raw_code"]
    journal.add_event(jid, "saarthi", "Saarthi diagnosed the issue", diag["normalized"]["root_cause"], stage="diagnose")
    journal.audit(jid, "diagnosis_engine", "DIAGNOSIS",
                  f"{code} → {diag['normalized']['standard_code']} · confidence {diag['confidence']:.0%}",
                  {"partner": diag["partner"]["partner_name"], "failure": code, "confidence": diag["confidence"],
                   "agent": diag.get("agent")})
    p = diag["decisions"]["primary"]
    if not p:
        _store(jid, diag)
        return
    option = next(o for o in diag["options"] if o["id"] == diag["decisions"]["primary_option_id"])
    p["id"] = f"dec-{uuid.uuid4().hex[:8]}"
    db.insert("decisions", {"id": p["id"], "journey_id": jid, "option_id": option["id"], "tier": p["tier"],
                            "checks": p["checks"], "rationale": "; ".join(p["reasons"]), "created_at": db.now_iso()})
    act = actions.create(jid, p, option)
    diag["pending_action_id"] = act["id"]
    _store(jid, diag)
    title = {"TIER_1": "Safe action taken automatically", "TIER_2": "Recovery proposed · your approval needed",
             "TIER_3": "Automation paused · human review recommended"}[p["tier"]]
    journal.add_event(jid, "saarthi", title, option["title"], stage="decide",
                      status="done" if p["tier"] == "TIER_1" else "waiting")
    journal.audit(jid, "decision_engine", "DECISION", f"{p['tier']} · {option['title']}",
                  {"tier": p["tier"], "reasons": p["reasons"],
                   "failed_checks": [c["label"] for c in p["checks"] if not c["passed"]]})
    if p["tier"] == "TIER_1":
        before = _health(jid, diag)
        _after_action(jid, actions.execute(act["id"]), before)


# ------------------------------------------------------------------ act
def recover(jid: str, option_id: str | None = None) -> dict:
    """Request a recovery. Tier decides what happens: execute / await approval / refuse."""
    diag = stored(jid)
    if not diag or diag.get("status") != "DIAGNOSED":
        raise actions.ActionBlocked("Saarthi is still investigating this journey")
    ctx = context.build(jid)
    option_id = option_id or diag["decisions"]["primary_option_id"]
    option = next((o for o in diag["options"] if o["id"] == option_id), None)
    if not option:
        raise actions.ActionBlocked("Unknown recovery option")
    dec = decision.decide(diag, option, ctx)
    since = ctx["journey"]["state"].get("incident_started_at") or ""
    pending = db.query_one("SELECT * FROM actions WHERE journey_id=? AND action_type=? AND created_at>=? AND status IN "
                           "('PENDING_APPROVAL','AUTO','BLOCKED')", (jid, option["action_type"], since))
    act = pending or actions.create(jid, dec, option)
    if dec["tier"] == "TIER_1":
        before = _health(jid, diag)
        act = actions.execute(act["id"])
        _after_action(jid, act, before)
        return {"outcome": "EXECUTED", "decision": dec, "action": act}
    if dec["tier"] == "TIER_2":
        return {"outcome": "APPROVAL_REQUIRED", "decision": dec, "action": act}
    journal.audit(jid, "safety_engine", "REFUSED", f"Will not execute {option['action_type']} automatically",
                  {"reasons": dec["reasons"]})
    return {"outcome": "ESCALATION_RECOMMENDED", "decision": dec, "action": act}


def approve(jid: str, action_id: str) -> dict:
    a = db.query_one("SELECT * FROM actions WHERE id=? AND journey_id=?", (action_id, jid))
    if not a:
        raise actions.ActionBlocked("Action not found for this journey")
    if a["status"] != "PENDING_APPROVAL":
        if a["status"] == "COMPLETED":
            return view(jid)
        raise actions.ActionBlocked(f"Action is {a['status']}, not awaiting approval")
    journal.add_event(jid, "user", "You approved the recovery", a["action_type"].replace("_", " "),
                      actor="user", stage="act")
    journal.audit(jid, "user", "USER_APPROVED", f"User approved {a['action_type']} ({a['tier']})", a["params"])
    before = _health(jid, stored(jid))
    result = actions.execute(action_id, approved_by_user=True)
    _after_action(jid, result, before)
    return {**view(jid), "action_result": result}


def _health(jid: str, diag: dict | None) -> int:
    ctx = context.build(jid)
    primary = (diag or {}).get("decisions", {}).get("primary")
    return health.compute(ctx, diag, primary if ctx["journey"]["status"] == "ATTENTION" else None)["score"]


def _after_action(jid: str, act: dict, before: int) -> None:
    from app.product import journeys as pj
    from app.product import sips as product_sips

    j = context.get_journey(jid)
    diag = stored(jid)
    at = act["action_type"]

    if act["status"] == "COMPLETED" and at == "remind_before_window":
        pj.close_incident(jid, "ATTENTION", "Waiting for a top-up")
        return

    if act["status"] == "COMPLETED":
        if at in SIP_ACTIONS:
            raw = act["result"]["verification"]["partner_raw"]
            bank_ref = raw.get("bankRefNo") or raw.get("utr")
            product_sips.complete_installment(j["state"]["sip_id"], bank_ref)
            n = j["state"].get("installment_no", "")
            pj.close_incident(jid, "RESOLVED", f"Installment #{n} recovered", bank_ref=bank_ref,
                              last_success_at=db.now_iso())
            journal.add_event(jid, "partner", "Payment confirmed by the bank", f"{inr(j['amount'])} · Ref {bank_ref}",
                              actor=j["partner_id"], stage="verify")
        elif at == "verify_ownership_via_aa":
            db.update("accounts", "id", j["state"]["account_id"], {"status": "VERIFIED"})
            pj.close_incident(jid, "RESOLVED", "Account verified")
            journal.add_event(jid, "partner", "Bank account verified", "Ownership proven via PAN on bank record",
                              actor=j["partner_id"], stage="verify")
        lesson = learning.record(context.get_journey(jid), diag, at, "SUCCESS")
        after = _health(jid, diag)
        diag["lesson"] = lesson
        diag["health_transition"] = {"before": before, "after": after}
        _store(jid, diag)
        journal.add_event(jid, "saarthi", "Saarthi learned from this resolution",
                          f"{lesson['partner_code']}: {lesson['after']['resolved']} of "
                          f"{lesson['after']['occurrences']} incidents resolved", stage="learn")
        journal.audit(jid, "health_engine", "HEALTH_UPDATED", f"Journey health {before} → {after}",
                      {"before": before, "after": after})
        return

    # ---- the action did not achieve its goal: find out why, never retry blindly.
    # The incident is still open, so nothing is learned yet - unless the original problem
    # was fixed and a different one surfaced, which counts as a success for the first code.
    if at == "verify_ownership_via_aa":
        journal.add_event(jid, "saarthi", "Ownership not proven", "Re-assessing with the new evidence",
                          status="failed", stage="verify")
        reopen(jid, "Account Aggregator returned a different PAN")
        return
    if at in SIP_ACTIONS:
        snap = connectors.call(j["partner_id"], "get_journey", journey_id=jid, ref=j["partner_ref"])
        code = snap["normalized"]["raw_code"]
        if code and code != j["state"].get("failure_code"):
            learning.record(j, diag, at, "SUCCESS")
            journal.add_event(jid, "saarthi", "First problem fixed, a new one surfaced",
                              f"{j['state'].get('failure_code')} cleared · bank now reports {code}", stage="verify")
            pj.open_incident(jid, code, snap["normalized"]["raw_message"] or "", j["partner_id"],
                             f"Installment #{j['state'].get('installment_no', '')} failed again")
            return
    journal.add_event(jid, "saarthi", "Recovery did not complete", "Saarthi is re-checking instead of retrying blindly",
                      status="failed", stage="verify")
    reopen(jid, "Recovery attempt did not verify")


# ------------------------------------------------------------------ escalate
NEXT_ACTION = {
    "ACCOUNT_VERIFICATION": ("Confirm with the customer on a recorded call whether the account is held in their name. "
                             "If it belongs to someone else, ask them to link an account in their own name. If it is "
                             "theirs, collect a bank-attested ownership letter and mark the account verified.",
                             ["Do not enable autopay on this account until ownership is confirmed",
                              "Do not accept mutual fund payments from this account (third-party payment rule)"]),
    "PAYMENT_FAILURE": ("Call the customer before the re-presentation window closes and agree how the shortfall will "
                        "be covered.", ["Do not re-present the debit without a confirmed balance"]),
    "MANDATE_LIMIT": ("Help the customer amend the autopay limit with their bank, or bring the SIP back within it.",
                      ["Do not re-present above the mandate limit"]),
}


def escalate(jid: str) -> dict:
    diag = stored(jid)
    if not diag:
        raise actions.ActionBlocked("Saarthi is still investigating this journey")
    if db.query_one("SELECT * FROM support_cases WHERE journey_id=? AND status='OPEN'", (jid,)):
        return view(jid)
    ctx = context.build(jid)
    j = ctx["journey"]
    case_id = f"SRT-{uuid.uuid4().hex[:6].upper()}"
    dec = diag.get("decisions", {}).get("primary")
    ft = diag.get("normalized", {}).get("failure_type", "")
    nxt, do_not = NEXT_ACTION.get(ft, ("Review the journey with the customer.", []))
    calls = db.query("SELECT endpoint, raw_json, normalized_json, ts FROM partner_responses WHERE journey_id=? "
                     "ORDER BY id DESC LIMIT 6", (jid,))
    run = latest_run(jid)
    payload = {
        "case_id": case_id, "priority": "P1 · Ownership risk" if diag.get("risk_signal") else "P2",
        "customer": {"id": ctx["user"]["id"], "name": ctx["user"]["name"], "kyc_status": ctx["user"]["kyc_status"]},
        "journey": {"id": jid, "title": j["title"], "partner": ctx["partner"]["name"], "ref": j["partner_ref"],
                    "amount": j["amount"]},
        "why_escalated": dec["reasons"] if dec else ["Low confidence"],
        "failed_checks": [c for c in (dec["checks"] if dec else []) if not c["passed"] and c["id"] != "recovery"],
        "checks_completed": [c for c in (dec["checks"] if dec else []) if c["passed"]],
        "evidence": diag.get("evidence", []), "facts": diag.get("facts", []),
        "partner_response": {"normalized": diag.get("partner"), "raw": diag.get("partner_raw"),
                             "diagnose": diag.get("partner_diagnose_raw")},
        "partner_calls": calls, "agent_trace": (run or {}).get("trace", []),
        "timeline": [{"ts": e["ts"], "title": e["title"], "detail": e["detail"]} for e in ctx["events"]],
        "confidence": diag.get("confidence"), "recommended_next_action": nxt, "do_not": do_not,
        "customer_safety": diag.get("safety_note"), "sla": "Specialist callback within 4 business hours",
    }
    db.insert("support_cases", {"id": case_id, "journey_id": jid, "created_at": db.now_iso(),
                                "priority": payload["priority"], "status": "OPEN", "payload": payload})
    connectors.call(j["partner_id"], "update_status", journey_id=jid, ref=j["partner_ref"], status="SPECIALIST_REVIEW")
    db.execute("UPDATE actions SET status='ESCALATED', completed_at=? WHERE journey_id=? AND status IN "
               "('BLOCKED','PENDING_APPROVAL')", (db.now_iso(), jid))
    before = _health(jid, diag)
    from app.product import journeys as pj
    pj.close_incident(jid, "ESCALATED", "With specialist", case_id=case_id)
    if diag.get("status") == "DIAGNOSED":
        learning.record(context.get_journey(jid), diag, "escalate_to_specialist", "ESCALATED")
    after = _health(jid, diag)
    diag["health_transition"] = {"before": before, "after": after}
    _store(jid, diag)
    journal.add_event(jid, "saarthi", "Escalated to a human specialist", f"Case {case_id} · full context attached",
                      stage="act")
    journal.audit(jid, "saarthi", "ESCALATED", f"Support case {case_id} created ({payload['priority']})",
                  {"case_id": case_id, "reasons": payload["why_escalated"]})
    return view(jid)


# ------------------------------------------------------------------ read models
def loop_state(j: dict, events: list[dict], run: dict | None) -> list[dict]:
    if j["status"] in ("ON_TRACK", "COMPLETE"):
        return [{"stage": s, "state": "done" if s == "perceive" else "idle"} for s in LOOP]
    since = j["state"].get("incident_started_at") or ""
    recent = [e for e in events if e["ts"] >= since]
    done = {e["loop_stage"] for e in recent if e["status"] != "failed"} | {"perceive"}
    if run and run["status"] == "RUNNING":
        done -= {"diagnose", "decide", "act", "verify", "learn"}
    out, current_set = [], False
    for s in LOOP:
        if s in done:
            state = "done"
        elif not current_set and j["status"] == "ATTENTION":
            state, current_set = "current", True
        else:
            state = "pending"
        out.append({"stage": s, "state": state})
    return out


def view(jid: str) -> dict:
    ctx = context.build(jid)
    j = ctx["journey"]
    diag = stored(jid)
    run = latest_run(jid)
    if j["status"] == "ATTENTION" and not diag and not (run and run["status"] == "RUNNING") and jid not in _running:
        start_agent(jid, "Re-investigating")
        run = latest_run(jid)
    primary = diag.get("decisions", {}).get("primary") if diag else None
    h = health.compute(ctx, diag, primary if j["status"] == "ATTENTION" else None)
    if j["health_score"] != h["score"]:
        db.update("journeys", "id", jid, {"health_score": h["score"]})
    case = db.query_one("SELECT * FROM support_cases WHERE journey_id=? ORDER BY created_at DESC", (jid,))
    return {
        "journey": {**j, "health_score": h["score"], "partner_name": ctx["partner"]["name"]},
        "health": h,
        "diagnosis": diag,
        "agent_run": run,
        "graph": graph.build(diag, primary, j["status"]) if diag and diag.get("status") == "DIAGNOSED" else None,
        "timeline": ctx["events"],
        "loop": loop_state(j, ctx["events"], run),
        "actions": ctx["previous_actions"][::-1],
        "documents": ctx["documents"],
        "linked_account": ctx["linked_account"],
        "sip": ctx["sip"], "mandate": ctx["mandate"], "fund": ctx["fund"],
        "support_case": case if case and j["status"] == "ESCALATED" else None,
        "audit": journal.audit_log(jid, 60),
    }


def summary(j: dict) -> dict:
    ctx = context.build(j["id"])
    diag = stored(j["id"]) if j["status"] != "ON_TRACK" else None
    primary = diag.get("decisions", {}).get("primary") if diag else None
    h = health.compute(ctx, diag, primary if j["status"] == "ATTENTION" else None)
    run = latest_run(j["id"])
    out = {**j, "health_score": h["score"], "band": h["band"], "partner_name": ctx["partner"]["name"],
           "agent_status": run["status"] if run else None}
    if diag and diag.get("status") == "DIAGNOSED":
        out["saarthi"] = {"headline": diag["explanation"]["headline"], "summary": diag["explanation"]["summary"],
                          "tier": primary["tier"] if primary else None, "partner_code": diag["partner"]["raw_code"],
                          "meaning": diag["normalized"]["meaning"],
                          "failure_type": diag["normalized"]["failure_type"]}
    return out
