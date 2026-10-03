"""Failure Knowledge Graph - a compact, journey-specific slice of the graph:

Partner -> Partner status -> Failure type -> Root cause -> Evidence -> Action -> Outcome

plus cross-partner 'equivalent' edges showing other partner codes that
normalize to the same standard failure."""
from app.database import db


def build(diag: dict, decision: dict | None, journey_status: str) -> dict:
    if diag.get("status") != "DIAGNOSED":
        return {"nodes": [], "edges": []}
    n = diag["normalized"]
    primary = next((o for o in diag["options"] if o["recommended"]), None)
    resolved = journey_status in ("RESOLVED", "ESCALATED")
    ev_ok = all(e["verified"] for e in diag["evidence"])
    nodes = [
        {"id": "partner", "kind": "partner", "label": diag["partner"]["partner_name"], "state": "done"},
        {"id": "status", "kind": "status", "label": n["partner_code"], "state": "done"},
        {"id": "failure", "kind": "failure", "label": n["meaning"], "sub": n["standard_code"], "state": "done"},
        {"id": "cause", "kind": "cause", "label": n["root_cause"],
         "state": "done" if diag["root_cause_confirmed"] else "warn"},
        {"id": "evidence", "kind": "evidence",
         "label": " + ".join(e["label"] for e in diag["evidence"][:2]), "state": "done" if ev_ok else "warn"},
        {"id": "action", "kind": "action", "label": primary["title"] if primary else "—",
         "sub": decision["tier"] if decision else None, "state": "done" if resolved else "active"},
        {"id": "outcome", "kind": "outcome", "label": n["expected_outcome"],
         "state": "done" if resolved else "pending"},
    ]
    edges = [{"from": a, "to": b, "label": l} for a, b, l in [
        ("partner", "status", "returns"), ("status", "failure", "normalizes to"), ("failure", "cause", "caused by"),
        ("cause", "evidence", "proven by"), ("evidence", "action", "enables"), ("action", "outcome", "leads to")]]
    names = {r["id"]: r["name"] for r in db.query("SELECT id, name FROM partners")}
    for i, eq in enumerate(x for x in n["equivalents"] if x["code"] != n["partner_code"]):
        nid = f"eq{i}"
        nodes.append({"id": nid, "kind": "equivalent", "label": eq["code"], "sub": names.get(eq["partner_id"]),
                      "state": "ghost"})
        edges.append({"from": nid, "to": "failure", "label": "same failure"})
    return {"nodes": nodes, "edges": edges}
