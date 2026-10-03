"""Conversational layer - an interface over Saarthi's structured intelligence,
not the product itself. Intent routing is deterministic; replies are built from
the stored diagnosis/decision/health of the user's own journeys. When the LLM
is enabled it may phrase the answer, but its output must pass the same numeric
grounding guard, and it can never trigger an action - actions come back as
approval cards."""
import json
import re

from app.agents import context as context_engine
from app.agents import explanation, llm, orchestrator, prompts
from app.database import db
from app.services.fmt import inr

INTENTS = [
    ("fix", r"\b(fix|resolve|retry|do it|go ahead|recover|sort it|handle)"),
    ("safe", r"\b(safe|lose|lost|refund|risk)"),
    ("health", r"\b(health|score|why is my)"),
    ("history", r"\b(history|before|previous|timeline|what happened so far|memory)"),
    ("escalate", r"\b(human|agent|support|escalat|call me)"),
    ("why", r"\b(why|what happened|reason|fail|stuck|explain|mean|wrong)"),
    ("overview", r"\b(attention|pending|what needs|overview|all journeys|anything|status)"),
]

CATEGORY_HINTS = [
    ("investment", r"\b(sip|invest|installment|instalment|payment|debit|autopay|mandate|fund|units)"),
    ("bank_account", r"\b(bank|account|verif|name|penny|link)"),
]


def _match(patterns, text, default=None):
    for key, pat in patterns:
        if re.search(pat, text):
            return key
    return default


def _pick_journey(uid: str, text: str, journey_id: str | None) -> dict | None:
    js = db.query("SELECT * FROM journeys WHERE user_id=?", (uid,))
    for j in js:  # a journey named in the message wins (e.g. a fund name)
        words = [w for w in re.findall(r"[a-z]+", j["title"].lower()) if len(w) > 3 and w not in ("fund", "bank")]
        if any(w in text for w in words):
            return j
    cat = _match(CATEGORY_HINTS, text)
    if cat:
        cands = sorted([j for j in js if j["category"] == cat], key=lambda j: j["updated_at"], reverse=True)
        cands.sort(key=lambda j: j["status"] != "ATTENTION")
        if cands:
            return cands[0]
    return next((j for j in js if j["id"] == journey_id), None)


def _card_journey(j):
    return {"type": "journey", "journey_id": j["id"], "title": j["title"], "status": j["status"]}


