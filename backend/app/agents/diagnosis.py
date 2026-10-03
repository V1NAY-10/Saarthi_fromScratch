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


def _by(ev):
    return {e["key"]: e for e in ev}


def _escalate_option(desc="A specialist reviews the case with you. Saarthi sends everything it checked."):
    return _option("escalate_to_specialist", "Hand over to a specialist", desc)


def _analyze_document(ctx, ev, pdiag, k):
    """Any document rule: period, recency, readability, type, presence, income, salary credits."""
    from app.services import doccheck, docintel
    by = _by(ev)
    req = by["document_requirement"]["value"]
    dt, rule, chk = req["doc_type"], req["rule"], req["check"]
    att = by["attached_document"]["value"]
    cands = by["vault_candidates"]["value"] or []
    label = docintel.TYPE_LABEL.get(dt, "identity document").lower() if dt != "IDENTITY" else "identity document"
    partner = ctx["partner"]["name"]
    if not chk and att:  # partner didn't say which check: evaluate ourselves
        issues = doccheck.evaluate(dt, rule, att, ctx["user"], ctx.get("application"))
        chk = {"required": issues[0]["required"], "found": issues[0]["found"]} if issues else {}
    required, found = chk.get("required") or doccheck.describe(dt, rule), chk.get("found") or "—"
    usable = [c for c in cands if c["ok"] and not c["already_submitted"]]
    risky = k["failure_type"] in ("STATEMENT_REJECTED",) and att and (att.get("checks") or {}).get("name_verdict") == "different"
    facts = [
        {"label": "Partner requires", "value": required, "source": f"{partner} rule · knowledge base"},
        {"label": "Your document", "value": found,
         "source": f"{att['name']} v{att['version']} · document intelligence" if att else "Application"},
        {"label": "Result", "value": k["customer_meaning"], "source": "Computed by Saarthi", "emphasis": True},
    ]
    options = []
    allowed = set(k["resolution_options"])
    if usable and not risky and "submit_existing_document" in allowed:
        u = usable[0]
        options.append(_option("submit_existing_document", f"Submit {u['name']} v{u['version']} from your vault",
                               f"{u['summary']}. It satisfies {partner}'s rule ({required}). Saarthi submits this exact "
                               "version to the partner and checks the result.",
                               {"role": chk.get("role") or doccheck.role_for(dt), "document_id": u["document_id"],
                                "version_id": u["version_id"], "label": f"{u['name']} v{u['version']}",
                                "summary": u["summary"], "doc_type": dt, "partner": partner}))
    if not risky and "request_document_upload" in allowed:
        options.append(_option("request_document_upload", f"Upload a {label} that meets the rule",
                               f"Saarthi waits for you to add a {label} ({required}) to your vault, checks it against "
                               f"{partner}'s rule, then asks before submitting it.",
                               {"doc_type": dt, "role": chk.get("role") or doccheck.role_for(dt), "requirement": required}))
    options.append(_escalate_option())
    kinds = [o["action_type"] for o in options]
    rec = next(t for t in ("submit_existing_document", "request_document_upload", "escalate_to_specialist") if t in kinds)
    vault_line = (f" I found {usable[0]['summary']} in your vault, which satisfies the rule." if rec == "submit_existing_document"
                  else " None of the documents in your vault satisfy it yet." if rec == "request_document_upload" else
                  " The name on the document belongs to someone else, so I won't resubmit anything automatically." if risky
                  else " Saarthi won't change what you declared, so a specialist should confirm the details with you.")
    return {
        "confirmed": bool(chk) and not risky and rec != "escalate_to_specialist", "risk_signal": bool(risky), "facts": facts,
        "options": _recommend(options, rec),
        "metrics": {"doc_type": dt, "required": required, "found": found, "usable": len(usable)},
        "document_evidence": {"doc_type": dt, "doc_label": docintel.TYPE_LABEL.get(dt, "Identity document"),
                              "required": required, "found": found, "rule": chk.get("rule"),
                              "submitted": {"name": att["name"], "version": att["version"],
                                            "summary": docintel.summary(att["doc_type"], att["fields"])} if att else None,
                              "candidates": cands},
        "missing": [] if usable else [f"{docintel.TYPE_LABEL.get(dt, 'Identity document')} that meets: {required}"],
        "headline": k["customer_meaning"],
        "summary": f"{partner} couldn't accept your {label}: it requires {required}, but the one submitted has {found}." + vault_line,
        "safety_note": "Your application is on hold, not rejected. Nothing is sent to the partner without your approval.",
    }


