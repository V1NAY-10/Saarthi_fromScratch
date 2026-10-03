"""Document intelligence: text extraction, classification and field extraction.

Text comes from the PDF's text layer (pypdf) or plain-text files. Images and
scans without a text layer are stored but marked unreadable - Saarthi does not
pretend to have read them. Fields that identify a person are masked before they
are stored in metadata; raw text is kept server-side only and never returned by
the API."""
import io
import re
from datetime import date, datetime

from app.services import namematch

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"], 1)}
TYPE_LABEL = {"BANK_STATEMENT": "Bank statement", "SALARY_SLIP": "Salary slip", "PAN": "PAN card",
              "AADHAAR": "Aadhaar card", "DRIVING_LICENCE": "Driving licence", "MEDICAL_REPORT": "Medical report",
              "FORM16": "Form 16", "ADDRESS_PROOF": "Address proof", "CANCELLED_CHEQUE": "Cancelled cheque",
              "OTHER": "Other document"}
IDENTITY_TYPES = {"PAN", "AADHAAR", "DRIVING_LICENCE"}


def extract_text(data: bytes, mime: str) -> str:
    if mime == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages[:20]).strip()
        except Exception:
            return ""
    if mime.startswith("text/"):
        return data.decode("utf-8", errors="ignore")[:200000]
    return ""  # images: no OCR in the sandbox


def classify(text: str, filename: str, hint: str | None) -> str:
    t = (text + " " + filename).lower()
    rules = [("PAN", ["permanent account number", "income tax department", "pan_card"]),
             ("AADHAAR", ["aadhaar"]), ("DRIVING_LICENCE", ["driving licence", "driving license"]),
             ("SALARY_SLIP", ["pay slip", "payslip", "salary slip", "net pay"]),
             ("BANK_STATEMENT", ["statement of account", "statement period", "bank_statement", "closing balance"]),
             ("MEDICAL_REPORT", ["medical report", "diagnostics"]), ("FORM16", ["form 16", "form16"]),
             ("CANCELLED_CHEQUE", ["cancelled cheque"]), ("ADDRESS_PROOF", ["address proof", "utility bill"])]
    for dtype, keys in rules:
        if any(k in t for k in keys):
            return dtype
    return hint if hint in TYPE_LABEL else "OTHER"


def _date(s: str) -> date | None:
    s = s.strip()
    for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _find(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else None


def _mask_digits(s: str, keep: int = 4) -> str:
    d = re.sub(r"\D", "", s)
    return "XX" + d[-keep:] if len(d) > keep else s


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) + 1


