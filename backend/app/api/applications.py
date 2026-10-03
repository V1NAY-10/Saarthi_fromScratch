"""Loan, insurance and KYC applications."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import current_user
from app.product import applications

router = APIRouter(prefix="/api/applications", tags=["applications"])


class StartBody(BaseModel):
    partner_id: str
    amount: float | None = None
    tenure_months: int | None = None
    monthly_income: float | None = None
    account_id: str | None = None


class SubmitBody(BaseModel):
    selections: dict[str, str]


@router.get("/catalog/{kind}")
def catalog(kind: str):
    return applications.catalog(kind)


@router.get("")
def list_applications(kind: str, user=Depends(current_user)):
    return applications.for_user(user["id"], kind)


@router.post("")
def start(body: StartBody, user=Depends(current_user)):
    return applications.start(user, body.partner_id, body.model_dump(exclude={"partner_id"}))


@router.get("/{jid}/precheck")
def precheck(jid: str, user=Depends(current_user)):
    return applications.precheck(user, jid)


@router.post("/{jid}/submit")
def submit(jid: str, body: SubmitBody, user=Depends(current_user)):
    return applications.submit(user, jid, body.selections)