def _analyze_identity(ctx, ev, pdiag, k):
    from app.services import doccheck, docintel
    by = _by(ev)
    sub = by["submitted_identity"]["value"] or {}
    kyc = by["kyc_identity"]["value"]
    f, c = sub.get("fields", {}), sub.get("checks", {})
    score = c.get("name_match")
    severe = c.get("pan_match") is False or (score is not None and score < 0.5)
    rule = {"name_match": True, "dob_match": True}
    cands = []
    for d in ctx["vault"]:
        if d["doc_type"] not in docintel.IDENTITY_TYPES or d["version_id"] == sub.get("version_id"):
            continue
        issues = doccheck.evaluate("IDENTITY", rule, d, ctx["user"])
        cands.append({**{x: d[x] for x in ("document_id", "version_id", "version", "name")},
                      "summary": docintel.summary(d["doc_type"], d["fields"]), "ok": not issues})
    cands.sort(key=lambda x: x["name"].endswith("(registry record)"))
    usable = [x for x in cands if x["ok"]]
    facts = [{"label": "KYC record", "value": f"{kyc['name']} · DOB {kyc['dob']}", "source": "PAN registry (KYC)"},
             {"label": "On the document", "value": f"{f.get('name', '—')} · DOB {f.get('dob', '—')}",
              "source": f"{sub.get('doc', 'Submitted document')} · document intelligence"},
             {"label": "Mismatch", "value": k["customer_meaning"], "source": "Computed by Saarthi", "emphasis": True}]
    options = []
    if usable and not severe:
        u = usable[0]
        options.append(_option("submit_existing_document", f"Submit {u['name']} v{u['version']} instead",
                               f"{u['summary']} matches your KYC record. Saarthi never edits identity data; it only "
                               "submits a document that already matches.",
                               {"role": sub.get("role", "identity"), "document_id": u["document_id"],
                                "version_id": u["version_id"], "label": f"{u['name']} v{u['version']}",
                                "summary": u["summary"], "doc_type": "IDENTITY", "partner": ctx["partner"]["name"]}))
    options.append(_escalate_option("A verification specialist confirms your identity. Saarthi never edits a name, "
                                    "date of birth or PAN."))
    return {
        "confirmed": not severe and bool(usable), "risk_signal": severe, "facts": facts,
        "options": _recommend(options, "submit_existing_document" if usable and not severe else "escalate_to_specialist"),
        "metrics": {"name_score": score, "dob_match": c.get("dob_match"), "pan_match": c.get("pan_match")},
        "missing": [] if usable else ["An identity document that matches your KYC record"],
        "headline": "High-risk identity mismatch" if severe else k["customer_meaning"],
        "summary": ("The identity on the submitted document doesn't belong to you, so automatic action is blocked."
                    if severe else f"The submitted document shows {f.get('name', '—')} / {f.get('dob', '—')}, but your "
                    f"KYC record is {kyc['name']} / {kyc['dob']}."
                    + (f" I found {usable[0]['summary']} in your vault that matches." if usable else
                       " No document in your vault matches your KYC record.")),
        "safety_note": "Saarthi never changes identity information. Your KYC record is unchanged.",
    }


def _analyze_transient(ctx, ev, pdiag, k):
    by = _by(ev)
    used = by["retry_history"]["value"]
    norm_code = ctx["journey"]["state"].get("failure_code")
    facts = [{"label": "Partner said", "value": norm_code, "source": f"{ctx['partner']['name']} API"},
             {"label": "Type", "value": "Temporary · safe to retry", "source": "Knowledge base"},
             {"label": "Automatic retries", "value": f"{used} of 2 used", "source": "Saarthi action log", "emphasis": True}]
    options = []
    if used < 2:
        options.append(_option("retry_with_partner", "Retry automatically",
                               "Re-sends the same request. Nothing new is shared and no money moves until the partner "
                               "accepts it, so this is safe to do without asking.", {"attempt": used + 1}))
    options.append(_escalate_option())
    return {"confirmed": True, "facts": facts, "options": _recommend(options, "retry_with_partner" if used < 2 else "escalate_to_specialist"),
            "metrics": {"retries_used": used}, "missing": [],
            "headline": k["customer_meaning"],
            "summary": f"{ctx['partner']['name']} returned a temporary error ({k['customer_meaning'].lower()}). "
                       + ("It is safe to retry, so Saarthi will do it automatically." if used < 2 else
                          "Two automatic retries didn't help, so a person should look at it."),
            "safety_note": "Nothing was charged or shared. A retry repeats the same request."}


