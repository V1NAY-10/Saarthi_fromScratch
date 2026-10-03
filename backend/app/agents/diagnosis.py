"""Failure Diagnosis Engine.

PARTNER-SPECIFIC STATUS -> STANDARDIZED FAILURE -> ROOT CAUSE -> EVIDENCE -> RECOVERY OPTIONS

The functions here are the building blocks the agent calls as tools:

  perceive()   query the partner through its connector, normalize the response
  knowledge()  structured lookup of the partner code in the failure knowledge graph
  evidence     run the collectors the knowledge entry demands (agents/evidence.py)
  analyze()    failure-type specific analysis -> facts, metrics, recovery options
  assemble()   confidence + the diagnosis record the UI renders

Recovery options are computed from live state (balances, other verified
accounts, mandate limits), so the same partner code can lead to different
plans for different users - or for the same user an hour later.
"""
import math

from app.agents import catalog
from app.agents.context import hours_until
from app.database import db
from app.knowledge import retrieval
from app.partners import connectors
from app.services.fmt import inr

SAFETY_BUFFER = 1000.0


def _option(action_type, title, description, params=None, recommended=False):
    return {"id": f"opt-{action_type}", "action_type": action_type, "title": title, "description": description,
            "params": params or {}, "recommended": recommended, "effects": catalog.ACTIONS[action_type]}


def _recommend(options: list[dict], action_type: str) -> list[dict]:
    for o in options:
        o["recommended"] = o["action_type"] == action_type
    return options


# ------------------------------------------------------------------ perceive / knowledge
def perceive(ctx: dict) -> dict:
    j = ctx["journey"]
    snap = connectors.call(j["partner_id"], "get_journey", journey_id=j["id"], ref=j["partner_ref"])
    pdiag = connectors.call(j["partner_id"], "diagnose", journey_id=j["id"], ref=j["partner_ref"])
    return {"snap": snap, "pdiag": pdiag}


def knowledge(partner_id: str, code: str | None) -> dict | None:
    return retrieval.lookup_code(partner_id, code) if code else None


def learned_stats(partner_id: str, code: str) -> dict | None:
    row = db.query_one("SELECT * FROM failure_patterns WHERE id=?", (f"{partner_id}:{code}",))
    if not row or not row["occurrences"]:
        return None
    return {"occurrences": row["occurrences"], "resolved": row["resolved"],
            "success_rate": round(row["resolved"] / row["occurrences"], 4), "avg_resolution_s": row["avg_resolution_s"]}


# ------------------------------------------------------------------ analyzers
def _analyze_payment(ctx, ev, pdiag):
    by = {e["key"]: e for e in ev}
    required = by["installment_amount"]["value"]
    available = by["mandate_account_balance"]["value"]
    target = ctx["linked_account"]
    shortfall = round(max(required - available, 0), 2)
    facts = [
        {"label": "Installment", "value": inr(required), "source": by["installment_amount"]["source"]},
        {"label": "Available now", "value": inr(available), "source": by["mandate_account_balance"]["source"]},
        {"label": "Shortfall", "value": inr(shortfall), "source": "Computed by Saarthi", "emphasis": True},
    ]
    used = pdiag.get("representments_used", 0)
    allowed = pdiag.get("representments_allowed", 3)
    options, recommended = [], None
    if shortfall == 0:
        options.append(_option(
            "retry_debit", f"Retry the {inr(required)} debit now",
            f"Your {target['bank']} {target['masked']} balance ({inr(available)}) now covers the installment, so "
            f"Saarthi can ask {ctx['partner']['name']} to re-present it ({allowed - used} retries left).",
            {"amount": required}))
        recommended = "retry_debit"
    sources = sorted([a for a in ctx["accounts"] if a["id"] != target["id"] and a["status"] == "VERIFIED"
                      and a["balance"] >= shortfall + SAFETY_BUFFER], key=lambda a: -a["balance"])
    if shortfall > 0 and sources:
        src = sources[0]
        options.append(_option(
            "fund_and_retry", f"Move {inr(shortfall)} from {src['bank']} {src['masked']} and retry",
            f"Transfers exactly the shortfall from your {src['bank']} account (balance {inr(src['balance'])}) to "
            f"{target['bank']} {target['masked']}, then asks the bank to re-present the {inr(required)} debit.",
            {"source_account": src["id"], "target_account": target["id"], "amount": shortfall,
             "source_label": f"{src['bank']} {src['masked']}", "target_label": f"{target['bank']} {target['masked']}",
             "source_balance": src["balance"]}))
        recommended = recommended or "fund_and_retry"
    options.append(_option(
        "remind_before_window", "Watch the balance and remind me",
        "No money moves. Saarthi notes the shortfall, and the debit can be retried once the account is topped up.",
        {"shortfall": shortfall}))
    recommended = recommended or "remind_before_window"
    no_source_note = "" if sources or shortfall == 0 else \
        f" None of your other verified accounts can cover {inr(shortfall)} plus a {inr(SAFETY_BUFFER)} buffer."
    return {
        "confirmed": True, "facts": facts, "options": _recommend(options, recommended),
        "metrics": {"required": required, "available": available, "shortfall": shortfall,
                    "representments_used": used, "representments_allowed": allowed},
        "missing": [] if shortfall == 0 or sources else [f"{inr(shortfall)} more in {target['bank']} {target['masked']}"],
        "headline": f"Your {inr(required)} SIP installment didn't go through",
        "summary": (f"{ctx['partner']['name']} returned the debit because {target['bank']} {target['masked']} had "
                    f"{inr(available)}, which is {inr(shortfall)} short of the {inr(required)} installment."
                    if shortfall else
                    f"{ctx['partner']['name']} returned the debit for insufficient funds, but the account now holds "
                    f"{inr(available)}, which is enough to retry.") + no_source_note,
        "safety_note": "Your SIP and its autopay mandate are still active and no money left your account. "
                       f"The bank allows {allowed - used} more re-presentation{'s' if allowed - used != 1 else ''}.",
    }


