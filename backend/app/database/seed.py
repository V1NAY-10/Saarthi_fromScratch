"""Reference data only: partners, the fund catalog and the knowledge base.

There is no demo user, no pre-made journey and no pre-broken state. Everything
a user sees is created by what they do in the app (register, link accounts,
start SIPs) and by how the sandbox partners respond to it."""
from app.database import db
from app.knowledge.entries import FAILURE_CODES, POLICIES

PARTNERS = [
    ("axis", "Axis Bank", "bank", "NPCI NACH dialect"),
    ("icici", "ICICI Bank", "bank", "NPCI NACH dialect"),
    ("hdfc", "HDFC Bank", "bank", "JSON envelope dialect"),
    ("sbi", "SBI", "bank", "JSON envelope dialect"),
    ("aa", "Account Aggregator", "aa", "Consent-based data"),
    ("nsdl", "PAN Registry (NSDL)", "registry", "Identity"),
]

# Fictional fund houses. NAVs and returns are illustrative sandbox numbers.
FUNDS = [
    ("f-nimbus-bluechip", "Nimbus Bluechip Fund", "Nimbus Mutual Fund", "Large Cap", "Moderately High",
     58.42, 14.2, 13.1, 15.4, 500, 0.62, 41250),
    ("f-vistara-flexi", "Vistara Flexi Cap Fund", "Vistara Mutual Fund", "Flexi Cap", "Very High",
     74.10, 18.9, 17.2, 19.8, 1000, 0.71, 28730),
    ("f-kaveri-midcap", "Kaveri Mid Cap Opportunities", "Kaveri Mutual Fund", "Mid Cap", "Very High",
     112.35, 26.4, 22.8, 24.1, 1000, 0.79, 19840),
    ("f-ganga-smallcap", "Ganga Small Cap Fund", "Ganga Mutual Fund", "Small Cap", "Very High",
     41.77, 31.2, 26.5, 28.9, 1000, 0.88, 12410),
    ("f-sahyadri-nifty", "Sahyadri Nifty 50 Index Fund", "Sahyadri Mutual Fund", "Index", "Moderately High",
     23.65, 13.4, 12.6, 14.9, 100, 0.18, 9620),
    ("f-narmada-elss", "Narmada ELSS Tax Saver", "Narmada Mutual Fund", "ELSS", "Very High",
     96.20, 17.5, 15.9, 18.2, 500, 0.74, 15330),
    ("f-godavari-baf", "Godavari Balanced Advantage", "Godavari Mutual Fund", "Hybrid", "Moderate",
     34.88, 11.2, 10.8, 12.1, 500, 0.66, 22160),
    ("f-yamuna-debt", "Yamuna Short Duration Fund", "Yamuna Mutual Fund", "Debt", "Low to Moderate",
     27.14, 7.4, 6.6, 6.9, 500, 0.35, 8050),
]


def seed() -> None:
    """Wipe everything and load reference data."""
    db.init_schema(drop=True)
    for p in PARTNERS:
        db.insert("partners", {"id": p[0], "name": p[1], "kind": p[2], "api_style": p[3]})
    for f in FUNDS:
        db.insert("funds", dict(zip(["id", "name", "amc", "category", "risk", "nav", "returns_1y", "returns_3y",
                                     "returns_5y", "min_sip", "expense_ratio", "aum_cr"], f)))
    for k in FAILURE_CODES:
        db.insert("knowledge_entries", {"id": k["id"], "kind": "failure_code", "partner_id": k["partner_id"],
                                        "code": k["code"], "title": k["title"], "body": k["body"], "data": k["data"]})
    for p in POLICIES:
        db.insert("knowledge_entries", {"id": p["id"], "kind": p["kind"], "partner_id": None, "code": None,
                                        "title": p["title"], "body": p["body"], "data": {}})
