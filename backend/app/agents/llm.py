"""Claude client wrapper. Optional by design: in DEMO_MODE (or without a key, or
on any API error) every caller falls back to deterministic logic, so the demo
never depends on the network."""
import json
import logging
import re

from app import config

log = logging.getLogger("saarthi.llm")
_client = None
_agent_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=30.0, max_retries=1)
    return _client


def agent_client():
    """Separate client for the agent loop: longer timeout, since one turn can think for a while."""
    global _agent_client
    if _agent_client is None:
        import anthropic
        _agent_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=120.0, max_retries=1)
    return _agent_client


def complete(system: str, user: str, max_tokens: int = 4096) -> str | None:
    if not config.llm_enabled():
        return None
    import anthropic
    try:
        resp = _get_client().beta.messages.create(
            model=config.SAARTHI_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            return None
        return "".join(b.text for b in resp.content if b.type == "text").strip() or None
    except anthropic.APIStatusError as e:
        log.warning("Claude API status error %s - falling back to deterministic output", e.status_code)
    except anthropic.APIConnectionError:
        log.warning("Claude API unreachable - falling back to deterministic output")
    except Exception:  # never let the LLM break a financial flow
        log.exception("LLM call failed")
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
