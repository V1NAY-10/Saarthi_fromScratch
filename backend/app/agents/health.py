"""Journey Health Score - deterministic, explainable.

score = clamp(50 + sum(factor impacts), 0, 100)

Each factor is a rule over the journey's live state, diagnosis and decision.
The factors are returned with the score so the user can open 'Why is my
Journey Health 37?' and see exactly what moved it."""
from app.agents.context import hours_since
from app.services.fmt import inr

BASE = 50


def band(score: int) -> dict:
    if score >= 85:
        return {"key": "healthy", "label": "On track"}
    if score >= 60:
        return {"key": "watch", "label": "Needs a nudge"}
    if score >= 35:
        return {"key": "risk", "label": "At risk"}
    return {"key": "critical", "label": "Critical"}


def compute(ctx: dict, diag: dict | None = None, decision: dict | None = None) -> dict:
    j = ctx["journey"]
    s = j["state"]
    f = []

    def add(key, label, impact, detail=""):
        f.append({"key": key, "label": label, "impact": impact, "detail": detail})

    status = j["status"]
    acc = ctx["linked_account"]
    active_issue = status == "ATTENTION" and diag and diag.get("status") == "DIAGNOSED"

    if active_issue:
        ft = diag["normalized"]["failure_type"]
        m = diag.get("metrics", {})
        if ft == "PAYMENT_FAILURE":
            add("payment_failed", "Installment failed", -30, diag["partner"]["raw_code"])
            if m.get("shortfall", 0) > 0:
                add("shortfall", "Funds shortfall", -20, f"{inr(m['shortfall'])} short in autopay account")
        elif ft == "MANDATE_LIMIT":
            add("payment_failed", "Installment failed", -30, diag["partner"]["raw_code"])
            add("limit", "SIP above autopay limit", -15, f"{inr(m.get('amount', 0))} vs limit {inr(m.get('limit', 0))}")
        elif ft == "ACCOUNT_VERIFICATION":
            add("unverified", "Bank account not verified", -25, diag["partner"]["raw_code"])
            if diag.get("risk_signal"):
                add("risk", "Account may not belong to you", -15, "Name/PAN mismatch")
        if decision and decision.get("tier") in ("TIER_1", "TIER_2"):
            add("recovery", "Safe recovery path available", +20, decision.get("tier_label", ""))
    elif status == "ATTENTION":
        add("investigating", "Saarthi is investigating", -20, "Diagnosis in progress")
    elif status == "RESOLVED":
        add("recovered", "Recovered & verified with partner", +25, s.get("bank_ref") or "")
    elif status == "ESCALATED":
        add("specialist", "Specialist assigned with full context", +20, s.get("case_id") or "")
        add("pending", "Waiting on human review", -20, "")
    elif status in ("ON_TRACK", "COMPLETE"):
        add("on_track", "Progressing normally", +25, j["stage"])

    if ctx["user"]["kyc_status"] == "VERIFIED":
        add("identity", "KYC verified", +10, "PAN registry")
    if acc and acc["status"] == "VERIFIED" and j["category"] == "investment":
        add("account_ok", "Autopay account verified", +5, f"{acc['bank']} {acc['masked']}")
    if j["category"] == "investment" and status in ("ON_TRACK", "RESOLVED") and ctx["sip"] and acc:
        sip, man = ctx["sip"], ctx["mandate"]
        if acc["balance"] < sip["amount"]:
            add("next_not_covered", "Next installment not covered", -10,
                f"{acc['bank']} {acc['masked']} has {inr(acc['balance'])}, next debit {inr(sip['amount'])}")
        if man and sip["amount"] > man["max_amount"]:
            add("over_limit", "SIP above autopay limit", -15,
                f"{inr(sip['amount'])} vs limit {inr(man['max_amount'])} — next debit will be refused")
        last_ok = hours_since(s.get("last_success_at"))
        if sip["installments_paid"] and (last_ok is None or last_ok < 24 * 40):
            add("recent_success", "Recent successful installment", +5, f"{sip['installments_paid']} paid so far")

    score = max(0, min(100, BASE + sum(x["impact"] for x in f)))
    return {"score": score, "base": BASE, "band": band(score), "factors": f}
