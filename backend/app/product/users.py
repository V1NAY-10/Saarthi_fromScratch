"""Registration and KYC."""
import re
import uuid
from datetime import date

from app.database import db
from app.partners import connectors
from app.product.journeys import ProductError
from app.services import journal

PHONE_RE = re.compile(r"^[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def _age(dob: date) -> int:
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


def register(name: str, phone: str, email: str, dob: str, pan: str) -> dict:
    name = " ".join(name.split())
    pan = pan.strip().upper()
    phone = re.sub(r"\D", "", phone)[-10:]
    if len(name) < 3 or not re.fullmatch(r"[A-Za-z .']+", name):
        raise ProductError("Enter your full name exactly as it appears on your PAN.")
    if not PHONE_RE.match(phone):
        raise ProductError("Enter a valid 10-digit Indian mobile number.")
    if not EMAIL_RE.match(email.strip()):
        raise ProductError("Enter a valid email address.")
    try:
        d = date.fromisoformat(dob)
    except ValueError:
        raise ProductError("Enter your date of birth.")
    if _age(d) < 18:
        raise ProductError("You must be 18 or older to invest.")
    if not PAN_RE.match(pan):
        raise ProductError("PAN must look like ABCDE1234F.")
    if pan[3] != "P":
        raise ProductError("The 4th character of an individual PAN is 'P'.")
    existing = db.query_one("SELECT * FROM users WHERE pan=?", (pan,))
    if existing:
        raise ProductError(f"This PAN is already registered to {existing['name']}. Use 'Continue as' instead.")

    uid = f"u-{uuid.uuid4().hex[:8]}"
    db.insert("users", {"id": uid, "name": name, "phone": phone, "email": email.strip(), "dob": dob, "pan": pan,
                        "kyc_status": "PENDING", "created_at": db.now_iso()})
    journal.audit(None, "user", "REGISTERED", f"{name} registered", {"phone": f"XXXXXX{phone[-4:]}"}, user_id=uid)

    res = connectors.call("nsdl", "verify_pan", pan=pan, name=name, dob=dob)
    ok = res["normalized"]["state"] == "VERIFIED"
    db.update("users", "id", uid, {"kyc_status": "VERIFIED" if ok else "FAILED"})
    db.insert("documents", {"id": f"doc-pan-{uid}", "user_id": uid, "doc_type": "PAN", "name": "PAN Card",
                            "status": "VERIFIED" if ok else "FAILED", "source": "PAN registry (sandbox)",
                            "updated_at": db.now_iso(),
                            "meta": {"name": name, "dob": dob, "number": pan[:5] + "••••" + pan[-1]}})
    journal.audit(None, "kyc", "KYC_VERIFIED" if ok else "KYC_FAILED",
                  f"PAN {pan[:5]}••••{pan[-1]} {'verified' if ok else 'rejected'} by PAN registry",
                  {"registry": res["raw"]}, user_id=uid)
    return get(uid)


def get(uid: str) -> dict:
    u = db.query_one("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        raise ProductError("Unknown user")
    return u


def public(u: dict) -> dict:
    return {"id": u["id"], "name": u["name"], "phone": f"+91 {u['phone'][:2]}XXXX{u['phone'][-4:]}",
            "email": u["email"], "dob": u["dob"], "pan_masked": u["pan"][:5] + "••••" + u["pan"][-1],
            "kyc_status": u["kyc_status"], "created_at": u["created_at"]}


def list_profiles() -> list[dict]:
    return [public(u) for u in db.query("SELECT * FROM users ORDER BY created_at DESC")]
