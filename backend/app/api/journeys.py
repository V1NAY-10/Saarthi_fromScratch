from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents import actions, context, decision, orchestrator
from app.api.deps import current_user, own_journey
from app.database import db
from app.services import journal

router = APIRouter(prefix="/api/journeys", tags=["journeys"])


class OptionBody(BaseModel):
    option_id: str | None = None


class ApproveBody(BaseModel):
    action_id: str


@router.get("")
def list_journeys(user=Depends(current_user)):
    rows = db.query("SELECT * FROM journeys WHERE user_id=? ORDER BY CASE status WHEN 'ATTENTION' THEN 0 "
                    "WHEN 'ESCALATED' THEN 1 WHEN 'RESOLVED' THEN 2 ELSE 3 END, updated_at DESC", (user["id"],))
    return [orchestrator.summary(j) for j in rows]


@router.get("/{jid}")
def get_journey(jid: str, user=Depends(current_user)):
    own_journey(jid, user)
    return orchestrator.view(jid)


@router.get("/{jid}/timeline")
def timeline(jid: str, user=Depends(current_user)):
    own_journey(jid, user)
    return journal.timeline(jid)


@router.get("/{jid}/agent")
def agent_run(jid: str, user=Depends(current_user)):
    own_journey(jid, user)
    return orchestrator.latest_run(jid)


@router.post("/{jid}/diagnose")
def diagnose(jid: str, user=Depends(current_user)):
    j = own_journey(jid, user)
    if j["status"] != "ATTENTION":
        raise HTTPException(409, "Nothing to diagnose - this journey has no open problem")
    orchestrator.reopen(jid, "Re-run requested by you")
    return orchestrator.view(jid)


@router.post("/{jid}/decide")
def decide(jid: str, body: OptionBody, user=Depends(current_user)):
    own_journey(jid, user)
    diag = orchestrator.stored(jid)
    if not diag or diag.get("status") != "DIAGNOSED":
        raise HTTPException(409, "Nothing to decide yet")
    oid = body.option_id or diag["decisions"]["primary_option_id"]
    option = next((o for o in diag["options"] if o["id"] == oid), None)
    if not option:
        raise HTTPException(404, "Unknown recovery option")
    return decision.decide(diag, option, context.build(jid))


@router.post("/{jid}/recover")
def recover(jid: str, body: OptionBody, user=Depends(current_user)):
    own_journey(jid, user)
    try:
        res = orchestrator.recover(jid, body.option_id)
    except actions.ActionBlocked as e:
        raise HTTPException(403, str(e))
    return {**res, "view": orchestrator.view(jid)}


@router.post("/{jid}/approve")
def approve(jid: str, body: ApproveBody, user=Depends(current_user)):
    own_journey(jid, user)
    try:
        return orchestrator.approve(jid, body.action_id)
    except actions.ActionBlocked as e:
        raise HTTPException(403, str(e))


@router.post("/{jid}/escalate")
def escalate(jid: str, user=Depends(current_user)):
    own_journey(jid, user)
    try:
        return orchestrator.escalate(jid)
    except actions.ActionBlocked as e:
        raise HTTPException(409, str(e))