def _analyze_monitor(ctx, ev, pdiag, k):
    by = _by(ev)
    mins = by["time_with_partner"]["value"] * 60
    facts = [{"label": "Partner status", "value": k["customer_meaning"], "source": f"{ctx['partner']['name']} API"},
             {"label": "Waiting for", "value": by["time_with_partner"]["display"], "source": "Journey memory"},
             {"label": "Escalate when", "value": k["escalation_conditions"][0], "source": "Knowledge base", "emphasis": True}]
    options = [_option("refresh_status", "Keep checking with the partner",
                       "A read-only status check. Saarthi re-checks automatically and tells you the moment it changes."),
               _escalate_option("Open a support case now with full context.")]
    return {"confirmed": True, "facts": facts, "options": _recommend(options, "refresh_status"),
            "metrics": {"minutes_waiting": round(mins)}, "missing": [], "headline": k["customer_meaning"],
            "summary": f"{ctx['partner']['name']} hasn't finished: {k['customer_meaning'].lower()}. There's nothing to fix "
                       "yet, so Saarthi monitors the partner and escalates if it takes too long.",
            "safety_note": "No action is needed from you right now."}


def _analyze_human_only(ctx, ev, pdiag, k):
    facts = [{"label": "Partner said", "value": ctx["journey"]["state"].get("failure_code"), "source": f"{ctx['partner']['name']} API"},
             {"label": "Meaning", "value": k["customer_meaning"], "source": "Knowledge base"},
             {"label": "Automation", "value": "Not permitted", "source": "Saarthi policy", "emphasis": True}]
    return {"confirmed": True, "risk_signal": k.get("risk_level") == "high", "facts": facts,
            "options": _recommend([_escalate_option()], "escalate_to_specialist"), "metrics": {}, "missing": [],
            "headline": k["customer_meaning"],
            "summary": f"{ctx['partner']['name']} reported: {k['customer_meaning'].lower()}. This needs a person; "
                       "Saarthi won't override a partner decision or act on an identity risk.",
            "safety_note": "Nothing was changed. A specialist will contact you with the full case file."}


def _analyze_mandate_invalid(ctx, ev, pdiag, k):
    by = _by(ev)
    m = ctx["mandate"]
    amount = by["installment_amount"]["value"]
    acc = ctx["linked_account"]
    new_limit = float(max(amount, m["max_amount"]))
    facts = [{"label": "Mandate", "value": f"{m['umrn']} · {by['mandate_status']['display']}", "source": by["mandate_status"]["source"]},
             {"label": "Installment", "value": inr(amount), "source": by["installment_amount"]["source"]},
             {"label": "Needed", "value": "A new autopay mandate", "source": "Knowledge base", "emphasis": True}]
    options = [_option("create_new_mandate", f"Register a new autopay mandate ({inr(new_limit)} limit) and retry",
                       f"Registers a fresh mandate on {acc['bank']} {acc['masked']} with a {inr(new_limit)} limit, "
                       "then re-presents the installment.", {"account_id": acc["id"], "max_amount": new_limit,
                                                              "old_umrn": m["umrn"], "amount": amount})]
    return {"confirmed": True, "facts": facts, "options": _recommend(options, "create_new_mandate"),
            "metrics": {"amount": amount, "new_limit": new_limit}, "missing": [], "headline": k["customer_meaning"],
            "summary": f"The autopay mandate {m['umrn']} can't be used any more ({k['customer_meaning'].lower()}), so "
                       f"{ctx['partner']['name']} refused the {inr(amount)} debit.",
            "safety_note": "No money left your account. A new mandate needs your approval."}


