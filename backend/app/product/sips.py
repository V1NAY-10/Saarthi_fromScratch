"""Starting SIPs, autopay mandates and installment debits."""
import calendar
import uuid
from datetime import date, timedelta

from app.database import db
from app.partners import connectors
from app.product import journeys
from app.product.journeys import ProductError
from app.services import journal
from app.services.fmt import inr


def _next_due(day: int, after: date) -> str:
    y, m = (after.year + (after.month // 12), after.month % 12 + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1])).isoformat()


def funds() -> list[dict]:
    return db.query("SELECT * FROM funds ORDER BY returns_3y DESC")


def fund(fid: str) -> dict:
    f = db.query_one("SELECT * FROM funds WHERE id=?", (fid,))
    if not f:
        raise ProductError("Unknown fund")
    return f


def get(sid: str) -> dict:
    s = db.query_one("SELECT * FROM sips WHERE id=?", (sid,))
    if not s:
        raise ProductError("Unknown SIP")
    return s


def for_user(uid: str) -> list[dict]:
    out = []
    for s in db.query("SELECT * FROM sips WHERE user_id=? ORDER BY created_at DESC", (uid,)):
        f = fund(s["fund_id"])
        m = db.query_one("SELECT * FROM mandates WHERE id=?", (s["mandate_id"],))
        a = db.query_one("SELECT * FROM accounts WHERE id=?", (s["account_id"],))
        out.append({**s, "fund": f, "mandate": m, "account": {"id": a["id"], "bank": a["bank"], "masked": a["masked"],
                                                              "balance": a["balance"]},
                    "current_value": round(s["units"] * f["nav"], 2),
                    "journey_status": journeys.get(s["journey_id"])["status"]})
    return out


def start(user: dict, fund_id: str, amount: float, sip_day: int, account_id: str, mandate_limit: float) -> dict:
    f = fund(fund_id)
    acc = db.query_one("SELECT * FROM accounts WHERE id=? AND user_id=?", (account_id, user["id"]))
    if user["kyc_status"] != "VERIFIED":
        raise ProductError("Complete KYC before investing.")
    if not acc:
        raise ProductError("Choose a linked bank account.")
    if acc["status"] != "VERIFIED":
        raise ProductError(f"{acc['bank']} {acc['masked']} isn't verified yet, so it can't be used for autopay.")
    if amount < f["min_sip"]:
        raise ProductError(f"Minimum SIP for this fund is {inr(f['min_sip'])}.")
    if amount % 100:
        raise ProductError("SIP amount must be a multiple of ₹100.")
    if not 1 <= sip_day <= 28:
        raise ProductError("Pick a SIP date between 1 and 28.")
    if mandate_limit < amount:
        raise ProductError("Autopay limit can't be lower than the SIP amount.")

    reg = connectors.call(acc["partner_id"], "register_mandate", account_id=acc["id"], max_amount=mandate_limit,
                          payer_name=user["name"])
    umrn = reg["raw"]["umrn"]
    mid, sid = f"man-{uuid.uuid4().hex[:8]}", f"sip-{uuid.uuid4().hex[:8]}"
    db.insert("mandates", {"id": mid, "user_id": user["id"], "account_id": acc["id"], "umrn": umrn,
                           "max_amount": mandate_limit, "status": "ACTIVE", "created_at": db.now_iso()})
    ref = f"SIP-{uuid.uuid4().hex[:6].upper()}"
    jid = journeys.create(user["id"], "investment", f["name"], f"SIP · {f['amc']}", acc["partner_id"], ref, amount,
                          "Autopay mandate registered",
                          {"sip_id": sid, "fund_id": f["id"], "account_id": acc["id"], "mandate_id": mid,
                           "umrn": umrn, "sip_day": sip_day})
    db.insert("sips", {"id": sid, "user_id": user["id"], "fund_id": f["id"], "amount": amount, "sip_day": sip_day,
                       "account_id": acc["id"], "mandate_id": mid, "status": "ACTIVE", "journey_id": jid,
                       "installments_paid": 0, "units": 0.0, "invested": 0.0, "next_due": date.today().isoformat(),
                       "created_at": db.now_iso()})
    journal.add_event(jid, "milestone", "SIP registered",
                      f"{inr(amount)} every month on day {sip_day} · {f['name']}", actor="user")
    journal.add_event(jid, "milestone", "Autopay mandate approved",
                      f"UMRN {umrn} · limit {inr(mandate_limit)} · {acc['bank']} {acc['masked']}", actor=acc["partner_id"])
    journal.audit(jid, "user", "SIP_STARTED", f"Started {inr(amount)}/month SIP in {f['name']}",
                  {"mandate": reg["raw"]})
    result = run_installment(user, sid)
    return {"sip": get(sid), "journey_id": jid, "installment": result}


def run_installment(user: dict, sid: str) -> dict:
    s = get(sid)
    if s["user_id"] != user["id"]:
        raise ProductError("Unknown SIP")
    j = journeys.get(s["journey_id"])
    if j["status"] in ("ATTENTION", "ESCALATED"):
        raise ProductError("The previous installment isn't settled yet. Open the journey to see what Saarthi is doing.")
    m = db.query_one("SELECT * FROM mandates WHERE id=?", (s["mandate_id"],))
    acc = db.query_one("SELECT * FROM accounts WHERE id=?", (s["account_id"],))
    n = s["installments_paid"] + 1
    journal.add_event(j["id"], "payment", f"Installment #{n} presented",
                      f"{inr(s['amount'])} presented to {acc['bank']} under UMRN {m['umrn']}", actor="system")
    res = connectors.call(acc["partner_id"], "present_debit", journey_id=j["id"], ref=j["partner_ref"],
                          umrn=m["umrn"], amount=s["amount"])
    norm = res["normalized"]
    if norm["state"] == "SUCCESS":
        bank_ref = res["raw"].get("bankRefNo") or res["raw"].get("utr")
        tx = complete_installment(sid, bank_ref)
        journeys.close_incident(j["id"], "ON_TRACK", f"Installment #{n} paid", bank_ref=bank_ref,
                                 last_success_at=db.now_iso())
        return {"status": "SUCCESS", "journey_id": j["id"], "transaction": tx}
    db.insert("transactions", {"id": f"tx-{uuid.uuid4().hex[:8]}", "user_id": user["id"], "sip_id": sid,
                               "kind": "SIP_DEBIT", "amount": s["amount"], "status": "FAILED", "code": norm["raw_code"],
                               "nav": None, "units": None, "bank_ref": None, "ts": db.now_iso()})
    journeys.open_incident(j["id"], norm["raw_code"], norm["raw_message"] or "", acc["partner_id"],
                           f"Installment #{n} failed", installment_no=n, failed_amount=s["amount"])
    return {"status": "FAILED", "journey_id": j["id"], "code": norm["raw_code"], "message": norm["raw_message"]}


def complete_installment(sid: str, bank_ref: str | None) -> dict:
    """Debit settled at the bank -> allot units at today's NAV."""
    s = get(sid)
    f = fund(s["fund_id"])
    units = round(s["amount"] / f["nav"], 3)
    n = s["installments_paid"] + 1
    tx = {"id": f"tx-{uuid.uuid4().hex[:8]}", "user_id": s["user_id"], "sip_id": sid, "kind": "SIP_DEBIT",
          "amount": s["amount"], "status": "SUCCESS", "code": None, "nav": f["nav"], "units": units,
          "bank_ref": bank_ref, "ts": db.now_iso()}
    db.insert("transactions", tx)
    db.update("sips", "id", sid, {"installments_paid": n, "units": round(s["units"] + units, 3),
                                  "invested": s["invested"] + s["amount"],
                                  "next_due": _next_due(s["sip_day"], date.today())})
    journal.add_event(s["journey_id"], "payment", f"Installment #{n} debited",
                      f"{inr(s['amount'])} · Ref {bank_ref} · {units} units at NAV ₹{f['nav']}", actor="system",
                      stage="verify")
    return tx


def update_amount(user: dict, sid: str, amount: float) -> dict:
    s = get(sid)
    if s["user_id"] != user["id"]:
        raise ProductError("Unknown SIP")
    f = fund(s["fund_id"])
    if amount < f["min_sip"] or amount % 100:
        raise ProductError(f"Amount must be at least {inr(f['min_sip'])} and a multiple of ₹100.")
    old = s["amount"]
    db.update("sips", "id", sid, {"amount": amount})
    db.update("journeys", "id", s["journey_id"], {"amount": amount, "updated_at": db.now_iso()})
    journal.add_event(s["journey_id"], "milestone", "SIP amount changed", f"{inr(old)} → {inr(amount)} per month",
                      actor="user")
    journal.audit(s["journey_id"], "user", "SIP_UPDATED", f"SIP changed from {inr(old)} to {inr(amount)}")
    return get(sid)


def due_soon(uid: str, days: int = 40) -> list[dict]:
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    return [s for s in for_user(uid) if s["status"] == "ACTIVE" and s["next_due"] <= cutoff]
