"""Demo mode: one-click scenarios for judges.

Each scenario performs ordinary user actions for the signed-in user (link an
account, upload sample documents through the real vault pipeline, start a SIP,
submit an application). The failure then comes from the sandbox partner's own
rules, and Saarthi's normal pipeline handles it: event -> RAG -> diagnosis ->
decision -> action -> partner -> verification -> timeline. Two scenarios (outage,
unknown error) use sandbox fault injection, because no customer action can cause
a partner outage. Nothing here bypasses the real logic or renders static screens."""
import uuid

from app.database import db
from app.knowledge import registry
from app.partners import applications as app_partners
from app.product import accounts, applications, sips, vault
from app.product.journeys import ProductError
from app.services import samples

SCENARIOS = [
    {"id": "sip_insufficient", "title": "SIP: insufficient balance", "family": "Payment",
     "what": "₹5,000 SIP from an account holding ₹2,000; another verified account has funds."},
    {"id": "sip_limit", "title": "SIP: above the autopay limit", "family": "Mandate",
     "what": "A ₹5,000 SIP is stepped up to ₹8,000 against a ₹5,000 mandate, then the next installment runs."},
    {"id": "name_mismatch", "title": "Bank account: name mismatch", "family": "Account verification",
     "what": "The bank holds the account under initials, so penny-drop verification fails."},
    {"id": "loan_statement", "title": "Loan: bank statement too short", "family": "Document",
     "what": "A 1-month statement is submitted to a lender that requires 3 months."},
    {"id": "loan_missing", "title": "Loan: required document missing", "family": "Document",
     "what": "The application is submitted without a salary slip."},
    {"id": "insurance_kyc", "title": "Insurance: date of birth mismatch", "family": "Identity",
     "what": "An Aadhaar showing a different date of birth is submitted with a health insurance proposal."},
    {"id": "partner_outage", "title": "Loan: temporary partner outage", "family": "Partner",
     "what": "The lender's system fails once (sandbox fault injection); Saarthi may retry automatically."},
    {"id": "unknown_error", "title": "Loan: unknown partner error", "family": "Unknown",
     "what": "The lender returns a code that isn't in the knowledge base (sandbox fault injection)."},
]


def _acct_no() -> str:
    return "60" + uuid.uuid4().hex[:10].translate(str.maketrans("abcdef", "123456"))


def _verified(user, bank="hdfc", balance=150000.0) -> dict:
    for a in accounts.for_user(user["id"]):
        if a["status"] == "VERIFIED" and a["partner_id"] == bank:
            return a
    return accounts.link(user, bank, _acct_no(), user["name"], balance, "self")


def _upload(user, kind: str, hint: str | None = None) -> dict:
    acc = db.query_one("SELECT * FROM accounts WHERE user_id=? AND status='VERIFIED' ORDER BY created_at", (user["id"],))
    data, filename = samples.generate(kind, user, acc)
    return vault.upload(user, data, filename, "application/pdf", hint)


def _initials(name: str) -> str:
    p = name.split()
    return " ".join([x[0] for x in p[:-1]] + [p[-1]]) if len(p) > 1 else name[0] + " " + name


def _loan(user, partner_id: str, selections: dict, income: float = 90000) -> str:
    acc = _verified(user)
    r = applications.start(user, partner_id, {"amount": 300000, "tenure_months": 24, "monthly_income": income,
                                              "account_id": acc["id"]})
    applications.submit(user, r["journey_id"], selections)
    return r["journey_id"]


def run(user: dict, sid: str) -> dict:
    if sid == "sip_insufficient":
        _verified(user, "hdfc", 150000)
        axis = accounts.link(user, "axis", _acct_no(), user["name"], 2000, "self")
        r = sips.start(user, "f-nimbus-bluechip", 5000, 5, axis["id"], 5000)
        return {"journey_id": r["journey_id"]}
    if sid == "sip_limit":
        icici = accounts.link(user, "icici", _acct_no(), user["name"], 30000, "self")
        r = sips.start(user, "f-vistara-flexi", 5000, 10, icici["id"], 5000)
        sips.update_amount(user, r["sip"]["id"], 8000)
        sips.run_installment(user, r["sip"]["id"])
        return {"journey_id": r["journey_id"]}
    if sid == "name_mismatch":
        a = accounts.link(user, "sbi", _acct_no(), _initials(user["name"]), 25000, "self")
        return {"journey_id": a["journey_id"]}
    if sid == "loan_statement":
        stmt = _upload(user, "bank_statement_1m", "BANK_STATEMENT")
        slip = _upload(user, "salary_slip")
        pan = db.query_one("SELECT id FROM documents WHERE user_id=? AND doc_type='PAN' ORDER BY updated_at DESC", (user["id"],))
        # The statement just uploaded may have become a new version of an existing statement: submit v1-style 1-month doc.
        return {"journey_id": _loan(user, "kaveri_bank", {"pan": pan["id"], "bank_statement": stmt["id"],
                                                          "salary_slip": slip["id"]})}
    if sid == "loan_missing":
        stmt = _upload(user, "bank_statement_3m", "BANK_STATEMENT")
        pan = db.query_one("SELECT id FROM documents WHERE user_id=? AND doc_type='PAN' ORDER BY updated_at DESC", (user["id"],))
        return {"journey_id": _loan(user, "vistara_finance", {"pan": pan["id"], "bank_statement": stmt["id"]})}
    if sid == "insurance_kyc":
        acc = _verified(user)
        doc = _upload(user, "aadhaar_wrong_dob")
        r = applications.start(user, "suraksha_insurance", {"account_id": acc["id"]})
        applications.submit(user, r["journey_id"], {"identity": doc["id"]})
        return {"journey_id": r["journey_id"]}
    if sid in ("partner_outage", "unknown_error"):
        stmt = _upload(user, "bank_statement_3m", "BANK_STATEMENT")
        slip = _upload(user, "salary_slip")
        pan = db.query_one("SELECT id FROM documents WHERE user_id=? AND doc_type='PAN' ORDER BY updated_at DESC", (user["id"],))
        partner = "vistara_finance"
        if sid == "partner_outage":
            app_partners.inject(partner, user["id"], registry.code_for(partner, "PARTNER_TECH_FAILURE"),
                                "PARTNER_TECH_FAILURE", 1, "Partner system error")
        else:
            app_partners.inject(partner, user["id"], "VF_ERR_999", None, 5, "Unexpected partner error")
        return {"journey_id": _loan(user, partner, {"pan": pan["id"], "bank_statement": stmt["id"],
                                                    "salary_slip": slip["id"]})}
    raise ProductError("Unknown scenario.")
