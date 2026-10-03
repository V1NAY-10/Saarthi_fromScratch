"""Journey bookkeeping shared by the product flows.

A journey is created by a real user action (linking a bank account, starting a
SIP). It becomes ATTENTION only when a partner actually rejects something - at
which point an incident is opened and Saarthi's agent is started."""
import uuid

from app.database import db
from app.services import journal


class ProductError(Exception):
    """A validation / business-rule error that should be shown to the user as-is."""


def create(user_id: str, category: str, title: str, subtitle: str, partner_id: str, ref: str, amount: float,
           stage: str, state: dict, status: str = "ON_TRACK") -> str:
    jid = f"j-{uuid.uuid4().hex[:8]}"
    now = db.now_iso()
    db.insert("journeys", {"id": jid, "user_id": user_id, "category": category, "title": title, "subtitle": subtitle,
                           "partner_id": partner_id, "partner_ref": ref, "amount": amount, "status": status,
                           "stage": stage, "state": state, "health_score": None, "created_at": now,
                           "updated_at": now})
    return jid


def get(jid: str) -> dict:
    return db.query_one("SELECT * FROM journeys WHERE id=?", (jid,))


def patch_state(jid: str, **changes) -> dict:
    j = get(jid)
    st = {**j["state"], **changes}
    db.update("journeys", "id", jid, {"state": st, "updated_at": db.now_iso()})
    return st


def open_incident(jid: str, code: str, message: str, actor: str, stage: str, **state) -> None:
    """A partner rejected something. Mark the journey, wipe the previous incident's
    diagnosis and hand it to Saarthi."""
    from app.agents import orchestrator  # late import: orchestrator imports product modules

    j = get(jid)
    incident = int(j["state"].get("incident", 0)) + 1
    st = {**j["state"], **state, "incident": incident, "incident_started_at": db.now_iso(),
          "failure_code": code, "case_id": None}
    db.update("journeys", "id", jid, {"status": "ATTENTION", "stage": stage, "state": st,
                                      "updated_at": db.now_iso()})
    db.execute("DELETE FROM diagnoses WHERE journey_id=?", (jid,))
    journal.add_event(jid, "partner", "Partner rejected the request", f"{code} · {message}", status="failed",
                      actor=actor, stage="perceive")
    orchestrator.start_agent(jid, reason=f"Partner returned {code}")


def close_incident(jid: str, status: str, stage: str, **state) -> None:
    j = get(jid)
    db.update("journeys", "id", jid, {"status": status, "stage": stage, "state": {**j["state"], **state},
                                      "updated_at": db.now_iso()})
