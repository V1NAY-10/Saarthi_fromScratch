"""Journey Context Engine - assembles everything Saarthi knows about a journey
from the system of record. Every downstream engine (and the LLM agent) reasons
only over this structured context."""
from datetime import datetime, timezone

from app.database import db
from app.services import journal


def hours_since(iso: str | None) -> float | None:
    if not iso:
        return None
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600


def hours_until(iso: str | None) -> float | None:
    h = hours_since(iso)
    return None if h is None else -h


def get_journey(journey_id: str) -> dict:
    j = db.query_one("SELECT * FROM journeys WHERE id=?", (journey_id,))
    if not j:
        raise KeyError(journey_id)
    return j


def build(journey_id: str) -> dict:
    j = get_journey(journey_id)
    st = j["state"]
    user = db.query_one("SELECT * FROM users WHERE id=?", (j["user_id"],))
    accounts = db.query("SELECT * FROM accounts WHERE user_id=? ORDER BY created_at", (j["user_id"],))
    linked = next((a for a in accounts if a["id"] == st.get("account_id")), None)
    sip = db.query_one("SELECT * FROM sips WHERE id=?", (st["sip_id"],)) if st.get("sip_id") else None
    mandate = db.query_one("SELECT * FROM mandates WHERE id=?", (st["mandate_id"],)) if st.get("mandate_id") else None
    fund = db.query_one("SELECT * FROM funds WHERE id=?", (sip["fund_id"],)) if sip else None
    docs = db.query("SELECT * FROM documents WHERE user_id=? ORDER BY updated_at DESC", (j["user_id"],))
    partner = db.query_one("SELECT * FROM partners WHERE id=?", (j["partner_id"],))
    since = st.get("incident_started_at") or ""
    actions = db.query("SELECT * FROM actions WHERE journey_id=? AND created_at>=? ORDER BY created_at",
                       (journey_id, since))
    events = journal.timeline(journey_id)
    return {
        "journey": j,
        "user": {"id": user["id"], "name": user["name"], "pan": user["pan"], "kyc_status": user["kyc_status"],
                 "dob": user["dob"]},
        "partner": partner, "accounts": accounts, "linked_account": linked, "sip": sip, "mandate": mandate,
        "fund": fund, "documents": docs, "events": events, "previous_actions": actions,
        "previous_failures": [e for e in events if e["status"] == "failed"],
    }


def summary_for_agent(ctx: dict) -> dict:
    """A compact, PAN-masked view for the LLM."""
    j, st = ctx["journey"], ctx["journey"]["state"]
    acc = ctx["linked_account"]
    out = {
        "journey": {"id": j["id"], "type": j["category"], "title": j["title"], "partner": ctx["partner"]["name"],
                    "partner_ref": j["partner_ref"], "status": j["status"], "stage": j["stage"],
                    "amount": j["amount"], "failure_code": st.get("failure_code"),
                    "incident_number": st.get("incident")},
        "customer": {"name_on_pan": ctx["user"]["name"], "kyc_status": ctx["user"]["kyc_status"]},
        "account_in_question": {"id": acc["id"], "bank": acc["bank"], "masked": acc["masked"],
                                "status": acc["status"], "balance": acc["balance"]} if acc else None,
        "recent_events": [f"{e['title']} - {e['detail']}" for e in ctx["events"][-8:]],
    }
    if ctx["sip"]:
        s = ctx["sip"]
        out["sip"] = {"fund": ctx["fund"]["name"], "amount": s["amount"], "installments_paid": s["installments_paid"],
                      "sip_day": s["sip_day"]}
    if ctx["mandate"]:
        out["mandate"] = {"umrn": ctx["mandate"]["umrn"], "max_amount": ctx["mandate"]["max_amount"],
                          "status": ctx["mandate"]["status"]}
    if st.get("aa_ownership"):
        out["previous_ownership_check"] = st["aa_ownership"]
    return out