def parse(doc_type: str, text: str) -> dict:
    f: dict = {}
    name = _find(r"(?:Account Holder|Employee Name|Patient Name|Name)\s*:\s*([A-Za-z .']+)", text)
    if name:
        f["name"] = " ".join(name.split())
    dob = _find(r"Date of Birth\s*:\s*([0-9/\-A-Za-z ]+?)(?:\n|$)", text)
    if dob and _date(dob):
        f["dob"] = _date(dob).isoformat()
    if doc_type == "BANK_STATEMENT":
        acct = _find(r"Account Number\s*:\s*([0-9X ]+)", text)
        if acct:
            f["account_masked"] = _mask_digits(acct)
        bank = _find(r"^\s*([A-Z][A-Z ]+?)\s*-\s*STATEMENT OF ACCOUNT", text) or _find(r"\n([A-Z][A-Z ]+?) - STATEMENT", text)
        if bank:
            f["bank"] = " ".join(w if w in ("HDFC", "SBI", "ICICI") else w.title() for w in bank.split())
        m = re.search(r"Statement Period\s*:\s*(.+?)\s+to\s+(.+?)(?:\n|$)", text, re.I)
        if m and _date(m.group(1)) and _date(m.group(2)):
            a, b = _date(m.group(1)), _date(m.group(2))
            f.update(period_start=a.isoformat(), period_end=b.isoformat(), months=_months_between(a, b),
                     period_label=f"{a:%b %Y}" if a.month == b.month and a.year == b.year else f"{a:%b}–{b:%b %Y}")
        gen = _find(r"Generated On\s*:\s*(.+)", text)
        if gen and _date(gen):
            f["issued_on"] = _date(gen).isoformat()
        f["salary_credits"] = len(re.findall(r"SALARY", text, re.I))
    elif doc_type == "SALARY_SLIP":
        f["employer"] = _find(r"^\s*(.+?)\s*-\s*PAY SLIP", text) or _find(r"\n(.+?) - PAY SLIP", text)
        pm = _find(r"Pay slip for\s+([A-Za-z]+ \d{4})", text)
        if pm:
            f["pay_month"] = pm
        net = _find(r"Net Pay\s*:\s*Rs\.?\s*([0-9,]+(?:\.\d+)?)", text)
        if net:
            f["net_pay"] = float(net.replace(",", ""))
        iss = _find(r"Issued On\s*:\s*(.+)", text)
        if iss and _date(iss):
            f["issued_on"] = _date(iss).isoformat()
    elif doc_type == "PAN":
        pan = _find(r"Permanent Account Number\s*:\s*([A-Z]{5}[0-9]{4}[A-Z])", text)
        if pan:
            f["pan_masked"] = pan[:5] + "••••" + pan[-1]
            f["_pan_hash"] = pan  # compared server-side only, stripped before returning
    elif doc_type == "AADHAAR":
        num = _find(r"Aadhaar Number\s*:\s*([0-9X ]+)", text)
        if num:
            f["number_masked"] = "XXXX XXXX " + re.sub(r"\D", "", num)[-4:]
    elif doc_type == "DRIVING_LICENCE":
        num = _find(r"Licence Number\s*:\s*([A-Z0-9 ]+)", text)
        if num:
            f["number_masked"] = num[:4] + " •••• " + num[-3:]
    elif doc_type == "MEDICAL_REPORT":
        rd = _find(r"Report Date\s*:\s*(.+)", text)
        if rd and _date(rd):
            f["issued_on"] = _date(rd).isoformat()
    exp = _find(r"(?:Valid Till|Valid Until|Expiry Date|Expires On)\s*:\s*(.+)", text)
    if exp and _date(exp):
        f["expiry_date"] = _date(exp).isoformat()
    return {k: v for k, v in f.items() if v not in (None, "")}


def checks(doc_type: str, fields: dict, readable: bool, user: dict) -> dict:
    """Customer-independent document checks (partner-specific rules are applied later)."""
    c = {"readable": readable}
    if fields.get("name"):
        m = namematch.score(fields["name"], user["name"])
        c["name_match"] = m["score"]
        c["name_verdict"] = m["verdict"]
    if fields.get("dob"):
        c["dob_match"] = fields["dob"] == user["dob"]
    if fields.get("_pan_hash"):
        c["pan_match"] = fields["_pan_hash"] == user["pan"]
    if fields.get("expiry_date"):
        days = (date.fromisoformat(fields["expiry_date"]) - date.today()).days
        c["expired"] = days < 0
        c["expiring_soon"] = 0 <= days <= 30
        c["days_to_expiry"] = days
    if fields.get("issued_on"):
        c["age_days"] = (date.today() - date.fromisoformat(fields["issued_on"])).days
    return c


def status_for(doc_type: str, fields: dict, c: dict) -> str:
    if not c["readable"]:
        return "UNREADABLE"
    if c.get("pan_match") is False or c.get("name_verdict") == "different":
        return "MISMATCH"
    if c.get("expired"):
        return "EXPIRED"
    if c.get("name_verdict") == "partial" or c.get("dob_match") is False:
        return "NEEDS_REVIEW"
    if c.get("expiring_soon"):
        return "EXPIRING_SOON"
    return "VERIFIED" if "name_match" in c else "AVAILABLE"


def public_fields(fields: dict) -> dict:
    return {k: v for k, v in fields.items() if not k.startswith("_")}


def summary(doc_type: str, fields: dict) -> str:
    if doc_type == "BANK_STATEMENT" and fields.get("months"):
        return f"{fields.get('bank', 'Bank')} {fields.get('account_masked', '')} · {fields['period_label']} · {fields['months']} month{'s' if fields['months'] != 1 else ''}"
    if doc_type == "SALARY_SLIP" and fields.get("pay_month"):
        return f"{fields['pay_month']} · net ₹{fields.get('net_pay', 0):,.0f}"
    if fields.get("pan_masked"):
        return fields["pan_masked"]
    if fields.get("number_masked"):
        return fields["number_masked"] + (f" · valid till {fields['expiry_date']}" if fields.get("expiry_date") else "")
    return fields.get("name", "")
