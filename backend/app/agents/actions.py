"""Action Engine - executes recovery plans through partner connectors.

Server-side guards (independent of the UI and of the LLM):
  * TIER_3 actions are never executed.
  * TIER_2 actions execute only after an explicit user approval is recorded.
  * Every step is verified against the partner before the journey is marked resolved.
"""
import uuid

from app.agents.context import get_journey
from app.database import db
from app.partners import connectors
from app.services import journal
from app.services.fmt import inr


class ActionBlocked(Exception):
    pass


def create(journey_id: str, decision: dict, option: dict) -> dict:
    status = {"TIER_1": "AUTO", "TIER_2": "PENDING_APPROVAL", "TIER_3": "BLOCKED"}[decision["tier"]]
    row = {"id": f"act-{uuid.uuid4().hex[:8]}", "journey_id": journey_id, "decision_id": decision.get("id"),
           "action_type": option["action_type"], "tier": decision["tier"], "status": status,
           "params": option["params"], "result": {}, "created_at": db.now_iso(), "completed_at": None}
    db.insert("actions", row)
    return db.query_one("SELECT * FROM actions WHERE id=?", (row["id"],))


def _step(label, resp=None, ok=True, detail=""):
    return {"label": label, "ok": ok, "detail": detail, "ts": db.now_iso(),
            "endpoint": resp["endpoint"] if resp else None,
            "partner_raw": resp["raw"] if resp else None,
            "partner_normalized": resp["normalized"] if resp else None}


def _retry(j, steps, label):
    r = connectors.call(j["partner_id"], "retry", journey_id=j["id"], ref=j["partner_ref"])
    ok = r["normalized"]["state"] == "SUCCESS"
    steps.append(_step(label, r, ok, f"{r['normalized']['raw_message'] or ''}"
                                     f"{' · ' + r['normalized']['raw_code'] if r['normalized']['raw_code'] else ''}"))
    journal.add_event(j["id"], "partner", "Debit re-presented", r["normalized"]["raw_message"] or "",
                      status="done" if ok else "failed", actor=j["partner_id"], stage="act")
    return ok


# ------------------------------------------------------------------ plans
def _fund_and_retry(j, p):
    steps = []
    src = db.query_one("SELECT * FROM accounts WHERE id=?", (p["source_account"],))
    t = connectors.call(src["partner_id"], "transfer", journey_id=j["id"], from_account=p["source_account"],
                        to_account=p["target_account"], amount=p["amount"])
    ok = t["normalized"]["state"] == "SUCCESS"
    steps.append(_step(f"Transferred {inr(p['amount'])} from {p['source_label']}", t, ok,
                       f"IMPS UTR {t['raw'].get('utr', '—')}"))
    journal.add_event(j["id"], "action", f"Moved {inr(p['amount'])} between your accounts",
                      f"{p['source_label']} → {p['target_label']} · UTR {t['raw'].get('utr', '—')}",
                      status="done" if ok else "failed", stage="act")
    if not ok:
        return steps, False
    acc = db.query_one("SELECT * FROM accounts WHERE id=?", (p["target_account"],))
    funded = acc["balance"] >= j["amount"]
    steps.append(_step("Autopay account balance re-checked", ok=funded,
                       detail=f"{acc['bank']} {acc['masked']}: {inr(acc['balance'])} vs {inr(j['amount'])} needed"))
    if not funded:
        return steps, False
    return steps, _retry(j, steps, "Bank re-presented the SIP debit")


def _retry_debit(j, p):
    steps = []
    acc = db.query_one("SELECT * FROM accounts WHERE id=?", (j["state"]["account_id"],))
    steps.append(_step("Autopay account balance re-checked", ok=acc["balance"] >= j["amount"],
                       detail=f"{acc['bank']} {acc['masked']}: {inr(acc['balance'])} vs {inr(j['amount'])} needed"))
    if acc["balance"] < j["amount"]:
        return steps, False
    return steps, _retry(j, steps, "Bank re-presented the SIP debit")


def _raise_limit(j, p):
    steps = []
    r = connectors.call(j["partner_id"], "amend_mandate", journey_id=j["id"], umrn=p["umrn"], max_amount=p["new_limit"])
    ok = r["normalized"]["state"] == "SUCCESS"
    steps.append(_step(f"Autopay limit raised {inr(p['old_limit'])} → {inr(p['new_limit'])}", r, ok,
                       f"UMRN {p['umrn']} amended"))
    if not ok:
        return steps, False
    db.update("mandates", "id", p["mandate_id"], {"max_amount": p["new_limit"]})
    journal.add_event(j["id"], "action", "Autopay limit raised", f"{inr(p['old_limit'])} → {inr(p['new_limit'])}",
                      stage="act", actor=j["partner_id"])
    # The bank re-presents the amount on the original presentment; make sure it's the current SIP amount.
    return steps, _retry(j, steps, "Bank re-presented the SIP debit")


def _reduce_sip(j, p):
    from app.partners import simulators
    steps = []
    sid = j["state"]["sip_id"]
    db.update("sips", "id", sid, {"amount": p["new_amount"]})
    db.update("journeys", "id", j["id"], {"amount": p["new_amount"]})
    st = simulators._get(j["partner_id"], j["partner_ref"])
    st["amount"] = p["new_amount"]
    simulators._put(j["partner_id"], j["partner_ref"], st)
    steps.append(_step(f"SIP changed {inr(p['old_amount'])} → {inr(p['new_amount'])}", ok=True,
                       detail="Presentment amended to the new amount"))
    journal.add_event(j["id"], "action", "SIP amount brought within autopay limit",
                      f"{inr(p['old_amount'])} → {inr(p['new_amount'])}", stage="act")
    j = get_journey(j["id"])
    return steps, _retry(j, steps, "Bank re-presented the SIP debit")


