"""Synthetic sample documents for the sandbox.

Generates small, real PDFs (with a text layer) personalised to the signed-in user,
so the demo exercises the actual upload -> extraction -> classification pipeline.
Every sample is marked SANDBOX / SYNTHETIC on the page."""
import calendar
import hashlib
import random
from datetime import date, timedelta


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines: list[str], with_text: bool = True) -> bytes:
    """Minimal single-page PDF. with_text=False draws only shapes (an 'unreadable scan')."""
    if with_text:
        body = "BT /F1 10 Tf 48 800 Td 15 TL " + "".join(f"({_esc(l)}) Tj T* " for l in lines) + "ET"
    else:
        body = "0.6 g 40 300 515 480 re f 0.3 g 80 700 300 40 re f 80 600 420 18 re f 80 560 380 18 re f"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(body.encode('latin-1'))} >>\nstream\n{body}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def _month_start(d: date, back: int) -> date:
    y, m = d.year, d.month - back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _fmt(d: date) -> str:
    return d.strftime("%d %b %Y")


def _money(n: float) -> str:
    return f"Rs {n:,.2f}"


SAMPLES = {
    "bank_statement_1m": "Bank statement · 1 month",
    "bank_statement_3m": "Bank statement · 3 months",
    "salary_slip": "Salary slip · last month",
    "pan_card": "PAN card",
    "aadhaar": "Aadhaar card",
    "aadhaar_wrong_dob": "Aadhaar card · different date of birth",
    "driving_licence_expired": "Driving licence · expired",
    "medical_report": "Medical report",
    "statement_other_person": "Bank statement · someone else's",
    "unreadable_scan": "Scanned statement · no text layer",
}


def generate(kind: str, user: dict, account: dict | None) -> tuple[bytes, str]:
    """Returns (pdf_bytes, filename)."""
    today = date.today()
    name = user["name"]
    acct = (account or {}).get("account_no") or "5010" + str(int(hashlib.sha256(user["id"].encode()).hexdigest(), 16))[:8]
    bank = (account or {}).get("bank") or "HDFC Bank"
    net_pay = 92400.0
    head = ["SANDBOX DOCUMENT - SYNTHETIC DATA - NOT A REAL RECORD", f"Sample ref: {random.randint(10**7, 10**8 - 1)}", ""]

    if kind in ("bank_statement_1m", "bank_statement_3m", "statement_other_person", "unreadable_scan"):
        months = 1 if kind == "bank_statement_1m" else 3
        holder = "Suresh Patel" if kind == "statement_other_person" else name
        end = _month_end(_month_start(today, 1))
        start = _month_start(today, months)
        lines = head + [f"{bank.upper()} - STATEMENT OF ACCOUNT", f"Account Holder: {holder}",
                        f"Account Number: {acct}", f"Statement Period: {_fmt(start)} to {_fmt(end)}",
                        f"Generated On: {_fmt(today - timedelta(days=2))}", "", "Date        Narration                 Amount"]
        bal = 41000.0
        for i in range(months, 0, -1):
            ms = _month_start(today, i)
            lines.append(f"{_fmt(ms.replace(day=1))}  SALARY CREDIT NIMBUS ANALYTICS  +{_money(net_pay)}")
            lines.append(f"{_fmt(ms.replace(day=5))}  UPI/RENT                       -{_money(22000)}")
            lines.append(f"{_fmt(ms.replace(day=12))}  CARD/GROCERY                  -{_money(8400)}")
            bal += net_pay - 30400
        lines += ["", f"Closing Balance: {_money(bal)}"]
        fname = "scanned_bank_statement.pdf" if kind == "unreadable_scan" else f"{kind}.pdf"
        return make_pdf(lines, with_text=kind != "unreadable_scan"), fname

    if kind == "salary_slip":
        pm = _month_start(today, 1)
        lines = head + ["NIMBUS ANALYTICS PVT LTD - PAY SLIP", f"Pay slip for {pm.strftime('%B %Y')}",
                        f"Employee Name: {name}", "Employee ID: NA-20417", f"Gross Pay: {_money(118000)}",
                        f"Deductions: {_money(25600)}", f"Net Pay: {_money(net_pay)}",
                        f"Issued On: {_fmt(_month_end(pm))}"]
        return make_pdf(lines), "salary_slip.pdf"

    if kind == "pan_card":
        lines = head + ["INCOME TAX DEPARTMENT - PERMANENT ACCOUNT NUMBER CARD", f"Name: {name}",
                        f"Date of Birth: {date.fromisoformat(user['dob']).strftime('%d/%m/%Y')}",
                        f"Permanent Account Number: {user['pan']}"]
        return make_pdf(lines), "pan_card.pdf"

    if kind == "aadhaar":
        lines = head + ["AADHAAR - UNIQUE IDENTIFICATION (SANDBOX)", f"Name: {name}",
                        f"Date of Birth: {date.fromisoformat(user['dob']).strftime('%d/%m/%Y')}",
                        f"Aadhaar Number: XXXX XXXX {random.randint(1000, 9999)}"]
        return make_pdf(lines), "aadhaar.pdf"

    if kind == "aadhaar_wrong_dob":
        d = date.fromisoformat(user["dob"])
        wrong = d.replace(month=(d.month % 12) + 1, day=min(d.day, 28))
        lines = head + ["AADHAAR - UNIQUE IDENTIFICATION (SANDBOX)", f"Name: {name}",
                        f"Date of Birth: {wrong.strftime('%d/%m/%Y')}",
                        f"Aadhaar Number: XXXX XXXX {random.randint(1000, 9999)}"]
        return make_pdf(lines), "aadhaar_card.pdf"

    if kind == "driving_licence_expired":
        lines = head + ["DRIVING LICENCE (SANDBOX)", f"Name: {name}",
                        f"Date of Birth: {date.fromisoformat(user['dob']).strftime('%d/%m/%Y')}",
                        f"Licence Number: MH12 2014 00{random.randint(10000, 99999)}",
                        f"Valid Till: {_fmt(today - timedelta(days=40))}"]
        return make_pdf(lines), "driving_licence.pdf"

    if kind == "medical_report":
        lines = head + ["SANDBOX DIAGNOSTICS - PRE-POLICY MEDICAL REPORT", f"Patient Name: {name}",
                        f"Report Date: {_fmt(today - timedelta(days=6))}", "Result: Within normal limits"]
        return make_pdf(lines), "medical_report.pdf"

    raise KeyError(kind)