def _analyze_mandate_limit(ctx, ev, pdiag):
    by = {e["key"]: e for e in ev}
    amount = by["installment_amount"]["value"]
    limit = by["mandate_limit"]["value"]
    available = by["mandate_account_balance"]["value"]
    acc = ctx["linked_account"]
    confirmed = limit is not None and amount > limit
    new_limit = float(math.ceil(amount / 1000) * 1000)
    funds_ok = available >= amount
    facts = [
        {"label": "SIP amount", "value": inr(amount), "source": by["installment_amount"]["source"]},
        {"label": "Autopay limit", "value": inr(limit), "source": by["mandate_limit"]["source"]},
        {"label": "Over the limit by", "value": inr(max(amount - limit, 0)), "source": "Computed by Saarthi",
         "emphasis": True},
    ]
    options = [
        _option("raise_mandate_limit_and_retry", f"Raise autopay limit to {inr(new_limit)} and retry",
                f"Amends mandate {ctx['mandate']['umrn']} from {inr(limit)} to {inr(new_limit)}, then asks "
                f"{ctx['partner']['name']} to re-present the {inr(amount)} installment."
                + ("" if funds_ok else f" Note: {acc['bank']} {acc['masked']} holds only {inr(available)}, so the "
                                        "retry may still need a top-up."),
                {"umrn": ctx["mandate"]["umrn"], "mandate_id": ctx["mandate"]["id"], "old_limit": limit,
                 "new_limit": new_limit, "amount": amount}),
    ]
    if ctx["fund"] and limit >= ctx["fund"]["min_sip"]:
        fit = float(math.floor(limit / 100) * 100)
        options.append(_option("reduce_sip_to_limit", f"Change the SIP to {inr(fit)} and retry",
                               f"Keeps your existing {inr(limit)} autopay limit and brings the SIP back to {inr(fit)}.",
                               {"new_amount": fit, "old_amount": amount}))
    return {
        "confirmed": confirmed, "facts": facts,
        "options": _recommend(options, "raise_mandate_limit_and_retry"),
        "metrics": {"amount": amount, "limit": limit, "new_limit": new_limit, "available": available},
        "missing": [] if funds_ok else [f"{inr(amount - available)} more in {acc['bank']} {acc['masked']}"],
        "headline": "Your SIP is bigger than the autopay limit you approved",
        "summary": f"You raised the SIP to {inr(amount)}, but the autopay mandate only allows debits up to "
                   f"{inr(limit)}, so {ctx['partner']['name']} refused the debit before checking your balance.",
        "safety_note": "No money left your account and your SIP is still active. The limit can be raised in one step.",
    }


def _analyze_name(ctx, ev, pdiag):
    by = {e["key"]: e for e in ev}
    m = by["name_similarity"]["value"]
    acc = ctx["linked_account"]
    ownership = ctx["journey"]["state"].get("aa_ownership")
    pan_mismatch = ownership == "PAN_MISMATCH"
    benign = m["verdict"] == "partial" and not pan_mismatch
    facts = [
        {"label": "Name on PAN", "value": by["pan_name"]["value"], "source": by["pan_name"]["source"]},
        {"label": "Name at bank", "value": by["bank_record_name"]["value"] or "—",
         "source": by["bank_record_name"]["source"]},
        {"label": "Match score", "value": f"{m['score']:.2f} / 0.85 needed", "source": "Saarthi name matcher",
         "emphasis": True},
    ]
    if pan_mismatch:
        facts.append({"label": "PAN at bank", "value": "Different PAN", "source": "Account Aggregator",
                      "emphasis": True})
    options = []
    if not pan_mismatch:
        options.append(_option(
            "verify_ownership_via_aa", "Prove ownership with Account Aggregator",
            f"With your one-time consent, Saarthi asks {acc['bank']} (via Account Aggregator) which PAN is linked to "
            f"{acc['masked']}. If it's your PAN, the account is verified even though the name is written differently.",
            {"account_id": acc["id"], "account_label": f"{acc['bank']} {acc['masked']}"}))
    options.append(_option(
        "escalate_to_specialist", "Hand over to a verification specialist",
        "A specialist reviews the account with you. Saarthi sends everything it checked so you don't repeat anything."))
    reasons = ", ".join(r.lower() for r in m["reasons"]) or "names differ"
    if pan_mismatch:
        summary = (f"{acc['bank']} confirmed that {acc['masked']} is registered to a different PAN. Mutual fund "
                   "payments must come from your own account, so Saarthi can't verify it automatically.")
    elif benign:
        summary = (f"{acc['bank']} has the account under '{by['bank_record_name']['value']}', while your PAN says "
                   f"'{by['pan_name']['value']}' ({reasons}). This looks like a formatting difference, but ownership "
                   "has to be proven before autopay can use this account.")
    else:
        summary = (f"{acc['bank']} has the account under '{by['bank_record_name']['value']}', which doesn't match "
                   f"your PAN name '{by['pan_name']['value']}'. It may belong to someone else, so Saarthi won't "
                   "verify it automatically.")
    return {
        "confirmed": benign, "risk_signal": not benign, "facts": facts,
        "options": _recommend(options, "verify_ownership_via_aa" if benign else "escalate_to_specialist"),
        "name_match": m, "metrics": {"score": m["score"], "verdict": m["verdict"], "ownership_check": ownership},
        "missing": ["Proof that the account is linked to your PAN"] if not pan_mismatch else [],
        "headline": f"{acc['bank']} {acc['masked']} couldn't be verified",
        "summary": summary,
        "safety_note": "Nothing was debited except the Re 1 test credit the bank sent you. Your other accounts and "
                       "investments are unaffected.",
    }


