"""Linking bank accounts (penny-drop verification) and sandbox balance controls."""
import re
import uuid

from app.database import db
from app.knowledge.entries import BANK_NAMES
from app.partners import connectors, simulators
from app.product import journeys
from app.product.journeys import ProductError
from app.services import journal, namematch
from app.services.fmt import inr

IFSC = {"axis": "UTIB0000123", "icici": "ICIC0000456", "hdfc": "HDFC0000789", "sbi": "SBIN0000321"}


def link(user: dict, bank: str, account_no: str, holder_name: str, opening_balance: float, owner: str) -> dict:
    """Link a bank account. `holder_name` is the name on the bank's own record and `owner`
    says whose PAN the bank has on file - both are sandbox inputs that stand in for the
    real bank's data, which Saarthi only learns through the bank's APIs."""
    account_no = re.sub(r"\s", "", account_no)
    holder_name = " ".join(holder_name.split())
    if bank not in BANK_NAMES:
        raise ProductError("Choose a supported bank.")
    if not re.fullmatch(r"\d{9,18}", account_no):
        raise ProductError("Account number must be 9 to 18 digits.")
    if not holder_name:
        raise ProductError("Enter the account holder name as printed on your passbook.")
    if not 0 <= opening_balance <= 1e7:
        raise ProductError("Sandbox balance must be between ₹0 and ₹1,00,00,000.")
    if owner not in ("self", "other"):
        raise ProductError("Unknown account owner.")
    if db.query_one("SELECT id FROM accounts WHERE user_id=? AND partner_id=? AND account_no=?",
                    (user["id"], bank, account_no)):
        raise ProductError("This account is already linked.")

    acc_id = f"acc-{uuid.uuid4().hex[:8]}"
    masked = "XX" + account_no[-4:]
    db.insert("accounts", {"id": acc_id, "user_id": user["id"], "partner_id": bank, "bank": BANK_NAMES[bank],
                           "account_no": account_no, "masked": masked, "ifsc": IFSC[bank], "holder_name": holder_name,
                           "balance": round(opening_balance, 2), "status": "VERIFYING", "bank_name_on_record": None,
                           "name_match": None, "journey_id": None, "created_at": db.now_iso()})
    holder_pan = user["pan"] if owner == "self" else simulators.random_pan()
    connectors.call(bank, "open_account", account_id=acc_id, holder_name=holder_name, holder_pan=holder_pan)
    res = connectors.call(bank, "validate_account", account_id=acc_id, expected_name=user["name"])
    state = res["normalized"]["state"]
    bav = simulators.get(bank).get_journey(f"BAV-{acc_id}")
    name_on_record = bav.get("beneName") or bav.get("beneficiary", {}).get("name")
    m = namematch.score(name_on_record, user["name"])
    db.update("accounts", "id", acc_id, {"bank_name_on_record": name_on_record, "name_match": m["score"]})

    if state == "VERIFIED":
        db.update("accounts", "id", acc_id, {"status": "VERIFIED"})
        journal.audit(None, "partner", "ACCOUNT_VERIFIED",
                      f"{BANK_NAMES[bank]} {masked} verified by penny drop (name match {m['score']:.2f})",
                      {"partner_raw": res["raw"]}, user_id=user["id"])
        return get(acc_id)

    db.update("accounts", "id", acc_id, {"status": "UNVERIFIED"})
    jid = journeys.create(user["id"], "bank_account", f"{BANK_NAMES[bank]} {masked}",
                          "Bank account verification", bank, f"BAV-{acc_id}", 0.0, "Penny-drop verification",
                          {"account_id": acc_id})
    db.update("accounts", "id", acc_id, {"journey_id": jid})
    journal.add_event(jid, "milestone", "Bank account linked", f"{BANK_NAMES[bank]} {masked} · IFSC {IFSC[bank]}",
                      actor="user")
    journal.add_event(jid, "payment", "Re 1 penny-drop credited", f"Bank returned beneficiary name '{name_on_record}'",
                      actor=bank)
    journeys.open_incident(jid, res["normalized"]["raw_code"], res["normalized"]["raw_message"] or "", bank,
                           "Verification failed", account_id=acc_id)
    return get(acc_id)


def get(acc_id: str) -> dict:
    a = db.query_one("SELECT * FROM accounts WHERE id=?", (acc_id,))
    if not a:
        raise ProductError("Unknown account")
    return a


def for_user(uid: str) -> list[dict]:
    return db.query("SELECT * FROM accounts WHERE user_id=? ORDER BY created_at", (uid,))


def adjust_balance(user: dict, acc_id: str, delta: float) -> dict:
    """Sandbox control: simulate salary credit / spending on the bank side."""
    a = get(acc_id)
    if a["user_id"] != user["id"]:
        raise ProductError("Unknown account")
    if not delta or abs(delta) > 1e7:
        raise ProductError("Enter an amount.")
    if a["balance"] + delta < 0:
        raise ProductError(f"Balance is only {inr(a['balance'])}.")
    db.update("accounts", "id", acc_id, {"balance": round(a["balance"] + delta, 2)})
    journal.audit(None, "sandbox", "BALANCE_CHANGED",
                  f"{a['bank']} {a['masked']} {'credited' if delta > 0 else 'debited'} {inr(abs(delta))} (sandbox)",
                  user_id=user["id"])
    if delta > 0:
        # New money can change the right fix for any open SIP incident (it may now cover the shortfall
        # itself, or become a funding source), so Saarthi re-assesses them.
        from app.agents import orchestrator
        for j in db.query("SELECT * FROM journeys WHERE user_id=? AND status='ATTENTION' AND category='investment'",
                          (user["id"],)):
            orchestrator.reopen(j["id"], f"{inr(delta)} credited to {a['bank']} {a['masked']}")
    return get(acc_id)
