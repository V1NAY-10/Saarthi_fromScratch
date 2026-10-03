"""Decision + Safety Engine - deterministic tiered autonomy.

The LLM never decides what Saarthi may do. Tiers are computed from auditable
checks over the diagnosis, the action catalog and partner policy:

  TIER_1_AUTO      safe, verified, reversible, no money moved, no new data shared
  TIER_2_APPROVAL  possible, but moves money / shares data / changes terms -> explicit user approval
  TIER_3_ESCALATE  ambiguous, risky, unverified or irreversible -> human support
"""
from app.agents import catalog

MIN_CONFIDENCE = 0.75
TIER_RANK = {"TIER_1": 1, "TIER_2": 2, "TIER_3": 3}
TIER_LABEL = {"TIER_1": "Auto action", "TIER_2": "Your approval required", "TIER_3": "Escalate to human support"}

FAIL_TEXT = {
    "evidence": "Required evidence could not be verified",
    "cause": "Root cause is ambiguous",
    "identity": "Customer KYC is not verified",
    "risk": "Risk signal: account may not belong to the investor",
    "confidence": "Diagnosis confidence below the 75% safety threshold",
    "reversible": "Action cannot be undone",
    "funds": "Source account cannot cover the transfer",
}


def _check(cid, label, passed, detail, blocking=True):
    return {"id": cid, "label": label, "passed": passed, "detail": detail, "blocking": blocking}


def _fail_reason(c):
    return FAIL_TEXT.get(c["id"], f"{c['label']} — failed")


def decide(diag: dict, option: dict, ctx: dict) -> dict:
    fx = catalog.ACTIONS[option["action_type"]]
    norm = diag.get("normalized", {})
    risk = bool(diag.get("risk_signal"))
    identity_ok = ctx["user"]["kyc_status"] == "VERIFIED"
    evidence = diag.get("evidence", [])
    conf = diag.get("confidence", 0)

    checks = [
        _check("status", "Partner status identified", bool(diag.get("partner", {}).get("raw_code")),
               f"{diag.get('partner', {}).get('partner_name')}: {diag.get('partner', {}).get('raw_code')}"),
        _check("mapped", "Partner failure mapped", bool(norm),
               f"{norm.get('partner_code')} → {norm.get('standard_code')}" if norm else "Unknown code"),
        *[_check(f"ev-{e['key']}", f"{e['label']} verified", e["verified"], e["display"], blocking=False)
          for e in evidence],
        _check("rule", "Partner rule retrieved", bool(diag.get("kb_entry")), diag.get("kb_entry", {}).get("title", "—")),
        _check("evidence", "Required evidence verified", all(e["verified"] for e in evidence),
               f"{sum(e['verified'] for e in evidence)}/{len(evidence)} verified"),
        _check("cause", "Root cause confirmed", diag.get("root_cause_confirmed", False), norm.get("root_cause", "—")),
        _check("identity", "Customer identity verified", identity_ok,
               "PAN verified (KYC)" if identity_ok else "KYC incomplete"),
        _check("risk", "No risk signal", not risk, "No risk signals" if not risk else "Possible third-party account"),
        _check("confidence", f"Diagnosis confidence ≥ {MIN_CONFIDENCE:.0%}", conf >= MIN_CONFIDENCE, f"{conf:.0%}"),
        _check("recovery", "Recovery path available", option["action_type"] != "escalate_to_specialist",
               option["title"]),
        _check("reversible", "Action is reversible", fx["reversible"],
               "Reversible" if fx["reversible"] else "Cannot be undone automatically"),
    ]
    if option["action_type"] == "fund_and_retry":
        p = option["params"]
        checks.append(_check("funds", "Source account can cover transfer", p.get("source_balance", 0) >= p.get("amount", 0),
                             f"{p.get('source_label')} → {p.get('target_label')}"))

    blocking_fail = [c for c in checks if c["blocking"] and not c["passed"] and c["id"] != "recovery"]
    reasons = []
    if option["action_type"] == "escalate_to_specialist":
        tier = "TIER_3"
        reasons += [_fail_reason(c) for c in blocking_fail]
        reasons.append("Human verification is the safe path")
    elif blocking_fail or fx["changes_identity"] or not fx["reversible"]:
        tier = "TIER_3"
        reasons += [_fail_reason(c) for c in blocking_fail]
        if fx["changes_identity"]:
            reasons.append("Edits identity data")
    elif fx["moves_money"] or fx["shares_data"] or fx["changes_terms"]:
        tier = "TIER_2"
        reasons.append("Moves money" if fx["moves_money"] else "Shares your financial data" if fx["shares_data"]
                       else "Changes your investment terms")
        if fx["changes_terms"] and fx["moves_money"]:
            reasons.append("Changes your mandate or SIP terms")
    else:
        tier = "TIER_1"
        reasons.append("Read-only / reversible, no financial impact")

    # Partner policy is a floor - Saarthi can be stricter than the partner, never looser.
    policy_tier = norm.get("policy_tier")
    impactful = fx["moves_money"] or fx["shares_data"] or fx["changes_terms"]
    if policy_tier and impactful and             option["action_type"] in diag.get("kb_entry", {}).get("data", {}).get("recovery_actions", []):
        if TIER_RANK[policy_tier] > TIER_RANK[tier]:
            reasons.append(f"Partner policy requires {policy_tier}")
            tier = policy_tier

    checks.append(_check("classified", "Action classified", True, f"{tier} · {TIER_LABEL[tier]}", blocking=False))
    return {"option_id": option["id"], "action_type": option["action_type"], "tier": tier,
            "tier_label": TIER_LABEL[tier], "checks": checks, "reasons": reasons, "confidence": conf}


def decide_all(diag: dict, ctx: dict, chosen_option_id: str | None = None) -> dict:
    """Classify every recovery option. The primary option is the agent's choice if it
    made a valid one, else the analyzer's recommendation."""
    options = diag.get("options", [])
    decisions = {o["id"]: decide(diag, o, ctx) for o in options}
    primary = next((o for o in options if o["id"] == chosen_option_id), None) or \
        next((o for o in options if o["recommended"]), None)
    return {"by_option": decisions, "primary_option_id": primary["id"] if primary else None,
            "primary": decisions.get(primary["id"]) if primary else None}
