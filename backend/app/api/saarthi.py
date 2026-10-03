from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import config
from app.agents import chat, orchestrator
from app.api.deps import current_user
from app.database import db, seed
from app.knowledge import retrieval
from app.product import accounts, sips, users
from app.services import journal
from app.services.fmt import inr

router = APIRouter(prefix="/api", tags=["saarthi"])


class ChatBody(BaseModel):
    message: str
    journey_id: str | None = None


@router.get("/system")
def system():
    return {"demo_mode": config.DEMO_MODE, "llm_enabled": config.llm_enabled(), "model": config.SAARTHI_MODEL,
            "agent_mode": "claude" if config.llm_enabled() else "deterministic"}


def _insights(accs: list[dict], my_sips: list[dict]) -> list[dict]:
    """Proactive checks over live state - Saarthi warns before a partner rejects anything."""
    out = []
    for s in my_sips:
        if s["status"] != "ACTIVE" or s["journey_status"] in ("ATTENTION", "ESCALATED"):
            continue
        acc, m = s["account"], s["mandate"]
        if s["amount"] > m["max_amount"]:
            out.append({"tone": "warn", "journey_id": s["journey_id"],
                        "text": f"{s['fund']['name']}: your {inr(s['amount'])} SIP is above the {inr(m['max_amount'])} "
                                "autopay limit, so the bank will refuse the next debit."})
        elif acc["balance"] < s["amount"]:
            out.append({"tone": "warn", "journey_id": s["journey_id"],
                        "text": f"{s['fund']['name']}: {acc['bank']} {acc['masked']} has {inr(acc['balance'])}, short "
                                f"of the next {inr(s['amount'])} installment on {date.fromisoformat(s['next_due']):%d %b}."})
        else:
            out.append({"tone": "ok", "journey_id": s["journey_id"],
                        "text": f"{s['fund']['name']}: next {inr(s['amount'])} installment is covered."})
    for a in accs:
        if a["status"] == "UNVERIFIED":
            out.append({"tone": "warn", "journey_id": a["journey_id"],
                        "text": f"{a['bank']} {a['masked']} isn't verified, so it can't be used for autopay yet."})
    if not accs:
        out.append({"tone": "info", "text": "Link a bank account to start investing."})
    elif not my_sips:
        out.append({"tone": "info", "text": "Pick a fund in Invest to start your first SIP."})
    return out


@router.get("/overview")
def overview(user=Depends(current_user)):
    accs = accounts.for_user(user["id"])
    my_sips = sips.for_user(user["id"])
    journeys = [orchestrator.summary(j) for j in db.query("SELECT * FROM journeys WHERE user_id=?", (user["id"],))]
    attention = sorted([j for j in journeys if j["status"] == "ATTENTION"],
                       key=lambda j: (j.get("saarthi", {}).get("tier") == "TIER_3", j["health_score"]))
    overall = round(sum(j["health_score"] for j in journeys) / len(journeys)) if journeys else 100
    cash = sum(a["balance"] for a in accs)
    invested = sum(s["invested"] for s in my_sips)
    value = sum(s["current_value"] for s in my_sips)
    obligations = [{"title": s["fund"]["name"], "amount": s["amount"], "due": s["next_due"], "sip_id": s["id"],
                    "status": "failed" if s["journey_status"] == "ATTENTION" else "upcoming",
                    "journey_id": s["journey_id"]} for s in my_sips if s["status"] == "ACTIVE"]
    return {
        "user": users.public(user), "accounts": [{k: v for k, v in a.items() if k != "account_no"} for a in accs],
        "cash": cash, "invested": invested, "portfolio_value": value, "net_worth": cash + value,
        "sips": my_sips, "obligations": sorted(obligations, key=lambda o: o["due"]),
        "journeys": journeys, "attention": attention, "overall_health": overall,
        "insights": _insights(accs, my_sips), "intelligence": journal.audit_log(None, 25, user_id=user["id"]),
        "system": system(),
    }


@router.get("/audit")
def audit(limit: int = 100, user=Depends(current_user)):
    return journal.audit_log(None, limit, user_id=user["id"])


@router.post("/chat")
def chat_endpoint(body: ChatBody, user=Depends(current_user)):
    return chat.respond(user["id"], body.message, body.journey_id)


@router.post("/demo/reset")
def reset():
    """Wipe every user, account, SIP and journey. Reference data (funds, knowledge) is reloaded."""
    seed.seed()
    retrieval.reset_index()
    return {"ok": True}
