"""Sandbox partner systems.

Each bank keeps its own state (account records, mandates, presentments) in the
partner_state table and speaks its own dialect - different field names, status
vocabularies and error codes. Saarthi's connectors/normalization layer absorbs
that fragmentation.

Nothing here is scripted. Outcomes come from state:
  * a debit fails with the bank's insufficient-funds code only if the account
    balance is actually below the installment,
  * it fails with the bank's mandate-limit code only if the installment is above
    the mandate's authorised maximum,
  * penny-drop verification fails only if the bank-record name does not match
    the investor's registered name,
  * Account Aggregator returns whatever PAN the bank holds for the account.
"""
import random
import re
import uuid
from datetime import datetime, timezone

from app.database import db
from app.knowledge.entries import BANK_CODES, BANK_NAMES
from app.services import namematch

NAME_MATCH_PASS = 0.85
MAX_REPRESENTMENTS = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(pid: str, ref: str) -> dict:
    row = db.query_one("SELECT * FROM partner_state WHERE partner_id=? AND ref=?", (pid, ref))
    if not row:
        raise KeyError(f"{pid}:{ref} unknown to partner")
    return row["state"]


def _put(pid: str, ref: str, state: dict) -> None:
    db.insert("partner_state", {"partner_id": pid, "ref": ref, "state": state})


def _account(acc_id: str) -> dict:
    acc = db.query_one("SELECT * FROM accounts WHERE id=?", (acc_id,))
    if not acc:
        raise KeyError(f"account {acc_id} unknown")
    return acc


class PartnerError(Exception):
    pass


