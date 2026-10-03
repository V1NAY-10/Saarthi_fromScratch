"""Loads the Markdown knowledge base (repo-root knowledge/) into two views:

  * the failure registry - deterministic, exact (partner, error_code) lookup built
    from each section's fenced yaml block; plus partner document requirements
    (`profile: true` blocks), which the sandbox partners and Saarthi's checks share
  * retrievable chunks - one per `##` section (prose only), fed to RAG

The Markdown files are the single source of truth."""
import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import BASE_DIR

KB_DIR = BASE_DIR.parent / "knowledge"
_YAML = re.compile(r"```yaml\n(.*?)```", re.S)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _compat(d: dict) -> dict:
    """Fields the original engines read, derived from the common schema."""
    return {**d, "meaning": d["customer_meaning"], "root_cause": d["possible_causes"][0],
            "recovery_actions": d["resolution_options"]}


@lru_cache(maxsize=1)
def load() -> dict:
    chunks, codes, profiles = [], {}, {}
    for path in sorted(KB_DIR.rglob("*.md")):
        rel = path.relative_to(KB_DIR).as_posix()
        if rel == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        for sec in re.split(r"\n(?=## )", text)[1:]:
            title = sec.splitlines()[0][3:].strip()
            m = _YAML.search(sec)
            data = yaml.safe_load(m.group(1)) if m else None
            prose = _YAML.sub("", sec[len(sec.splitlines()[0]):]).strip()
            kind = "policy"
            if data and data.get("profile"):
                kind = "partner_profile"
                profiles[data["partner"]] = data
            elif data and data.get("error_code"):
                kind = "failure_code"
                codes[(data["partner"], data["error_code"])] = _compat(data)
            folder = rel.split("/")[0]
            chunks.append({"id": f"{rel}#{_slug(title)}", "source": rel, "folder": folder, "title": title,
                           "text": prose, "kind": kind, "partner_id": (data or {}).get("partner"),
                           "code": (data or {}).get("error_code"), "data": data})
    by_type: dict[tuple, str] = {}
    for (pid, code), d in codes.items():
        by_type.setdefault((pid, d["failure_type"]), code)
    names = {d["partner"]: d["partner_name"] for d in list(codes.values()) + list(profiles.values())}
    return {"chunks": chunks, "codes": codes, "profiles": profiles, "by_type": by_type, "names": names}


def reload() -> dict:
    load.cache_clear()
    return load()


def entry(partner_id: str, code: str | None) -> dict | None:
    return load()["codes"].get((partner_id, code)) if code else None


def code_for(partner_id: str, failure_type: str) -> str | None:
    """The partner's own code for a normalized failure (used by the sandbox partners)."""
    return load()["by_type"].get((partner_id, failure_type))


def requirements(partner_id: str) -> dict:
    return (load()["profiles"].get(partner_id) or {}).get("requirements", {})


def partner_name(partner_id: str) -> str:
    return load()["names"].get(partner_id, partner_id)


def equivalents(standard_code: str) -> list[dict]:
    return [{"partner_id": pid, "code": c} for (pid, c), d in load()["codes"].items()
            if d.get("standard_code") == standard_code]