ANALYZERS = {"PAYMENT_FAILURE": _analyze_payment, "MANDATE_LIMIT": _analyze_mandate_limit,
             "ACCOUNT_VERIFICATION": _analyze_name}


def analyze(failure_type: str, ctx: dict, ev: list[dict], pdiag: dict) -> dict:
    return ANALYZERS[failure_type](ctx, ev, pdiag)


def confidence(ev: list[dict], analysis: dict, stats: dict | None) -> float:
    verified = [e for e in ev if e["verified"]]
    coverage = len(verified) / len(ev) if ev else 0
    return round(0.5 * coverage + 0.3 * (1 if analysis["confirmed"] else 0) +
                 0.2 * (stats["success_rate"] if stats else 0.5), 2)


def assemble(ctx, perceived, kb, ev, analysis, knowledge_hits) -> dict:
    j = ctx["journey"]
    snap, pdiag = perceived["snap"], perceived["pdiag"]
    norm = snap["normalized"]
    code = norm["raw_code"]
    k = kb["data"]
    stats = learned_stats(j["partner_id"], code)
    conf = confidence(ev, analysis, stats)
    steps = [
        {"id": "decode", "label": "Partner status decoded", "passed": True,
         "detail": f"{norm['partner_name']} returned {code}"},
        {"id": "map", "label": "Partner failure mapped", "passed": True,
         "detail": f"{code} → {k['standard_code']} ({k['meaning']})"},
        *[{"id": f"ev-{e['key']}", "label": f"{e['label']} verified" if e["verified"] else f"{e['label']} unverified",
           "passed": e["verified"], "detail": f"{e['display']} · {e['source']}"} for e in ev],
        {"id": "cause", "label": "Root cause confirmed" if analysis["confirmed"] else "Root cause ambiguous",
         "passed": analysis["confirmed"], "detail": k["root_cause"]},
    ]
    return {
        "journey_id": j["id"], "status": "DIAGNOSED", "incident": j["state"].get("incident"),
        "partner": norm, "partner_raw": snap["raw"], "partner_diagnose_raw": pdiag["raw"],
        "partner_endpoints": [snap["endpoint"], pdiag["endpoint"]],
        "normalized": {"partner_code": code, "failure_type": k["failure_type"], "standard_code": k["standard_code"],
                       "meaning": k["meaning"], "root_cause": k["root_cause"],
                       "evidence_required": k["evidence_required"], "retry_allowed": k["retry_allowed"],
                       "policy_tier": k["action_tier"], "expected_outcome": k["expected_outcome"],
                       "equivalents": retrieval.equivalent_codes(k["standard_code"])},
        "kb_entry": {"id": kb["id"], "title": kb["title"], "body": kb["body"], "data": k},
        "evidence": ev, "facts": analysis["facts"], "metrics": analysis["metrics"],
        "name_match": analysis.get("name_match"), "risk_signal": analysis.get("risk_signal", False),
        "root_cause_confirmed": analysis["confirmed"], "missing": analysis["missing"],
        "options": analysis["options"], "confidence": conf, "learned": stats,
        "knowledge": knowledge_hits, "steps": steps,
        "headline": analysis["headline"], "summary": analysis["summary"], "safety_note": analysis["safety_note"],
    }


def unmapped(ctx, perceived) -> dict:
    snap = perceived["snap"]
    return {"journey_id": ctx["journey"]["id"], "status": "UNMAPPED", "partner": snap["normalized"],
            "partner_raw": snap["raw"], "confidence": 0.2, "steps": [], "options": [], "evidence": [],
            "knowledge": [], "headline": "Saarthi couldn't map this partner status",
            "summary": "This partner code isn't in Saarthi's knowledge base yet, so it needs a human."}