def respond(uid: str, message: str, journey_id: str | None = None) -> dict:
    text = message.lower().strip()
    j0 = _pick_journey(uid, text, journey_id)
    intent = _match(INTENTS, text, "why" if j0 else "overview")
    if intent == "overview" or not j0:
        return _overview(uid)

    jid = j0["id"]
    v = orchestrator.view(jid)
    j, diag, h, run = v["journey"], v["diagnosis"], v["health"], v["agent_run"]
    cards, replies = [], []
    issue = bool(diag and diag.get("status") == "DIAGNOSED" and j["status"] == "ATTENTION")
    primary = diag["decisions"]["primary"] if issue else None

    if j["status"] == "ATTENTION" and not issue:
        replies.append(f"Something went wrong with your {j['title']} and I'm investigating it right now. "
                       "Open the journey to watch each step.")
    elif intent == "fix":
        if not issue:
            replies.append(f"Your {j['title']} doesn't need fixing. It's {j['stage'].lower()}.")
        else:
            res = orchestrator.recover(jid)
            option = next(o for o in diag["options"] if o["id"] == res["decision"]["option_id"])
            if res["outcome"] == "APPROVAL_REQUIRED":
                replies.append("I can do this, but it needs your approval first.")
                replies.append(option["description"])
                cards.append({"type": "approval", "journey_id": jid, "action_id": res["action"]["id"],
                              "title": option["title"], "tier": res["decision"]["tier"],
                              "checks": [c["label"] for c in res["decision"]["checks"] if c["passed"]][:6]})
            elif res["outcome"] == "EXECUTED":
                replies.append(f"Done. That was a safe, reversible step: {option['title'].lower()}.")
            else:
                replies.append("I don't have enough confidence to fix this automatically. I can hand it to a "
                               "specialist with everything I've checked.")
                cards.append({"type": "escalate", "journey_id": jid, "reasons": res["decision"]["reasons"][:4]})
    elif intent == "safe":
        replies.append(diag["explanation"]["safety_note"] if issue else
                       f"Yes. Your {j['title']} is {h['band']['label'].lower()} with a health score of {h['score']}.")
    elif intent == "health":
        top = sorted(h["factors"], key=lambda f: f["impact"])
        neg = [f for f in top if f["impact"] < 0][:3]
        pos = [f for f in reversed(top) if f["impact"] > 0][:2]
        replies.append(f"Journey Health is {h['score']}/100 ({h['band']['label']}).")
        if neg:
            replies.append("Pulling it down: " + ", ".join(f"{f['label'].lower()} ({f['impact']})" for f in neg) + ".")
        if pos:
            replies.append("Holding it up: " + ", ".join(f"{f['label'].lower()} (+{f['impact']})" for f in pos) + ".")
        cards.append({"type": "health", "journey_id": jid, "score": h["score"]})
    elif intent == "history":
        replies.append("Here's what I remember about this journey:")
        replies.append(" → ".join(e["title"] for e in v["timeline"][-6:]))
    elif intent == "escalate":
        replies.append("I can open a support case with the full context (evidence, partner responses and every "
                       "check I ran) so the specialist doesn't start from zero.")
        cards.append({"type": "escalate", "journey_id": jid, "reasons": primary["reasons"] if primary else []})
    else:  # why
        if issue:
            replies.append(diag["explanation"]["summary"])
            if primary and primary["tier"] != "TIER_3":
                replies.append("I've found a safe way to fix it.")
            cards.append({"type": "decision", "journey_id": jid, "tier": primary["tier"] if primary else None})
        elif j["status"] == "RESOLVED":
            replies.append(f"Your {j['title']} hit a problem, and I resolved it and verified the result with "
                           f"{j['partner_name']}. It's now {j['stage'].lower()}.")
        else:
            replies.append(f"Nothing is wrong with your {j['title']}. It's {j['stage'].lower()} and its Journey "
                           f"Health is {h['score']}.")
            if j["category"] == "investment" and v["sip"] and v["linked_account"]:
                acc, sip = v["linked_account"], v["sip"]
                if acc["balance"] < sip["amount"]:
                    replies.append(f"Heads up: {acc['bank']} {acc['masked']} has {inr(acc['balance'])}, which won't "
                                   f"cover the next {inr(sip['amount'])} installment.")

    if issue:
        replies = _maybe_llm(message, v, replies)
    cards.append(_card_journey(j))
    return {"journey_id": jid, "intent": intent, "messages": replies, "cards": cards}


def _maybe_llm(question: str, v: dict, replies: list[str]) -> list[str]:
    diag = v["diagnosis"]
    ctx = context_engine.build(v["journey"]["id"])
    grounded = explanation.llm_context(ctx, diag)
    grounded["health"] = {"score": v["health"]["score"], "factors": v["health"]["factors"]}
    grounded["decision_tier"] = (diag["decisions"]["primary"] or {}).get("tier")
    grounded["journey_memory"] = [e["title"] for e in v["timeline"]]
    grounded["draft_answer"] = replies
    out = llm.complete(prompts.EXPLANATION_SYSTEM,
                       f"Context:\n{json.dumps(grounded, ensure_ascii=False, default=str)}\n\n"
                       f"Customer question: {question}", max_tokens=2000)
    if not out:
        return replies
    return [out] if explanation.grounding_check(out, grounded)["passed"] else replies


def _overview(uid: str) -> dict:
    js = [orchestrator.summary(j) for j in db.query("SELECT * FROM journeys WHERE user_id=?", (uid,))]
    if not js:
        return {"intent": "overview", "cards": [],
                "messages": ["You don't have any journeys yet. Link a bank account and start a SIP, and I'll keep "
                             "an eye on every step."]}
    attention = [j for j in js if j["status"] == "ATTENTION"]
    if not attention:
        escalated = [j for j in js if j["status"] == "ESCALATED"]
        msgs = ["Nothing needs your action right now."]
        msgs += [f"{j['title']} is with a specialist (case {j['state'].get('case_id')})." for j in escalated]
        return {"intent": "overview", "messages": msgs, "cards": [_card_journey(j) for j in escalated]}
    lines = [f"{len(attention)} journey{'s need' if len(attention) > 1 else ' needs'} your attention:"]
    for j in sorted(attention, key=lambda x: x["health_score"]):
        what = j.get("saarthi", {}).get("meaning", "being investigated").lower()
        lines.append(f"• {j['title']}: {what} (health {j['health_score']})")
    return {"intent": "overview", "messages": lines, "cards": [_card_journey(j) for j in attention]}
