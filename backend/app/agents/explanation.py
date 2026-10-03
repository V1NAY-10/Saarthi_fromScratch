"""Explanation grounding.

Deterministic template explanations are always produced by the diagnosis
analyzers. When Claude writes the customer explanation (agent submit_plan, or a
chat answer), its text passes a grounding guard: every number it mentions must
exist in the verified context, otherwise the template is used. The LLM cannot
introduce a balance, amount or account that the backend didn't verify."""
import json
import re

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(text or "")}


def grounding_check(text: str, context: dict) -> dict:
    allowed = _numbers(json.dumps(context, ensure_ascii=False, default=str))
    # also allow integer forms of decimals present in the context (2586.0 -> 2586)
    allowed |= {a.split(".")[0] for a in allowed}
    used = _numbers(text)
    unsupported = sorted(n for n in used if n not in allowed)
    return {"passed": not unsupported, "numbers_checked": len(used), "unsupported": unsupported}


def llm_context(ctx: dict, diag: dict) -> dict:
    j = ctx["journey"]
    return {
        "journey": {"title": j["title"], "partner": ctx["partner"]["name"], "amount": j["amount"],
                    "status": j["status"], "stage": j["stage"]},
        "partner_response": diag.get("partner"),
        "normalized_failure": diag.get("normalized"),
        "verified_evidence": [{"label": e["label"], "value": e["display"], "source": e["source"]}
                              for e in diag.get("evidence", []) if e["verified"]],
        "facts": diag.get("facts"),
        "metrics": diag.get("metrics"),
        "missing_information": diag.get("missing"),
        "recovery_options": [{"title": o["title"], "description": o["description"]} for o in diag.get("options", [])],
        "retrieved_knowledge": [k["title"] + ": " + k["body"] for k in diag.get("knowledge", [])[:3]],
        "template": {"headline": diag["headline"], "summary": diag["summary"], "safety_note": diag["safety_note"]},
    }
