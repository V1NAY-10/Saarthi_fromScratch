"""Application journeys: personal loans, insurance policies and KYC verification.

  start()     creates the journey with the partner's document checklist
  precheck()  Saarthi matches vault documents to each requirement and checks them
              against the partner's published rule (journey memory: upload once,
              reuse everywhere)
  submit()    attaches the chosen document *versions* and sends the application to
              the sandbox partner; a rejection opens an incident for the agent"""
import uuid

from app.database import db
from app.knowledge import registry
from app.partners import connectors
from app.product import journeys, vault
from app.product.journeys import NotFound, ProductError
from app.services import doccheck, docintel, journal
from app.services.fmt import inr

OFFERS = {
    "vistara_finance": {"rate": 13.5, "max_amount": 1000000, "min_income": 25000, "tagline": "Instant decision"},
    "kaveri_bank": {"rate": 11.25, "max_amount": 1500000, "min_income": 30000, "tagline": "Lowest rate"},
    "suraksha_insurance": {"plan": "Family Health Shield", "cover": 1000000, "premium_per_year": 14800,
                           "tagline": "₹10L family floater"},
    "identiverify": {"tagline": "Re-KYC with a document"},
}
KIND_FOR = {"loan": "loan", "insurance": "insurance", "kyc": "kyc"}


def catalog(kind: str) -> list[dict]:
    out = []
    for pid, prof in registry.load()["profiles"].items():
        if prof["journey_type"] != kind:
            continue
        reqs = doccheck.ordered(prof["requirements"], {"age": 99})
        out.append({"partner_id": pid, "name": prof["partner_name"], "product": prof["product"], **OFFERS.get(pid, {}),
                    "requirements": [{"doc_type": dt, "label": doccheck.describe(dt, r)} for dt, r in reqs]})
    return out


def _emi(amount: float, rate: float, months: int) -> float:
    r = rate / 1200
    return round(amount * r * (1 + r) ** months / ((1 + r) ** months - 1), 0)


def start(user: dict, partner_id: str, params: dict) -> dict:
    prof = registry.load()["profiles"].get(partner_id)
    if not prof:
        raise ProductError("Unknown partner.")
    kind = prof["journey_type"]
    if user["kyc_status"] != "VERIFIED" and kind != "kyc":
        raise ProductError("Complete KYC first.")
    acc_id = params.get("account_id")
    acc = db.query_one("SELECT * FROM accounts WHERE id=? AND user_id=?", (acc_id, user["id"])) if acc_id else None
    if kind in ("loan", "insurance") and not acc:
        raise ProductError("Choose the bank account for " + ("the payout." if kind == "loan" else "the premium."))
    o = OFFERS.get(partner_id, {})
    app = {"age": doccheck.age_of(user["dob"])}
    if kind == "loan":
        amount, months, income = float(params.get("amount") or 0), int(params.get("tenure_months") or 0), \
            float(params.get("monthly_income") or 0)
        if not 50000 <= amount <= o["max_amount"]:
            raise ProductError(f"Loan amount must be between ₹50,000 and {inr(o['max_amount'])}.")
        if months not in (12, 24, 36, 48, 60):
            raise ProductError("Choose a tenure of 12 to 60 months.")
        if income < o["min_income"]:
            raise ProductError(f"Minimum monthly income for this lender is {inr(o['min_income'])}.")
        app.update(amount=amount, tenure_months=months, monthly_income=income, rate=o["rate"],
                   emi=_emi(amount, o["rate"], months))
        title, subtitle, amt = "Personal Loan", f"{prof['partner_name']} · {months} months @ {o['rate']}%", amount
    elif kind == "insurance":
        app.update(plan=o["plan"], cover=o["cover"], premium=float(o["premium_per_year"]))
        title, subtitle, amt = o["plan"], f"{prof['partner_name']} · cover {inr(o['cover'])}", float(o["premium_per_year"])
    else:
        title, subtitle, amt = "KYC verification", prof["partner_name"], 0.0
    ref = {"loan": "LN", "insurance": "INS", "kyc": "KYC"}[kind] + "-" + uuid.uuid4().hex[:6].upper()
    reqs = doccheck.ordered(prof["requirements"], app)
    jid = journeys.create(user["id"], kind, title, subtitle, partner_id, ref, amt, "Collecting documents",
                          {"application": app, "account_id": acc["id"] if acc else None,
                           "required": [dt for dt, _ in reqs], "submitted": False})
    journal.add_event(jid, "milestone", "Application started", subtitle, actor="user")
    journal.audit(jid, "user", "APPLICATION_STARTED", f"{title} with {prof['partner_name']}", {"ref": ref})
    return {"journey_id": jid, **precheck(user, jid)}


