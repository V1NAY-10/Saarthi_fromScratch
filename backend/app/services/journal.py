"""Journey memory (timeline events) and the Saarthi audit log."""
from app.database import db


def add_event(journey_id: str, kind: str, title: str, detail: str = "", status: str = "done",
              actor: str = "saarthi", stage: str = "perceive", meta: dict | None = None) -> None:
    db.insert("journey_events", {"journey_id": journey_id, "ts": db.now_iso(), "kind": kind, "title": title,
                                 "detail": detail, "status": status, "actor": actor, "loop_stage": stage,
                                 "meta": meta or {}})


def _user_of(journey_id: str | None) -> str | None:
    if not journey_id:
        return None
    j = db.query_one("SELECT user_id FROM journeys WHERE id=?", (journey_id,))
    return j["user_id"] if j else None


def audit(journey_id: str | None, actor: str, event_type: str, summary: str, data: dict | None = None,
          user_id: str | None = None) -> None:
    db.insert("audit_logs", {"ts": db.now_iso(), "user_id": user_id or _user_of(journey_id), "journey_id": journey_id,
                             "actor": actor, "event_type": event_type, "summary": summary, "data": data or {}})


def timeline(journey_id: str) -> list[dict]:
    return db.query("SELECT * FROM journey_events WHERE journey_id=? ORDER BY ts, id", (journey_id,))


def audit_log(journey_id: str | None = None, limit: int = 100, user_id: str | None = None) -> list[dict]:
    if journey_id:
        return db.query("SELECT * FROM audit_logs WHERE journey_id=? ORDER BY id DESC LIMIT ?", (journey_id, limit))
    if user_id:
        return db.query("SELECT * FROM audit_logs WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
    return db.query("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
