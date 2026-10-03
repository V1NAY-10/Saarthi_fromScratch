"""Knowledge retrieval for Saarthi.

Two layers, both over the Markdown knowledge base:

  1. Exact lookup  - registry.entry(partner, code): deterministic, used to decide.
  2. RAG           - semantic retrieval of the relevant sections, used to ground
                     and explain. Engine:
                       * Cognee (cognee.remember / cognee.recall) when installed and
                         ingested - runs keyless with Cognee's local CPU models;
                       * BM25 over the same chunks otherwise, reported as a fallback.

Every hit carries the engine that produced it, so the UI never presents a BM25
result as Cognee's."""
import asyncio
import hashlib
import json
import logging
import math
import re
import threading
from collections import Counter

from app.config import DATA_DIR
from app.knowledge import registry

log = logging.getLogger("saarthi.rag")
DATASET = "saarthi_kb"
STATE_FILE = DATA_DIR / ".cognee_state.json"

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "in", "for", "be", "on", "by", "with", "it", "as", "that",
         "this", "are", "at", "from", "if", "not", "any", "no", "can", "may", "must", "yes"}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall((text or "").lower()) if t not in _STOP]


class BM25Index:
    def __init__(self, docs: list[dict], k1: float = 1.4, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.toks = [_tokens(f"{d['title']} {d['title']} {d.get('code') or ''} {d.get('partner_id') or ''} {d['text']}")
                     for d in docs]
        self.avgdl = sum(len(t) for t in self.toks) / max(len(self.toks), 1)
        df = Counter()
        for t in self.toks:
            df.update(set(t))
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.tf = [Counter(t) for t in self.toks]

    def search(self, query: str, k: int = 4, kinds: set[str] | None = None) -> list[dict]:
        q = _tokens(query)
        scored = []
        for i, d in enumerate(self.docs):
            if kinds and d["kind"] not in kinds:
                continue
            dl = len(self.toks[i])
            s = sum(self.idf[w] * self.tf[i][w] * (self.k1 + 1) /
                    (self.tf[i][w] + self.k1 * (1 - self.b + self.b * dl / self.avgdl)) for w in q if self.tf[i].get(w))
            if s > 0:
                scored.append((s, d))
        scored.sort(key=lambda x: -x[0])
        top = scored[:k]
        if not top:
            return []
        mx = top[0][0]
        return [{**d, "score": round(s / mx, 2)} for s, d in top]


_index: BM25Index | None = None


def index() -> BM25Index:
    global _index
    if _index is None:
        _index = BM25Index(registry.load()["chunks"])
    return _index


def reset_index() -> None:
    global _index
    _index = None


# ------------------------------------------------------------------ Cognee
class _Cognee:
    """Thin wrapper: one private event loop thread, because Cognee is async and the
    rest of Saarthi is sync (request handlers and agent threads)."""

    def __init__(self):
        self.state = "not_installed"   # not_installed | idle | ingesting | ready | failed
        self.error: str | None = None
        self.chunks_ingested = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        try:
            import cognee  # noqa: F401
            self.state = "idle"
        except Exception as e:  # not installed / import error
            self.error = f"{type(e).__name__}: {e}"[:200]

    def _run(self, coro, timeout: float):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            threading.Thread(target=self._loop.run_forever, daemon=True, name="cognee-loop").start()
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def kb_hash(self, chunks) -> str:
        return hashlib.sha256("".join(c["id"] + c["text"] for c in chunks).encode()).hexdigest()[:16]

    def ingest(self, force: bool = False) -> None:
        if self.state == "not_installed":
            return
        with self._lock:
            chunks = registry.load()["chunks"]
            h = self.kb_hash(chunks)
            try:
                saved = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
            except Exception:
                saved = {}
            if saved.get("hash") == h and not force:
                self.state, self.chunks_ingested = "ready", saved.get("chunks", 0)
                return
            self.state, self.error = "ingesting", None
            try:
                import cognee

                async def go():
                    if force or saved:
                        try:
                            await cognee.forget(dataset=DATASET)
                        except Exception as e:  # first run / API difference: continue with a fresh add
                            log.info("cognee.forget skipped: %s", e)
                    for c in chunks:
                        await cognee.remember(_doc_text(c), dataset_name=DATASET)

                self._run(go(), timeout=1800)
                STATE_FILE.write_text(json.dumps({"hash": h, "chunks": len(chunks)}))
                self.state, self.chunks_ingested = "ready", len(chunks)
                log.info("Cognee ingested %d knowledge chunks", len(chunks))
            except Exception as e:
                self.state, self.error = "failed", f"{type(e).__name__}: {e}"[:300]
                log.warning("Cognee ingestion failed - using BM25 fallback: %s", self.error)

    def search(self, query: str, k: int) -> list[dict] | None:
        if self.state != "ready":
            return None
        try:
            import cognee
            raw = self._run(cognee.recall(query, datasets=[DATASET]), timeout=60)
        except Exception as e:
            log.warning("Cognee recall failed - BM25 fallback for this query: %s", e)
            return None
        by_id = {c["id"]: c for c in registry.load()["chunks"]}
        hits, seen = [], set()
        for i, text in enumerate(_texts(raw)):
            m = re.search(r"\[kb:([^\]]+)\]", text)
            c = by_id.get(m.group(1)) if m else None
            if not c or c["id"] in seen:
                continue
            seen.add(c["id"])
            hits.append({**c, "score": round(1 - i / max(k * 2, 1), 2)})
            if len(hits) >= k:
                break
        return hits


def _doc_text(c: dict) -> str:
    # The [kb:id] tag lets recall results be mapped back to the exact Markdown section.
    return f"[kb:{c['id']}] {c['title']}\n\n{c['text']}"


def _texts(raw) -> list[str]:
    """Flatten whatever recall returns (strings, dicts, objects, nested lists) into texts."""
    out = []

    def walk(x):
        if x is None:
            return
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for key in ("text", "content", "chunk", "search_result", "result", "payload"):
                if key in x:
                    walk(x[key])
                    return
            out.append(json.dumps(x, default=str))
        elif isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
        else:
            for attr in ("text", "content", "search_result", "payload"):
                if hasattr(x, attr):
                    walk(getattr(x, attr))
                    return
            out.append(str(x))
    walk(raw)
    return out


cognee_engine = _Cognee()


def start_background_ingest() -> None:
    if cognee_engine.state == "idle":
        threading.Thread(target=cognee_engine.ingest, daemon=True, name="cognee-ingest").start()


def status() -> dict:
    c = cognee_engine
    active = "cognee" if c.state == "ready" else "bm25"
    reason = {"ready": f"Cognee ready · {c.chunks_ingested} sections ingested",
              "ingesting": "Cognee is ingesting the knowledge base; BM25 is answering meanwhile",
              "failed": f"Cognee ingestion failed ({c.error}); using BM25 fallback",
              "not_installed": "Cognee not installed; using BM25 fallback",
              "idle": "Cognee installed, ingestion not started; using BM25 fallback"}[c.state]
    return {"active_engine": active, "cognee_state": c.state, "reason": reason,
            "sections": len(registry.load()["chunks"]), "failure_codes": len(registry.load()["codes"])}


# ------------------------------------------------------------------ public API
def search(query: str, k: int = 4, partner_id: str | None = None) -> list[dict]:
    """RAG retrieval. Returns relevant knowledge sections, each tagged with its engine."""
    hits = cognee_engine.search(query, k)
    engine = "cognee"
    if hits is None:
        engine = "bm25"
        hits = index().search(query, k=k + 3)
    if partner_id:  # a partner's own sections first, then general policy
        hits = sorted(hits, key=lambda h: (h.get("partner_id") not in (partner_id, None), -h["score"]))
    return [{"id": h["id"], "title": h["title"], "source": h["source"], "kind": h["kind"],
             "partner_id": h.get("partner_id"), "code": h.get("code"), "body": h["text"][:600],
             "score": h["score"], "engine": engine} for h in hits[:k]]


def lookup_code(partner_id: str, code: str | None) -> dict | None:
    d = registry.entry(partner_id, code)
    if not d:
        return None
    chunk = next((c for c in registry.load()["chunks"] if c["partner_id"] == partner_id and c["code"] == code), None)
    return {"id": chunk["id"] if chunk else f"{partner_id}:{code}", "title": chunk["title"] if chunk else code,
            "body": chunk["text"] if chunk else "", "source": chunk["source"] if chunk else "", "data": d}


def equivalent_codes(standard_code: str) -> list[dict]:
    return registry.equivalents(standard_code)


def retrieve_for(query: str, k: int = 4, partner_id: str | None = None) -> list[dict]:
    return [h for h in search(query, k=k, partner_id=partner_id) if h["score"] >= 0.2]
