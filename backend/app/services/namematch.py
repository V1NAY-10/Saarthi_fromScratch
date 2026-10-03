"""Explainable person-name matching, the way bank account verification does it.

score(a, b) returns 0..1 plus the reasons, so the UI and the agent can show
*why* two names were judged similar ("middle name missing", "initial matches")."""
import re
from difflib import SequenceMatcher

_HONORIFICS = {"mr", "mrs", "ms", "miss", "dr", "shri", "smt", "kumari"}


def _tokens(name: str) -> list[str]:
    toks = re.sub(r"[^a-z ]", " ", (name or "").lower()).split()
    return [t for t in toks if t not in _HONORIFICS]


def _tok_match(a: str, b: str) -> tuple[float, str]:
    if a == b:
        return 1.0, "exact"
    if len(a) == 1 and b.startswith(a) or len(b) == 1 and a.startswith(b):
        return 0.6, "initial"
    r = SequenceMatcher(None, a, b).ratio()
    return (round(r * 0.9, 2), "spelling") if r >= 0.8 else (0.0, "different")


def score(a: str, b: str) -> dict:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return {"score": 0.0, "verdict": "different", "reasons": ["Name missing"], "pairs": []}
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    used, pairs, total = set(), [], 0.0
    for t in short:
        best = (0.0, "different", None)
        for j, u in enumerate(long_):
            if j in used:
                continue
            s, kind = _tok_match(t, u)
            if s > best[0]:
                best = (s, kind, j)
        if best[2] is not None:
            used.add(best[2])
        pairs.append({"token": t, "matched": long_[best[2]] if best[2] is not None else None, "kind": best[1]})
        total += best[0]
    coverage = total / len(short)
    extra = len(long_) - len(short)
    # an unmatched extra token (a middle name) costs a little; first/last order changes cost nothing
    s = round(max(0.0, coverage - 0.1 * extra), 2)
    reasons = []
    if any(p["kind"] == "initial" for p in pairs):
        reasons.append("Initials used for part of the name")
    if extra:
        reasons.append(f"{extra} extra name part{'s' if extra > 1 else ''} (e.g. middle name)")
    if any(p["kind"] == "spelling" for p in pairs):
        reasons.append("Minor spelling difference")
    matched_idx = [long_.index(p["matched"]) for p in pairs if p["matched"]]
    if matched_idx != sorted(matched_idx):
        reasons.append("Name parts in a different order")
    if any(p["kind"] == "different" for p in pairs):
        reasons.append("Some name parts don't match at all")
    verdict = "match" if s >= 0.85 else "partial" if s >= 0.5 else "different"
    if s >= 0.85 and not reasons:
        reasons.append("Names are identical")
    return {"score": s, "verdict": verdict, "reasons": reasons, "pairs": pairs}
