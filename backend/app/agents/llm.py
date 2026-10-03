"""LLM provider layer: Gemini (google-genai).

Two operations:

  complete(system, user)      one-shot text (chat answers, explanations)
  tool_loop(system, tools)    a manual function-calling loop the agent drives
                              one turn at a time: send() -> (texts, calls)

Optional by design: in DEMO_MODE, without a key, or on any provider error,
callers fall back to deterministic logic. The model never decides tiers and
never executes anything - tools return data, the safety engine decides.

Retry policy: on 429 / 503 (overloaded), we back off and retry up to 3 times
before giving up and letting the deterministic planner take over."""
import json
import logging
import re
import time

from app import config

log = logging.getLogger("saarthi.llm")
_clients: dict = {}


class LLMRefusal(Exception):
    pass


# ------------------------------------------------------------------ Gemini
def _gemini():
    if "gemini" not in _clients or _clients.get("gemini_key") != config.GEMINI_API_KEY:
        from google import genai
        print(f"[GEMINI] Initialising client - key={config.GEMINI_API_KEY[:8] if config.GEMINI_API_KEY else 'NOT SET'}...")
        _clients["gemini"] = genai.Client(api_key=config.GEMINI_API_KEY)
        _clients["gemini_key"] = config.GEMINI_API_KEY
    return _clients["gemini"]


def _to_gemini_schema(s: dict) -> dict:
    """JSON Schema subset -> Gemini Schema (uppercase type names)."""
    out = {"type": s["type"].upper()}
    if "description" in s:
        out["description"] = s["description"]
    if s["type"] == "object":
        out["properties"] = {k: _to_gemini_schema(v) for k, v in s.get("properties", {}).items()}
        if s.get("required"):
            out["required"] = s["required"]
    if s["type"] == "array":
        out["items"] = _to_gemini_schema(s["items"])
    return out


class _GeminiLoop:
    def __init__(self, system: str, tools: list[dict]):
        from google.genai import types
        self.types = types
        self.contents = []
        self.config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t["name"], description=t["description"],
                                          parameters=types.Schema(**_to_gemini_schema(t["input_schema"])))
                for t in tools])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2, max_output_tokens=8192)

    def send(self, user_text: str | None = None, results: list[dict] | None = None):
        t = self.types
        if user_text is not None:
            self.contents.append(t.Content(role="user", parts=[t.Part(text=user_text)]))
        if results:
            self.contents.append(t.Content(role="user", parts=[
                t.Part.from_function_response(name=r["name"], response={"result": r["output"]}) for r in results]))
        resp = _gemini().models.generate_content(model=config.GEMINI_MODEL, contents=self.contents, config=self.config)
        print(f"[GEMINI] tool_loop.send() -> model={config.GEMINI_MODEL} candidates={len(resp.candidates or [])}")
        if not resp.candidates:
            raise LLMRefusal("Gemini returned no candidates (blocked prompt)")
        cand = resp.candidates[0]
        if str(cand.finish_reason).upper().endswith(("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII")):
            raise LLMRefusal(f"Gemini stopped: {cand.finish_reason}")
        if cand.content:
            self.contents.append(cand.content)  # keeps thought signatures for the next turn
        parts = (cand.content.parts if cand.content else None) or []
        texts = [p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)]
        calls = [{"id": f"call-{i}", "name": p.function_call.name, "args": dict(p.function_call.args or {})}
                 for i, p in enumerate(parts) if getattr(p, "function_call", None)]
        return texts, calls


def _gemini_complete(system: str, user: str, max_tokens: int) -> str | None:
    from google.genai import types
    for attempt in range(3):
        try:
            print(f"[GEMINI] complete() attempt={attempt + 1} model={config.GEMINI_MODEL} max_tokens={max_tokens}")
            resp = _gemini().models.generate_content(
                model=config.GEMINI_MODEL, contents=user,
                config=types.GenerateContentConfig(system_instruction=system, temperature=0.3, max_output_tokens=max_tokens))
            print(f"[GEMINI] complete() -> {len(resp.text or '')} chars")
            return (resp.text or "").strip() or None
        except Exception as e:
            err = str(e).lower()
            if attempt < 2 and any(x in err for x in ("429", "503", "overload", "quota", "resource exhausted")):
                wait = (attempt + 1) * 4
                log.warning("Gemini overloaded (attempt %d/3), retrying in %ds: %s", attempt + 1, wait, e)
                time.sleep(wait)
            else:
                raise
    return None


# ------------------------------------------------------------------ public
def tool_loop(system: str, tools: list[dict]):
    return _GeminiLoop(system, tools)


def provider_label() -> str:
    return f"Gemini · {config.GEMINI_MODEL}"


def complete(system: str, user: str, max_tokens: int = 2048) -> str | None:
    if not config.llm_enabled():
        return None
    try:
        return _gemini_complete(system, user, max_tokens)
    except Exception as e:  # never let the LLM break a financial flow
        log.warning("Gemini call failed (%s) - falling back to deterministic output", e)
        return None


def complete_json(system: str, user: str) -> dict | None:
    text = complete(system, user)
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None