# --------------------------------------------------------------------------- banks
class SandboxBank:
    """A sandbox bank. `dialect` decides how responses look on the wire:

    nach   - flat NPCI-style fields: txnStatus S/F/P, respCode, respMsg, string amounts
    nested - JSON envelope: {status: {code, desc, stage}, ...}
    """

    OK = {"nach": "00", "nested": None}

    def __init__(self, pid: str, dialect: str):
        self.id, self.dialect = pid, dialect
        self.name = BANK_NAMES[pid]
        self.codes = BANK_CODES[pid]

    # ---- wire formatting
    def _txn(self, s: dict) -> dict:
        ok = s["status"] == "SUCCESS"
        if self.dialect == "nach":
            return {"sipRef": s["ref"], "umrn": s["umrn"], "txnStatus": "S" if ok else "F",
                    "respCode": "00" if ok else s["code"], "respMsg": s["message"],
                    "amount": f"{s['amount']:.2f}", "presentedOn": s["presented_on"],
                    "bankRefNo": s.get("bank_ref"), "representments": s["retries"]}
        return {"reference": s["ref"], "status": {"code": "DEBIT_OK" if ok else s["code"], "desc": s["message"],
                                                  "stage": "SETTLED" if ok else "RETURNED"},
                "mandate": {"umrn": s["umrn"]}, "amount": s["amount"], "presented_at": s["presented_on"],
                "utr": s.get("bank_ref"), "retry_count": s["retries"]}

    def _bav(self, s: dict) -> dict:
        ok = s["status"] == "VERIFIED"
        if self.dialect == "nach":
            return {"bavRef": s["ref"], "bavStatus": "S" if ok else "F", "respCode": "00" if ok else s["code"],
                    "respMsg": s["message"], "beneName": s["name_on_record"], "nameMatchScore": s["score"],
                    "pennyAmount": "1.00"}
        return {"reference": s["ref"], "status": {"code": "BAV_OK" if ok else s["code"], "desc": s["message"]},
                "beneficiary": {"name": s["name_on_record"]}, "match": {"score": s["score"],
                                                                         "expected": s["expected_name"]}}

    # ---- accounts
    def open_account(self, account_id: str, holder_name: str, holder_pan: str):
        _put(self.id, f"acct:{account_id}", {"holder_name": holder_name, "holder_pan": holder_pan,
                                             "opened_at": _now()})
        return {"ack": True}

    def validate_account(self, account_id: str, expected_name: str):
        """Penny drop: credit Re 1, read back the beneficiary name, score it against the expected name."""
        rec = _get(self.id, f"acct:{account_id}")
        acc = _account(account_id)
        db.update("accounts", "id", account_id, {"balance": round(acc["balance"] + 1, 2)})
        m = namematch.score(rec["holder_name"], expected_name)
        ok = m["score"] >= NAME_MATCH_PASS
        s = {"ref": f"BAV-{account_id}", "account_id": account_id, "status": "VERIFIED" if ok else "FAILED",
             "code": None if ok else self.codes["ACCOUNT_VERIFICATION"],
             "message": "BENEFICIARY VALIDATED" if ok else "BENEFICIARY NAME MISMATCH",
             "name_on_record": rec["holder_name"].upper(), "expected_name": expected_name, "score": m["score"],
             "validated_at": _now()}
        _put(self.id, s["ref"], s)
        return self._bav(s)

    def mark_verified(self, ref: str, method: str):
        s = _get(self.id, ref)
        s.update(status="VERIFIED", code=None, message=f"OWNERSHIP CONFIRMED ({method})")
        _put(self.id, ref, s)
        return self._bav(s)

    # ---- mandates
    def register_mandate(self, account_id: str, max_amount: float, payer_name: str):
        _get(self.id, f"acct:{account_id}")
        umrn = f"{self.id.upper()}{random.randint(10**9, 10**10 - 1)}"
        _put(self.id, f"mandate:{umrn}", {"umrn": umrn, "account_id": account_id, "max_amount": max_amount,
                                         "status": "ACTIVE", "payer": payer_name, "registered_at": _now()})
        if self.dialect == "nach":
            return {"umrn": umrn, "mandateStatus": "ACTIVE", "maxAmount": f"{max_amount:.2f}", "respCode": "00"}
        return {"status": {"code": "MANDATE_OK", "desc": "Mandate registered"}, "umrn": umrn,
                "limits": {"max_amount": max_amount}}

    def amend_mandate(self, umrn: str, max_amount: float):
        m = _get(self.id, f"mandate:{umrn}")
        old = m["max_amount"]
        m.update(max_amount=max_amount, amended_at=_now())
        _put(self.id, f"mandate:{umrn}", m)
        if self.dialect == "nach":
            return {"umrn": umrn, "mandateStatus": m["status"], "maxAmount": f"{max_amount:.2f}",
                    "prevMaxAmount": f"{old:.2f}", "respCode": "00", "respMsg": "MANDATE AMENDED"}
        return {"status": {"code": "MANDATE_OK", "desc": "Mandate amended"}, "umrn": umrn,
                "limits": {"max_amount": max_amount, "previous": old}}

    def mandate(self, umrn: str) -> dict:
        return _get(self.id, f"mandate:{umrn}")

    # ---- debits
    def _settle(self, s: dict) -> dict:
        m = _get(self.id, f"mandate:{s['umrn']}")
        acc = _account(m["account_id"])
        s["presented_on"] = _now()
        if m["status"] != "ACTIVE":
            s.update(status="FAILED", code=self.codes["MANDATE_LIMIT"], message="MANDATE NOT ACTIVE")
        elif s["amount"] > m["max_amount"] + 1e-6:
            s.update(status="FAILED", code=self.codes["MANDATE_LIMIT"], message="AMOUNT EXCEEDS MANDATE LIMIT")
        elif acc["balance"] + 1e-6 < s["amount"]:
            s.update(status="FAILED", code=self.codes["PAYMENT_FAILURE"], message="DEBIT RETURNED - FUNDS INSUFFICIENT")
        else:
            db.update("accounts", "id", acc["id"], {"balance": round(acc["balance"] - s["amount"], 2)})
            s.update(status="SUCCESS", code=None, message="DEBIT SUCCESS",
                     bank_ref=f"{self.id[:2].upper()}N{random.randint(10**9, 10**10 - 1)}")
        _put(self.id, s["ref"], s)
        return self._txn(s)

    def present_debit(self, ref: str, umrn: str, amount: float):
        s = {"ref": ref, "umrn": umrn, "amount": amount, "retries": 0, "status": "PENDING", "code": None,
             "message": "", "bank_ref": None}
        return self._settle(s)

    def retry(self, ref: str):
        s = _get(self.id, ref)
        if s["status"] == "SUCCESS":
            return self._txn(s)
        if s["retries"] >= MAX_REPRESENTMENTS:
            s.update(code=self.codes["PAYMENT_FAILURE"], message="RE-PRESENTMENT LIMIT REACHED")
            return self._txn(s)
        s["retries"] += 1
        return self._settle(s)

    # ---- reads
    def get_journey(self, ref: str):
        s = _get(self.id, ref)
        return self._bav(s) if ref.startswith("BAV-") else self._txn(s)

    def diagnose(self, ref: str):
        s = _get(self.id, ref)
        if ref.startswith("BAV-"):
            return {"ref": ref, "check": "PENNY_DROP", "name_on_record": s["name_on_record"],
                    "expected_name": s["expected_name"], "score": s["score"], "pass_threshold": NAME_MATCH_PASS}
        m = _get(self.id, f"mandate:{s['umrn']}")
        return {"ref": ref, "mandate_status": m["status"], "mandate_max": m["max_amount"],
                "presented_amount": s["amount"], "representments_used": s["retries"],
                "representments_allowed": MAX_REPRESENTMENTS}

    # ---- money movement
    def transfer(self, from_account: str, to_account: str, amount: float):
        src, dst = _account(from_account), _account(to_account)
        if src["partner_id"] != self.id:
            raise PartnerError(f"Source account not held at {self.name}")
        if src["balance"] + 1e-6 < amount:
            return {"status": {"code": "IMPS_FAILED", "desc": "Insufficient balance in remitter account"}}
        db.update("accounts", "id", src["id"], {"balance": round(src["balance"] - amount, 2)})
        dst = _account(to_account)
        db.update("accounts", "id", dst["id"], {"balance": round(dst["balance"] + amount, 2)})
        return {"status": {"code": "IMPS_SUCCESS", "desc": "Credited to beneficiary"},
                "utr": f"6{random.randint(10**10, 10**11 - 1)}", "amount": amount,
                "beneficiary": f"{dst['bank']} {dst['masked']}"}

    def update_status(self, ref: str, status: str):
        return {"ack": True, "ref": ref, "note": status}