def _analyze_debit_inference(ctx, ev, pdiag, k):
    """A generic 'recurring debit failed': infer the cause from evidence, or refuse to guess."""
    by = _by(ev)
    amount, bal, limit = by["installment_amount"]["value"], by["mandate_account_balance"]["value"], by["mandate_limit"]["value"]
    if limit is not None and amount > limit:
        out = _analyze_mandate_limit(ctx, ev, pdiag)
        out["summary"] = "The bank gave no reason, but the evidence explains it: " + out["summary"][0].lower() + out["summary"][1:]
        return out
    if bal < amount:
        out = _analyze_payment(ctx, ev, pdiag)
        out["summary"] = "The bank gave no reason, but the evidence explains it: " + out["summary"]
        return out
    facts = [{"label": "Balance", "value": inr(bal), "source": by["mandate_account_balance"]["source"]},
             {"label": "Installment", "value": inr(amount), "source": by["installment_amount"]["source"]},
             {"label": "Autopay limit", "value": inr(limit), "source": by["mandate_limit"]["source"], "emphasis": True}]
    return {"confirmed": False, "facts": facts, "options": _recommend([_escalate_option()], "escalate_to_specialist"),
            "metrics": {"amount": amount, "balance": bal, "limit": limit},
            "missing": ["The bank's actual reason for the return"], "headline": "Saarthi couldn't confirm why the debit failed",
            "summary": "The bank returned a generic failure, and neither the balance nor the autopay limit explains it. "
                       "Saarthi won't guess, so a specialist should check with the bank.",
            "safety_note": "No money left your account."}


def _analyze_payment_retry(ctx, ev, pdiag, k):
    by = _by(ev)
    due, bal = by["payment_amount"]["value"], by["paying_account_balance"]["value"]
    acc = ctx["linked_account"]
    short = round(max(due - bal, 0), 2)
    sources = sorted([a for a in ctx["accounts"] if a["id"] != acc["id"] and a["status"] == "VERIFIED"
                      and a["balance"] >= short + SAFETY_BUFFER], key=lambda a: -a["balance"])
    options = []
    if short == 0:
        options.append(_option("retry_payment", f"Pay {inr(due)} from {acc['bank']} {acc['masked']} now",
                               f"The account now holds {inr(bal)}. Saarthi asks {ctx['partner']['name']} to collect the premium again.",
                               {"amount": due}))
    elif sources:
        src = sources[0]
        options.append(_option("fund_and_retry_payment", f"Move {inr(short)} from {src['bank']} {src['masked']} and pay",
                               f"Transfers exactly the shortfall from your own verified account, then retries the premium.",
                               {"source_account": src["id"], "target_account": acc["id"], "amount": short,
                                "source_label": f"{src['bank']} {src['masked']}", "target_label": f"{acc['bank']} {acc['masked']}",
                                "source_balance": src["balance"]}))
    options.append(_option("remind_before_window", "Remind me to top up", "No money moves.", {"shortfall": short}))
    facts = [{"label": "Premium due", "value": inr(due), "source": by["payment_amount"]["source"]},
             {"label": "Available", "value": inr(bal), "source": by["paying_account_balance"]["source"]},
             {"label": "Shortfall", "value": inr(short), "source": "Computed by Saarthi", "emphasis": True}]
    return {"confirmed": True, "facts": facts, "options": _recommend(options, options[0]["action_type"]),
            "metrics": {"due": due, "available": bal, "shortfall": short}, "missing": [],
            "headline": "Your premium payment didn't go through",
            "summary": f"{ctx['partner']['name']} couldn't collect the {inr(due)} premium from {acc['bank']} {acc['masked']} "
                       f"(balance {inr(bal)}).",
            "safety_note": "Your application is saved. No premium was charged."}


def _analyze_account_unverified(ctx, ev, pdiag, k):
    acc = ctx["linked_account"]
    others = [a for a in ctx["accounts"] if a["status"] == "VERIFIED" and (not acc or a["id"] != acc["id"])]
    options = []
    if others:
        o = others[0]
        options.append(_option("switch_partner_account", f"Use {o['bank']} {o['masked']} instead",
                               f"{o['bank']} {o['masked']} is verified in your name. Saarthi updates the application.",
                               {"account_id": o["id"], "label": f"{o['bank']} {o['masked']}"}))
    options.append(_escalate_option())
    facts = [{"label": "Selected account", "value": f"{acc['bank']} {acc['masked']} · {acc['status'].lower()}" if acc else "None",
              "source": "Application"},
             {"label": "Verified accounts", "value": ", ".join(f"{a['bank']} {a['masked']}" for a in others) or "None",
              "source": "Linked accounts", "emphasis": True}]
    return {"confirmed": True, "facts": facts, "options": _recommend(options, options[0]["action_type"]), "metrics": {},
            "missing": [] if others else ["A verified bank account in your name"], "headline": k["customer_meaning"],
            "summary": f"{ctx['partner']['name']} will only pay out to a verified account in your name, and the selected "
                       "account isn't verified." + (f" {others[0]['bank']} {others[0]['masked']} is." if others else ""),
            "safety_note": "No money was sent anywhere."}


