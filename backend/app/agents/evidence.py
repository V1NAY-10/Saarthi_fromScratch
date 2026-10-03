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


COLLECTORS = {f.__name__: f for f in [mandate_account_balance, installment_amount, mandate_status, mandate_limit,
                                      pan_name, bank_record_name, name_similarity]}


def collect(keys: list[str], ctx: dict, partner_raw: dict, partner_diag: dict) -> list[dict]:
    out = []
    for k in keys:
        fn = COLLECTORS.get(k)
        out.append(fn(ctx, partner_raw, partner_diag) if fn else _ev(k, k, None, "No collector", "—", verified=False))
    return out
