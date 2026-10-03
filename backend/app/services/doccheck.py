"""Evaluate a document version against a partner's published document rule.

The rule comes from the knowledge base (the partner profile's `requirements`).
The same evaluation is used by the sandbox partner (to decide) and by Saarthi (to
pre-check, explain and pick a replacement from the vault), because both read the
same published rule. Each issue names the normalized failure type it produces."""
from datetime import date

from app.services import namematch
from app.services.docintel import IDENTITY_TYPES, TYPE_LABEL

ORDER = ["PAN", "IDENTITY", "BANK_STATEMENT", "SALARY_SLIP", "MEDICAL_REPORT"]


def accepted_types(doc_type: str, rule: dict) -> list[str]:
    if rule.get("accepted_types"):
        return list(rule["accepted_types"])
    return sorted(IDENTITY_TYPES) if doc_type == "IDENTITY" else [doc_type]


def describe(doc_type: str, rule: dict) -> str:
    parts = []
    if rule.get("min_months"):
        parts.append(f"latest {rule['min_months']} months")
    if rule.get("max_age_days"):
        parts.append(f"issued within {rule['max_age_days']} days")
    if rule.get("name_match"):
        parts.append("name matches your PAN")
    if rule.get("dob_match"):
        parts.append("date of birth matches your KYC")
    if rule.get("unexpired"):
        parts.append("not expired")
    if rule.get("salary_credits"):
        parts.append("shows salary credits")
    if rule.get("income_tolerance"):
        parts.append(f"net pay within {int(rule['income_tolerance'] * 100)}% of declared income")
    label = " or ".join(TYPE_LABEL.get(t, t) for t in accepted_types(doc_type, rule))
    return label + (f": {', '.join(parts)}" if parts else "")


def evaluate(doc_type: str, rule: dict, version: dict | None, user: dict, application: dict | None = None) -> list[dict]:
    """Returns a list of issues; empty means the document satisfies the rule."""
    if version is None:
        return [{"failure_type": "DOCUMENT_MISSING", "rule": "present", "required": describe(doc_type, rule),
                 "found": "Not attached", "message": f"{TYPE_LABEL.get(doc_type, 'Identity document')} is missing"}]
    f, c = version.get("fields") or {}, version.get("checks") or {}
    vtype = version.get("doc_type")
    issues = []

    def add(ftype, rule_name, required, found, message):
        issues.append({"failure_type": ftype, "rule": rule_name, "required": required, "found": found,
                       "message": message})

    if not c.get("readable", True):
        add("STATEMENT_UNREADABLE", "readable", "A text-based PDF", "No readable text (scan or image)",
            "The document couldn't be read")
        return issues
    if vtype and vtype not in accepted_types(doc_type, rule):
        add("DOC_UNSUPPORTED", "accepted_types", " or ".join(accepted_types(doc_type, rule)),
            TYPE_LABEL.get(vtype, vtype), f"{TYPE_LABEL.get(vtype, vtype)} isn't accepted here")
        return issues
    # identity fields
    if c.get("pan_match") is False:
        add("PAN_MISMATCH", "pan_match", "Your KYC PAN", f.get("pan_masked", "Different PAN"), "PAN differs from KYC")
    if doc_type in ("PAN", "IDENTITY") or rule.get("name_match"):
        score = c.get("name_match")
        if score is not None and score < 0.85:
            ftype = "STATEMENT_REJECTED" if doc_type == "BANK_STATEMENT" else "NAME_MISMATCH"
            add(ftype, "name_match", f"Name matching '{user['name']}' (score ≥ 0.85)",
                f"'{f.get('name')}' (score {score:.2f})", "Name doesn't match your PAN")
    if (doc_type in ("PAN", "IDENTITY") or rule.get("dob_match")) and c.get("dob_match") is False:
        add("DOB_MISMATCH", "dob_match", f"Date of birth {user['dob']}", f.get("dob", "—"),
            "Date of birth differs from KYC")
    if (rule.get("unexpired") or doc_type == "IDENTITY") and c.get("expired"):
        add("DOC_EXPIRED", "unexpired", "A document that hasn't expired", f"Expired on {f.get('expiry_date')}",
            "The document has expired")
    # statement rules
    if doc_type == "BANK_STATEMENT":
        if rule.get("min_months") and (f.get("months") or 0) < rule["min_months"]:
            add("STATEMENT_PERIOD_INSUFFICIENT", "min_months", f"{rule['min_months']} months (latest complete months)",
                f"{f.get('months', 0)} month{'s' if f.get('months', 0) != 1 else ''} · {f.get('period_label', 'unknown period')}",
                f"Statement covers {f.get('months', 0)} of the {rule['min_months']} months required")
        if rule.get("max_age_days") and (c.get("age_days") or 0) > rule["max_age_days"]:
            add("DOC_EXPIRED", "max_age_days", f"Issued within {rule['max_age_days']} days",
                f"Issued {c.get('age_days')} days ago", "Statement is too old")
        if rule.get("salary_credits") and (f.get("salary_credits") or 0) < rule["salary_credits"]:
            add("SALARY_CREDIT_NOT_DETECTED", "salary_credits", "At least one salary credit", "No salary credits found",
                "No salary credits in the statement")
    if doc_type == "SALARY_SLIP":
        if rule.get("max_age_days") and (c.get("age_days") or 0) > rule["max_age_days"]:
            add("DOC_EXPIRED", "max_age_days", f"Issued within {rule['max_age_days']} days",
                f"Issued {c.get('age_days')} days ago", "Salary slip is too old")
        income = (application or {}).get("monthly_income")
        if rule.get("income_tolerance") and income and f.get("net_pay"):
            gap = abs(income - f["net_pay"]) / f["net_pay"]
            if gap > rule["income_tolerance"]:
                add("INCOME_MISMATCH", "income_tolerance",
                    f"Declared income within {int(rule['income_tolerance'] * 100)}% of net pay",
                    f"Declared ₹{income:,.0f} vs net pay ₹{f['net_pay']:,.0f} ({gap:.0%} apart)",
                    "Declared income doesn't match the salary slip")
    return issues


def ordered(requirements: dict, application: dict | None = None) -> list[tuple[str, dict]]:
    """Requirements in evaluation order, skipping conditional ones that don't apply."""
    out = []
    for dt in sorted(requirements, key=lambda d: ORDER.index(d) if d in ORDER else 99):
        rule = requirements[dt] or {}
        if rule.get("when_age_over") and (application or {}).get("age", 0) <= rule["when_age_over"]:
            continue
        out.append((dt, rule))
    return out


def role_for(doc_type: str) -> str:
    return doc_type.lower()


def age_of(dob: str) -> int:
    d, t = date.fromisoformat(dob), date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))