ANALYZERS = {"insufficient_funds": lambda c, e, p, k: _analyze_payment(c, e, p),
             "mandate_limit": lambda c, e, p, k: _analyze_mandate_limit(c, e, p),
             "name_mismatch": lambda c, e, p, k: _analyze_name(c, e, p),
             "document_requirement": _analyze_document, "identity_mismatch": _analyze_identity,
             "transient": _analyze_transient, "monitor": _analyze_monitor, "human_only": _analyze_human_only,
             "mandate_invalid": _analyze_mandate_invalid, "debit_inference": _analyze_debit_inference,
             "payment_retry": _analyze_payment_retry, "account_unverified": _analyze_account_unverified}


def analyze(k: dict, ctx: dict, ev: list[dict], pdiag: dict) -> dict:
    return ANALYZERS[k["analyzer"]](ctx, ev, pdiag, k)


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
                       "meaning": k["meaning"], "root_cause": k["root_cause"], "analyzer": k["analyzer"],
                       "risk_level": k.get("risk_level"), "journey_type": k.get("journey_type"),
                       "possible_causes": k.get("possible_causes", []),
                       "escalation_conditions": k.get("escalation_conditions", []),
                       "automatic_action_allowed": k.get("automatic_action_allowed"),
                       "evidence_required": k["evidence_required"], "retry_allowed": k["retry_allowed"],
                       "policy_tier": k["action_tier"], "expected_outcome": k["expected_outcome"],
                       "equivalents": retrieval.equivalent_codes(k["standard_code"])},
        "kb_entry": {"id": kb["id"], "title": kb["title"], "body": kb["body"], "source": kb.get("source"), "data": k},
        "document_evidence": analysis.get("document_evidence"),
        "evidence": ev, "facts": analysis["facts"], "metrics": analysis["metrics"],
        "name_match": analysis.get("name_match"), "risk_signal": analysis.get("risk_signal", False),
        "root_cause_confirmed": analysis["confirmed"], "missing": analysis["missing"],
        "options": analysis["options"], "confidence": conf, "learned": stats,
        "knowledge": knowledge_hits, "steps": steps,
        "headline": analysis["headline"], "summary": analysis["summary"], "safety_note": analysis["safety_note"],
    }


def unmapped(ctx, perceived, rag_hits: list | None = None) -> dict:
    """No knowledge for this code: say so plainly and route to a human. Never guess."""
    snap = perceived["snap"]
    n = snap["normalized"]
    code = n["raw_code"] or "UNKNOWN"
    return {
        "journey_id": ctx["journey"]["id"], "status": "DIAGNOSED", "unknown": True,
        "incident": ctx["journey"]["state"].get("incident"),
        "partner": n, "partner_raw": snap["raw"], "partner_diagnose_raw": perceived["pdiag"]["raw"],
        "partner_endpoints": [snap["endpoint"], perceived["pdiag"]["endpoint"]],
        "normalized": {"partner_code": code, "failure_type": "UNKNOWN", "standard_code": "UNKNOWN",
                       "meaning": "Unrecognised partner code", "root_cause": "Not in Saarthi's knowledge base",
                       "analyzer": None, "risk_level": "high", "evidence_required": [], "retry_allowed": False,
                       "policy_tier": "TIER_3", "expected_outcome": "A specialist identifies the issue",
                       "possible_causes": [], "escalation_conditions": ["Always"], "equivalents": []},
        "kb_entry": None, "evidence": [],
        "facts": [{"label": "Partner", "value": n["partner_name"], "source": "Partner API"},
                  {"label": "Code", "value": code, "source": "Partner API"},
                  {"label": "Knowledge found", "value": "None reliable", "source": "Registry + RAG", "emphasis": True}],
        "metrics": {}, "name_match": None, "risk_signal": True, "root_cause_confirmed": False,
        "missing": [f"What {code} means"], "options": [_option("escalate_to_specialist", "Hand over to a specialist",
                                                              "A specialist checks the code with the partner.", recommended=True)],
        "confidence": 0.0, "learned": None, "knowledge": rag_hits or [], "steps": [],
        "headline": "Saarthi couldn't confidently identify this issue",
        "summary": f"{n['partner_name']} returned {code}, which isn't in Saarthi's knowledge base, and retrieval found "
                   "nothing reliable about it. Saarthi won't guess a fix; this needs human review.",
        "safety_note": "No action was taken on your account.",
    }
