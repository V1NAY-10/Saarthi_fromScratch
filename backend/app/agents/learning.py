"""Outcome / Learning Engine.

After every incident Saarthi records partner code -> action -> outcome ->
resolution time. These statistics start empty and grow only from real
outcomes in this deployment; they feed straight back into diagnosis confidence
(diagnosis.confidence), so each verified outcome sharpens the next diagnosis of
the same partner code."""
from app.agents.context import hours_since
from app.database import db
from app.services import journal


def record(journey: dict, diag: dict, action_type: str, outcome: str) -> dict:
    code = diag["normalized"]["partner_code"]
    pid = journey["partner_id"]
    key = f"{pid}:{code}"
    row = db.query_one("SELECT * FROM failure_patterns WHERE id=?", (key,)) or {
        "occurrences": 0, "resolved": 0, "avg_resolution_s": 0.0}
    secs = round((hours_since(journey["state"].get("incident_started_at")) or 0) * 3600)
    before = {"occurrences": row["occurrences"], "resolved": row["resolved"],
              "success_rate": row["resolved"] / row["occurrences"] if row["occurrences"] else None,
              "avg_resolution_s": row["avg_resolution_s"]}
    occ = row["occurrences"] + 1
    res = row["resolved"] + (1 if outcome == "SUCCESS" else 0)
    avg = round((row["avg_resolution_s"] * row["resolved"] + secs) / res, 1) if outcome == "SUCCESS" \
        else row["avg_resolution_s"]
    db.insert("failure_patterns", {"id": key, "partner_id": pid, "partner_code": code,
                                   "failure_type": diag["normalized"]["failure_type"],
                                   "root_cause": diag["normalized"]["root_cause"], "occurrences": occ,
                                   "resolved": res, "avg_resolution_s": avg, "last_outcome": outcome,
                                   "updated_at": db.now_iso()})
    after = {"occurrences": occ, "resolved": res, "success_rate": res / occ, "avg_resolution_s": avg}
    lesson = {"partner": pid, "partner_code": code, "failure_type": diag["normalized"]["failure_type"],
              "diagnosis": diag["normalized"]["root_cause"], "action": action_type, "outcome": outcome,
              "resolution_seconds": secs, "before": before, "after": after}
    journal.audit(journey["id"], "saarthi", "LEARN",
                  f"Outcome recorded for {code}: {outcome} via {action_type} in {secs}s", lesson)
    return lesson
