"""Evidence collectors. The knowledge base says *which* evidence a partner code
requires; each collector fetches it from the system of record or the partner's
own response and states its source, so every number Saarthi shows is traceable."""
from app.services import namematch
from app.services.fmt import inr


def _ev(key, label, value, display, source, verified=True, note=None):
    return {"key": key, "label": label, "value": value, "display": display, "source": source,
            "verified": verified, "note": note}


def _partner_amount(raw: dict) -> float | None:
    v = raw.get("amount")
    return float(v) if v is not None else None


def mandate_account_balance(ctx, raw, pdiag):
    acc = ctx["linked_account"]
    if not acc:
        return _ev("mandate_account_balance", "Available balance", None, "Unavailable", "—", verified=False)
    return _ev("mandate_account_balance", "Available balance", acc["balance"], inr(acc["balance"]),
               f"{acc['bank']} {acc['masked']} · live balance")


def installment_amount(ctx, raw, pdiag):
    presented = _partner_amount(raw)
    sip_amt = ctx["sip"]["amount"] if ctx["sip"] else ctx["journey"]["amount"]
    if presented is None:
        presented = sip_amt
    agrees = abs(presented - sip_amt) < 0.01
    return _ev("installment_amount", "Installment amount", presented, inr(presented),
               f"{ctx['partner']['name']} presentment · matches SIP registry" if agrees else "Partner presentment",
               verified=agrees, note=None if agrees else f"SIP registry says {inr(sip_amt)}")


def mandate_status(ctx, raw, pdiag):
    st = pdiag.get("mandate_status") or (ctx["mandate"] or {}).get("status")
    return _ev("mandate_status", "Autopay mandate", st, (st or "Unknown").title(),
               f"UMRN {(ctx['mandate'] or {}).get('umrn', '—')} · {ctx['partner']['name']}", verified=st == "ACTIVE",
               note=None if st == "ACTIVE" else "Mandate not active")


def mandate_limit(ctx, raw, pdiag):
    lim = pdiag.get("mandate_max") if pdiag.get("mandate_max") is not None else (ctx["mandate"] or {}).get("max_amount")
    return _ev("mandate_limit", "Autopay limit", lim, inr(lim) if lim is not None else "—",
               f"{ctx['partner']['name']} mandate record", verified=lim is not None)


def pan_name(ctx, raw, pdiag):
    doc = next((d for d in ctx["documents"] if d["doc_type"] == "PAN"), None)
    name = ctx["user"]["name"]
    return _ev("pan_name", "Name on PAN", name, name, "PAN registry (KYC)",
               verified=bool(doc and doc["status"] == "VERIFIED"))


def bank_record_name(ctx, raw, pdiag):
    name = raw.get("beneName") or (raw.get("beneficiary") or {}).get("name") or pdiag.get("name_on_record")
    return _ev("bank_record_name", "Name on bank record", name, name or "—",
               f"{ctx['partner']['name']} penny drop response", verified=bool(name))


def name_similarity(ctx, raw, pdiag):
    a = (raw.get("beneName") or (raw.get("beneficiary") or {}).get("name") or pdiag.get("name_on_record") or "")
    m = namematch.score(a, ctx["user"]["name"])
    return _ev("name_similarity", "Name match", m, f"{m['score']:.2f} · {m['verdict']}",
               "Saarthi name matcher (token-level)", note="; ".join(m["reasons"]))


# ------------------------------------------------------------------ application journeys
def _target(ctx, pdiag):
    """Which document requirement failed: the partner's diagnose response says so."""
    chk = (pdiag or {}).get("check") or {}
    dt = chk.get("doc_type")
    if not dt:
        kb_req = (ctx.get("kb_entry") or {}).get("requirement") or {}
        dt = kb_req.get("doc_type")
    rule = {**((ctx.get("kb_entry") or {}).get("requirement") or {}), **(ctx["requirements"].get(dt) or {})}
    rule.pop("doc_type", None)
    return dt, rule, chk


def document_requirement(ctx, raw, pdiag):
    from app.services import doccheck
    dt, rule, chk = _target(ctx, pdiag)
    label = doccheck.describe(dt, rule) if dt else "Unknown requirement"
    return _ev("document_requirement", "Partner requirement", {"doc_type": dt, "rule": rule, "check": chk}, label,
               f"{ctx['partner']['name']} published rule (knowledge base)", verified=bool(dt))


def attached_document(ctx, raw, pdiag):
    from app.services import docintel
    dt, rule, chk = _target(ctx, pdiag)
    role = chk.get("role") or (dt or "").lower()
    a = ctx["attached"].get(role)
    if not a:
        return _ev("attached_document", "Submitted document", None, "Nothing attached", "Application", verified=True,
                   note="Required document was not attached")
    fields = {k: v for k, v in a["fields"].items() if not k.startswith("_")}
    return _ev("attached_document", "Submitted document", {**a, "fields": fields},
               f"{a['name']} v{a['version']} · {docintel.summary(a['doc_type'], a['fields']) or 'no readable details'}",
               "Document Vault · document intelligence", verified=True)