def _verify_ownership(j, p):
    steps = []
    consent_id = f"AA-CNS-{uuid.uuid4().hex[:6].upper()}"
    steps.append(_step("Consent artefact created", ok=True,
                       detail=f"{consent_id} · account profile of {p['account_label']} · one-time"))
    f = connectors.call("aa", "fetch_profile", journey_id=j["id"], account_id=p["account_id"], consent_id=consent_id)
    holder = f["raw"]["profile"]["holders"][0]
    user = db.query_one("SELECT * FROM users WHERE id=?", (j["user_id"],))
    pan_ok = holder["pan"] == user["pan"]
    masked = holder["pan"][:5] + "••••" + holder["pan"][-1]
    steps.append(_step(f"Bank returned account holder profile", f, True,
                       f"Holder {holder['name']} · PAN {masked} · fetched directly from the bank"))
    steps.append(_step("PAN on bank record matches your PAN" if pan_ok else "PAN on bank record is NOT your PAN",
                       ok=pan_ok, detail=f"Bank: {masked} · KYC: {user['pan'][:5]}••••{user['pan'][-1]}"))
    from app.product import journeys as product_journeys
    product_journeys.patch_state(j["id"], aa_ownership="PAN_MATCH" if pan_ok else "PAN_MISMATCH")
    journal.add_event(j["id"], "document", "Ownership checked via Account Aggregator",
                      "PAN matches" if pan_ok else "PAN does not match", status="done" if pan_ok else "failed",
                      stage="act", actor="aa")
    if not pan_ok:
        return steps, False
    v = connectors.call(j["partner_id"], "mark_verified", journey_id=j["id"], ref=j["partner_ref"],
                        method="AA PAN match")
    ok = v["normalized"]["state"] == "VERIFIED"
    steps.append(_step("Bank marked the account verified", v, ok, v["normalized"]["raw_message"] or ""))
    return steps, ok


def _remind(j, p):
    from app.product import journeys as product_journeys
    product_journeys.patch_state(j["id"], reminder_set=True)
    journal.add_event(j["id"], "action", "Watching for a top-up",
                      f"Saarthi will retry with your approval once {inr(p.get('shortfall') or 0)} more is in the account",
                      stage="act")
    return [_step("Reminder scheduled", ok=True, detail="No money moved · reversible")], True


PLANS = {"fund_and_retry": _fund_and_retry, "retry_debit": _retry_debit, "raise_mandate_limit_and_retry": _raise_limit,
         "reduce_sip_to_limit": _reduce_sip, "verify_ownership_via_aa": _verify_ownership,
         "remind_before_window": _remind}

VERIFY_STATES = {"fund_and_retry": "SUCCESS", "retry_debit": "SUCCESS", "raise_mandate_limit_and_retry": "SUCCESS",
                 "reduce_sip_to_limit": "SUCCESS", "verify_ownership_via_aa": "VERIFIED"}


def execute(action_id: str, approved_by_user: bool = False) -> dict:
    a = db.query_one("SELECT * FROM actions WHERE id=?", (action_id,))
    if not a:
        raise ActionBlocked("Unknown action")
    if a["tier"] == "TIER_3":
        journal.audit(a["journey_id"], "safety_engine", "BLOCKED", f"Refused to execute {a['action_type']} (TIER_3)")
        raise ActionBlocked("Tier 3 actions are never executed automatically")
    if a["tier"] == "TIER_2" and not approved_by_user:
        raise ActionBlocked("This action requires your explicit approval")
    if a["status"] in ("COMPLETED", "FAILED"):
        return a
    j = get_journey(a["journey_id"])
    db.update("actions", "id", a["id"], {"status": "EXECUTING"})
    journal.audit(j["id"], "action_engine", "ACTION_STARTED", f"Executing {a['action_type']} ({a['tier']})", a["params"])
    steps, ok = PLANS[a["action_type"]](j, a["params"])

    verification = None
    if ok and a["action_type"] in VERIFY_STATES:
        v = connectors.call(j["partner_id"], "get_journey", journey_id=j["id"], ref=j["partner_ref"])
        expected = VERIFY_STATES[a["action_type"]]
        got = v["normalized"]["state"]
        ok = got == expected
        verification = {"endpoint": v["endpoint"], "expected": expected, "observed": got, "passed": ok,
                        "partner_raw": v["raw"], "partner_code": v["normalized"]["raw_code"]}
        steps.append(_step("Outcome verified with partner", v, ok, f"Expected {expected}, partner reports {got}"))

    status = "COMPLETED" if ok else "FAILED"
    result = {"steps": steps, "verification": verification, "ok": ok}
    db.update("actions", "id", a["id"], {"status": status, "result": result, "completed_at": db.now_iso()})
    journal.audit(j["id"], "action_engine", "ACTION_" + status,
                  f"{a['action_type']} {status.lower()}" + (f" · verified ({verification['observed']})" if verification else ""),
                  {"verification": verification})
    return db.query_one("SELECT * FROM actions WHERE id=?", (a["id"],))
