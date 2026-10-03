from fastapi import APIRouter, Depends

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
def search(q: str, k: int = 5, partner_id: str | None = None):
    """RAG retrieval over the Markdown knowledge base (Cognee, or BM25 fallback)."""
    return {"status": retrieval.status(), "hits": retrieval.search(q, k=k, partner_id=partner_id)}


@router.get("/knowledge/status")
def knowledge_status():
    return retrieval.status()


@router.post("/knowledge/reingest")
def reingest():
    """Reload the Markdown files and re-ingest them into Cognee (in the background)."""
    from app.database import seed
    seed.load_knowledge()
    retrieval.reset_index()
    import threading
    threading.Thread(target=retrieval.cognee_engine.ingest, kwargs={"force": True}, daemon=True).start()
    return retrieval.status()