def vault_candidates(ctx, raw, pdiag):
    from app.services import doccheck, docintel
    dt, rule, chk = _target(ctx, pdiag)
    if not dt:
        return _ev("vault_candidates", "Vault documents", [], "—", "Document Vault", verified=False)
    accepted = doccheck.accepted_types(dt, rule)
    user = ctx["user"]
    attached_vid = (ctx["attached"].get(chk.get("role") or dt.lower()) or {}).get("version_id")
    cands = []
    for d in ctx["vault"]:
        if d["doc_type"] not in accepted:
            continue
        issues = doccheck.evaluate(dt, rule, d, user, ctx.get("application"))
        cands.append({"document_id": d["document_id"], "version_id": d["version_id"], "version": d["version"],
                      "name": d["name"], "summary": docintel.summary(d["doc_type"], d["fields"]), "ok": not issues,
                      "issues": [i["message"] for i in issues], "already_submitted": d["version_id"] == attached_vid})
    cands.sort(key=lambda c: (c["name"].endswith("(registry record)"), -c["version"]))  # uploaded files first
    usable = [c for c in cands if c["ok"] and not c["already_submitted"]]
    return _ev("vault_candidates", "Vault documents checked", cands,
               f"{len(cands)} checked · {len(usable)} satisfy the rule", "Document Vault (journey memory)")


def kyc_identity(ctx, raw, pdiag):
    u = ctx["user"]
    return _ev("kyc_identity", "KYC identity", {"name": u["name"], "dob": u["dob"], "pan_masked": u["pan"][:5] + "••••" + u["pan"][-1]},
               f"{u['name']} · DOB {u['dob']}", "PAN registry (KYC)", verified=u["kyc_status"] == "VERIFIED")


def submitted_identity(ctx, raw, pdiag):
    chk = (pdiag or {}).get("check") or {}
    role = chk.get("role") or next(iter(ctx["attached"]), None)
    a = ctx["attached"].get(role) if role else None
    if not a:
        return _ev("submitted_identity", "Submitted identity", None, "Nothing attached", "Application", verified=False)
    f = {k: v for k, v in a["fields"].items() if not k.startswith("_")}
    c = a["checks"]
    return _ev("submitted_identity", "Submitted identity document", {"doc": a["name"], "version_id": a["version_id"],
                                                                     "fields": f, "checks": c, "role": role},
               f"{a['name']}: {f.get('name', '—')} · DOB {f.get('dob', '—')}", "Document Vault · document intelligence")


def partner_status(ctx, raw, pdiag):
    st = raw.get("status")
    code = raw.get("respCode") or raw.get("reasonCode") or (st.get("code") if isinstance(st, dict) else None)
    return _ev("partner_status", "Partner status", raw, f"{ctx['partner']['name']} · {code or 'no code'}",
               "Partner API (live)")


def retry_history(ctx, raw, pdiag):
    n = sum(1 for a in ctx["previous_actions"] if a["action_type"] == "retry_with_partner")
    return _ev("retry_history", "Automatic retries this incident", n, f"{n} of 2 used", "Saarthi action log",
               note="Retry budget exhausted" if n >= 2 else None)


def time_with_partner(ctx, raw, pdiag):
    from app.agents.context import hours_since
    h = hours_since(ctx["journey"]["state"].get("incident_started_at")) or 0
    return _ev("time_with_partner", "Waiting on partner", round(h, 2), f"{h * 60:.0f} min" if h < 1 else f"{h:.1f} h",
               "Journey memory")


def paying_account_balance(ctx, raw, pdiag):
    return mandate_account_balance(ctx, raw, pdiag) | {"key": "paying_account_balance"}


def payment_amount(ctx, raw, pdiag):
    amt = ((pdiag or {}).get("check") or {}).get("premium") or ctx["journey"]["amount"]
    return _ev("payment_amount", "Amount due", amt, inr(amt), f"{ctx['partner']['name']} premium schedule")


def paying_account(ctx, raw, pdiag):
    a = ctx["linked_account"]
    return _ev("paying_account", "Selected account", a and {"id": a["id"], "status": a["status"]},
               f"{a['bank']} {a['masked']} · {a['status'].lower()}" if a else "None", "Application")


def verified_accounts(ctx, raw, pdiag):
    v = [a for a in ctx["accounts"] if a["status"] == "VERIFIED"]
    return _ev("verified_accounts", "Verified accounts", [{"id": a["id"], "label": f"{a['bank']} {a['masked']}"} for a in v],
               ", ".join(f"{a['bank']} {a['masked']}" for a in v) or "None", "Linked accounts")


COLLECTORS = {f.__name__: f for f in [mandate_account_balance, installment_amount, mandate_status, mandate_limit,
                                      pan_name, bank_record_name, name_similarity, document_requirement,
                                      attached_document, vault_candidates, kyc_identity, submitted_identity,
                                      partner_status, retry_history, time_with_partner, paying_account_balance,
                                      payment_amount, paying_account, verified_accounts]}


def collect(keys: list[str], ctx: dict, partner_raw: dict, partner_diag: dict) -> list[dict]:
    out = []
    for k in keys:
        fn = COLLECTORS.get(k)
        out.append(fn(ctx, partner_raw, partner_diag) if fn else _ev(k, k, None, "No collector", "—", verified=False))
    return out
