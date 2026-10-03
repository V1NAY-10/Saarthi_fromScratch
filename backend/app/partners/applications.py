"""Sandbox application partners: lenders, insurers and a KYC registry.

Each partner evaluates an application against *its own published rules* (the
`requirements` in its knowledge-base profile), reading the documents the
customer actually attached, in order, and returns the first failure as its own
partner code (looked up from the knowledge base). A loan that passes is
sanctioned and disbursed into the customer's account; an insurance policy that
passes collects its premium from the customer's account and is issued.

Sandbox fault injection (`inject`) lets the demo make a partner return a given
code (an outage, a manual review, an unknown error) for N calls, so those
scenarios also flow through the real pipeline."""
import random
from datetime import datetime, timezone

from app.database import db
from app.knowledge import registry
from app.services import doccheck

SUCCESS = {"loan": "DISBURSED", "insurance": "ISSUED", "kyc": "VERIFIED"}
PENDING_TYPES = {"APPLICATION_STUCK", "MANUAL_REVIEW", "DISBURSEMENT_PENDING", "IDV_PENDING"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(pid, ref):
    row = db.query_one("SELECT * FROM partner_state WHERE partner_id=? AND ref=?", (pid, ref))
    if not row:
        raise KeyError(f"{pid}:{ref} unknown to partner")
    return row["state"]


def _put(pid, ref, s):
    db.insert("partner_state", {"partner_id": pid, "ref": ref, "state": s})


def _version(vid: str | None) -> dict | None:
    if not vid:
        return None
    v = db.query_one("SELECT v.*, d.doc_type FROM document_versions v JOIN documents d ON d.id = v.document_id "
                     "WHERE v.id=?", (vid,))
    return {"doc_type": v["doc_type"], "fields": v["fields"] or {}, "checks": v["checks"] or {}} if v else None


class ApplicationPartner:
    def __init__(self, pid: str):
        self.id = pid
        prof = registry.load()["profiles"][pid]
        self.dialect, self.journey_type = prof["dialect"], prof["journey_type"]

    # ---- wire formatting
    def _wire(self, s: dict) -> dict:
        if self.dialect == "nested":
            code = s["code"] or {"DISBURSED": "APP_DISBURSED", "ISSUED": "POLICY_ISSUED", "VERIFIED": "KYC_OK",
                                 "SUBMITTED": "APP_RECEIVED"}.get(s["status"], "APP_OK")
            return {"application": {"id": s["ref"], "stage": s["stage"], "product": s["product"]},
                    "status": {"code": code, "desc": s["message"], "state": s["status"]},
                    "updated_at": s["updated_at"], **({"disbursal": s["disbursal"]} if s.get("disbursal") else {})}
        return {"appRef": s["ref"], "appStatus": s["status"], "reasonCode": s["code"] or "00",
                "reasonText": s["message"], "stage": s["stage"], "lastUpdated": s["updated_at"],
                **({"payout": s["disbursal"]} if s.get("disbursal") else {})}

    def _code(self, ftype: str) -> str:
        # A partner without a published code for this failure returns an undocumented one.
        return registry.code_for(self.id, ftype) or f"{self.id.upper()}_ERR_{abs(hash(ftype)) % 900 + 100}"

    def _set(self, s, status, code=None, message="", stage=None, failure_type=None, detail=None):
        s.update(status=status, code=code, message=message, stage=stage or s.get("stage"), updated_at=_now(),
                 failure_type=failure_type, detail=detail or {})
        s.setdefault("history", []).append({"ts": _now(), "status": status, "code": code})

    # ---- evaluation
    def _evaluate(self, s: dict) -> None:
        inj = s.get("inject")
        if inj and inj.get("remaining", 0) > 0:
            ft = inj.get("failure_type")
            if ft in PENDING_TYPES:
                # A partner queue clears with time, not with how often someone asks.
                until = inj.setdefault("until", (datetime.now(timezone.utc).timestamp() + inj.get("seconds", 25)))
                if datetime.now(timezone.utc).timestamp() < until:
                    self._set(s, "PENDING", inj["code"], inj.get("message", "Under review"), "Processing", ft)
                    return
                inj["remaining"] = 0
            else:
                inj["remaining"] -= 1
                status = "REJECTED" if ft else "ERROR"
                self._set(s, status, inj["code"], inj.get("message", "Partner returned an error"), "Processing", ft)
                return
        user = db.query_one("SELECT * FROM users WHERE id=?", (s["user_id"],))
        acc = db.query_one("SELECT * FROM accounts WHERE id=?", (s.get("account_id"),)) if s.get("account_id") else None
        if self.journey_type in ("loan", "insurance") and (not acc or acc["status"] != "VERIFIED"):
            self._set(s, "REJECTED", self._code("ACCOUNT_UNVERIFIED_FOR_PAYOUT"),
                      "Payout account is not verified", "Bank verification", "ACCOUNT_UNVERIFIED_FOR_PAYOUT",
                      {"account_id": s.get("account_id")})
            return
        app = {**s.get("application", {}), "age": doccheck.age_of(user["dob"])}
        for doc_type, rule in doccheck.ordered(registry.requirements(self.id), app):
            role = doccheck.role_for(doc_type)
            v = _version(s["documents"].get(role))
            issues = doccheck.evaluate(doc_type, rule, v, user, app)
            if issues:
                i = issues[0]
                self._set(s, "REJECTED", self._code(i["failure_type"]), i["message"], "Document verification",
                          i["failure_type"], {"role": role, "doc_type": doc_type, "rule": i["rule"],
                                              "required": i["required"], "found": i["found"],
                                              "version_id": s["documents"].get(role)})
                return
        self._complete(s, acc)

    def _complete(self, s: dict, acc: dict | None) -> None:
        if self.journey_type == "loan":
            amt = s["application"]["amount"]
            db.update("accounts", "id", acc["id"], {"balance": round(acc["balance"] + amt, 2)})
            s["disbursal"] = {"amount": amt, "account": acc["masked"], "utr": f"7{random.randint(10**10, 10**11 - 1)}"}
            self._set(s, "DISBURSED", None, "Loan sanctioned and disbursed", "Disbursed")
        elif self.journey_type == "insurance":
            premium = s["application"]["premium"]
            if acc["balance"] + 1e-6 < premium:
                self._set(s, "REJECTED", self._code("PREMIUM_PAYMENT_FAILED"), "Premium debit returned",
                          "Premium collection", "PREMIUM_PAYMENT_FAILED", {"premium": premium,
                                                                           "account_id": acc["id"]})
                return
            db.update("accounts", "id", acc["id"], {"balance": round(acc["balance"] - premium, 2)})
            s["disbursal"] = {"premium": premium, "policy_no": f"POL-{random.randint(10**6, 10**7 - 1)}"}
            self._set(s, "ISSUED", None, "Premium collected, policy issued", "Policy issued")
        else:
            self._set(s, "VERIFIED", None, "Identity verified", "Verified")

    # ---- partner API
    def submit_application(self, ref: str, user_id: str, product: str, application: dict, documents: dict,
                           account_id: str | None):
        s = {"ref": ref, "user_id": user_id, "product": product, "application": application, "documents": documents,
             "account_id": account_id, "attempts": 0, "stage": "Received", "created_at": _now()}
        try:
            s["inject"] = _get(self.id, f"inject:{user_id}")
            db.execute("DELETE FROM partner_state WHERE partner_id=? AND ref=?", (self.id, f"inject:{user_id}"))
        except KeyError:
            pass
        self._evaluate(s)
        _put(self.id, ref, s)
        return self._wire(s)

    def submit_document(self, ref: str, role: str, version_id: str):
        s = _get(self.id, ref)
        s["documents"][role] = version_id
        self._evaluate(s)
        _put(self.id, ref, s)
        return self._wire(s)

    def update_account(self, ref: str, account_id: str):
        s = _get(self.id, ref)
        s["account_id"] = account_id
        self._evaluate(s)
        _put(self.id, ref, s)
        return self._wire(s)

    def retry(self, ref: str):
        s = _get(self.id, ref)
        if s["status"] in SUCCESS.values():
            return self._wire(s)
        s["attempts"] += 1
        self._evaluate(s)
        _put(self.id, ref, s)
        return self._wire(s)

    def get_journey(self, ref: str):
        """Status check. A pending state (manual review, disbursal pending...) progresses
        when re-checked, just as a real partner's queue would."""
        s = _get(self.id, ref)
        if s["status"] == "PENDING":
            self._evaluate(s)
            _put(self.id, ref, s)
        return self._wire(s)

    def diagnose(self, ref: str):
        s = _get(self.id, ref)
        return {"ref": ref, "status": s["status"], "check": s.get("detail") or {},
                "attempts": s.get("attempts", 0), "history": s.get("history", [])[-6:]}

    def update_status(self, ref: str, status: str):
        s = _get(self.id, ref)
        s["note"] = status
        _put(self.id, ref, s)
        return {"ack": True, "ref": ref}


def inject(pid: str, user_id: str, code: str, failure_type: str | None, times: int, message: str,
           seconds: int = 25) -> None:
    """Sandbox control: make the partner return `code` for the user's next application - `times` times for
    errors, or for `seconds` for pending states (manual review, disbursal pending)."""
    _put(pid, f"inject:{user_id}", {"code": code, "failure_type": failure_type, "remaining": times, "message": message,
                                    "seconds": seconds})
