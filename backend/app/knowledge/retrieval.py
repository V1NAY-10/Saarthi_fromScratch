"""Lightweight retrieval: exact structured lookup for partner codes + BM25 over
all knowledge text. No external vector DB - deterministic, fast, explainable."""
import math
import re
from collections import Counter

from app.database import db

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "in", "for", "be", "on", "by", "with", "it", "as",
         "that", "this", "are", "at", "from", "if", "not", "any", "no", "can", "may", "must"}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25Index:
    def __init__(self, docs: list[dict], k1: float = 1.4, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.toks = [_tokens(f"{d['title']} {d['title']} {d.get('code') or ''} {d.get('partner_id') or ''} {d['body']}")
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
            s = 0.0
            for w in q:
                f = self.tf[i].get(w)
                if not f:
                    continue
                s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
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
        _index = BM25Index(db.query("SELECT * FROM knowledge_entries"))
    return _index


def reset_index() -> None:
    global _index
    _index = None


def lookup_code(partner_id: str, code: str) -> dict | None:
    return db.query_one("SELECT * FROM knowledge_entries WHERE kind='failure_code' AND partner_id=? AND code=?",
                        (partner_id, code))


def equivalent_codes(standard_code: str) -> list[dict]:
    """Cross-partner view: all partner codes that normalize to the same standard failure."""
    rows = db.query("SELECT * FROM knowledge_entries WHERE kind='failure_code'")
    return [{"partner_id": r["partner_id"], "code": r["code"]} for r in rows
            if r["data"] and r["data"].get("standard_code") == standard_code]


def retrieve_for(query: str, k: int = 4) -> list[dict]:
    hits = index().search(query, k=k, kinds={"action_constraint", "journey_policy", "recovery_policy",
                                             "document_requirement"})
    return [{"id": h["id"], "kind": h["kind"], "title": h["title"], "body": h["body"], "score": h["score"]}
            for h in hits if h["score"] >= 0.25]