# --------------------------------------------------------------------------- Account Aggregator
class AccountAggregator:
    """Consent-based data from the bank (FIP). Returns what the bank actually holds."""
    id = "aa"

    def fetch_profile(self, account_id: str, consent_id: str):
        acc = _account(account_id)
        rec = _get(acc["partner_id"], f"acct:{account_id}")
        pan = rec["holder_pan"]
        return {"consentId": consent_id, "fipId": acc["partner_id"].upper() + "-FIP", "status": "DATA_READY",
                "profile": {"holders": [{"name": rec["holder_name"].upper(), "pan": pan,
                                         "type": "SINGLE"}], "account": acc["masked"], "bank": acc["bank"],
                            "accountType": "SAVINGS"}}


# --------------------------------------------------------------------------- PAN registry
class PanRegistry:
    """Sandbox NSDL PAN verification: structural validation + name/DOB seeding."""
    id = "nsdl"
    PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

    def verify_pan(self, pan: str, name: str, dob: str):
        if not self.PAN_RE.match(pan or ""):
            return {"pan": pan, "pan_status": "INVALID", "name_match": "N", "dob_match": "N"}
        holder_type = {"P": "Individual"}.get(pan[3], "Non-individual")
        return {"pan": pan, "pan_status": "E" if pan[3] == "P" else "NOT_INDIVIDUAL", "holder_type": holder_type,
                "name_match": "Y", "dob_match": "Y", "seeding_status": "Y"}


def random_pan() -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(random.choice(letters) for _ in range(3)) + "P" + random.choice(letters) + \
        f"{random.randint(1000, 9999)}" + random.choice(letters)


PARTNERS = {"axis": SandboxBank("axis", "nach"), "icici": SandboxBank("icici", "nach"),
            "hdfc": SandboxBank("hdfc", "nested"), "sbi": SandboxBank("sbi", "nested"),
            "aa": AccountAggregator(), "nsdl": PanRegistry()}


def get(pid: str):
    if pid not in PARTNERS:
        raise PartnerError(f"No connector for partner {pid}")
    return PARTNERS[pid]


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