def precheck(user: dict, jid: str) -> dict:
    j = _own(user, jid)
    app = j["state"]["application"]
    reqs = registry.requirements(j["partner_id"])
    docs = vault.latest_versions(user["id"])
    found, items = 0, []
    for dt, rule in doccheck.ordered(reqs, app):
        accepted = doccheck.accepted_types(dt, rule)
        cands = []
        for d in docs:
            if d["doc_type"] not in accepted:
                continue
            issues = doccheck.evaluate(dt, rule, d, user, app)
            cands.append({"document_id": d["document_id"], "version_id": d["version_id"], "version": d["version"],
                          "name": d["name"], "summary": docintel.summary(d["doc_type"], d["fields"]),
                          "ok": not issues, "issues": [i["message"] for i in issues],
                          "evidence": [{"required": i["required"], "found": i["found"]} for i in issues]})
        cands.sort(key=lambda c: (not c["ok"], -c["version"]))
        if cands:
            found += 1
        items.append({"doc_type": dt, "role": doccheck.role_for(dt), "label": docintel.TYPE_LABEL.get(dt, "Identity document"),
                      "requirement": doccheck.describe(dt, rule), "candidates": cands})
    problems = [f"{i['label']}: {i['candidates'][0]['issues'][0]}" for i in items if i["candidates"] and not i["candidates"][0]["ok"]]
    missing = [i["label"] for i in items if not i["candidates"]]
    note = (f"I found {found} document{'s' if found != 1 else ''} in your vault that may satisfy this application."
            if found else "I didn't find matching documents in your vault yet.")
    return {"journey_id": jid, "checklist": items, "saarthi_note": note, "problems": problems, "missing": missing}


def submit(user: dict, jid: str, selections: dict) -> dict:
    j = _own(user, jid)
    if j["state"].get("submitted"):
        raise ProductError("This application was already submitted.")
    attached = {}
    for role, doc_id in (selections or {}).items():
        d = db.query_one("SELECT * FROM documents WHERE id=? AND user_id=?", (doc_id, user["id"]))
        if not d:
            raise ProductError("One of the selected documents isn't in your vault.")
        attached[role] = d["latest_version_id"]
        db.insert("journey_documents", {"journey_id": jid, "document_id": doc_id, "role": role,
                                        "version_id": d["latest_version_id"], "attached_at": db.now_iso()})
        journal.add_event(jid, "document", f"{d['name']} attached", f"v{d['latest_version']} from your vault",
                          actor="user")
    res = connectors.call(j["partner_id"], "submit_application", journey_id=jid, ref=j["partner_ref"],
                          user_id=user["id"], product=j["category"], application=j["state"]["application"],
                          documents=attached, account_id=j["state"].get("account_id"))
    journeys.patch_state(jid, submitted=True)
    journal.add_event(jid, "partner", "Application submitted to partner", res["endpoint"], actor="system")
    return after_partner_response(jid, res)


def after_partner_response(jid: str, res: dict) -> dict:
    """Apply a partner response to the journey (success, pending or failure)."""
    j = journeys.get(jid)
    n = res["normalized"]
    if n["state"] == "SUCCESS":
        stage = {"loan": "Disbursed", "insurance": "Policy issued", "kyc": "Verified"}[j["category"]]
        journeys.close_incident(jid, "ON_TRACK" if j["status"] != "ATTENTION" else "RESOLVED", stage,
                                last_success_at=db.now_iso())
        _success_event(j, res)
        if j["category"] == "kyc":
            db.update("users", "id", j["user_id"], {"kyc_status": "VERIFIED"})
        return {"status": "SUCCESS", "journey_id": jid}
    journeys.open_incident(jid, n["raw_code"] or "UNKNOWN", n["raw_message"] or "", j["partner_id"],
                           "Waiting on partner" if n["state"] == "PENDING" else "Partner rejected application")
    return {"status": n["state"], "journey_id": jid, "code": n["raw_code"], "message": n["raw_message"]}


def _success_event(j: dict, res: dict) -> None:
    raw = res["raw"]
    pay = raw.get("disbursal") or raw.get("payout") or {}
    if j["category"] == "loan":
        journal.add_event(j["id"], "partner", "Loan disbursed", f"{inr(pay.get('amount', j['amount']))} credited to "
                          f"{pay.get('account', 'your account')} · UTR {pay.get('utr', '—')}", actor=j["partner_id"],
                          stage="verify")
    elif j["category"] == "insurance":
        journal.add_event(j["id"], "partner", "Policy issued", f"Policy {pay.get('policy_no', '—')} · premium "
                          f"{inr(pay.get('premium', j['amount']))} collected", actor=j["partner_id"], stage="verify")
    else:
        journal.add_event(j["id"], "partner", "Identity verified", "KYC registry confirmed your identity",
                          actor=j["partner_id"], stage="verify")


def _own(user: dict, jid: str) -> dict:
    j = journeys.get(jid)
    if not j or j["user_id"] != user["id"]:
        raise NotFound("Journey not found.")
    return j


def for_user(uid: str, kind: str) -> list[dict]:
    return db.query("SELECT * FROM journeys WHERE user_id=? AND category=? ORDER BY created_at DESC", (uid, kind))
