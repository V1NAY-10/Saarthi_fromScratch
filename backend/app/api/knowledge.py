from fastapi import APIRouter, Depends

from app.api.deps import current_user
from app.database import db
from app.knowledge import retrieval

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/knowledge")
def knowledge():
    entries = db.query("SELECT * FROM knowledge_entries ORDER BY kind, partner_id, id")
    stats = {r["id"]: r for r in db.query("SELECT * FROM failure_patterns")}
    for e in entries:
        s = stats.get(f"{e['partner_id']}:{e['code']}")
        if s and s["occurrences"]:
            e["learned"] = {"occurrences": s["occurrences"], "resolved": s["resolved"],
                            "success_rate": round(s["resolved"] / s["occurrences"], 4),
                            "avg_resolution_s": s["avg_resolution_s"], "last_outcome": s["last_outcome"]}
    return entries


@router.get("/knowledge/search")
def search(q: str, k: int = 5):
    return retrieval.index().search(q, k=k)


@router.get("/documents")
def documents(user=Depends(current_user)):
    return db.query("SELECT * FROM documents WHERE user_id=? ORDER BY updated_at DESC", (user["id"],))
