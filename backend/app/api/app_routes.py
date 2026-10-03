"""The fintech app's own API: registration, bank accounts, funds and SIPs."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import current_user
from app.product import accounts, sips, users

router = APIRouter(prefix="/api", tags=["app"])


class RegisterBody(BaseModel):
    name: str
    phone: str
    email: str
    dob: str
    pan: str


class LinkBody(BaseModel):
    bank: str
    account_no: str
    holder_name: str
    opening_balance: float
    owner: str = "self"


class BalanceBody(BaseModel):
    delta: float


class SipBody(BaseModel):
    fund_id: str
    amount: float
    sip_day: int
    account_id: str
    mandate_limit: float


class SipUpdateBody(BaseModel):
    amount: float


# ---------------------------------------------------------------- users
@router.post("/users/register")
def register(body: RegisterBody):
    return users.public(users.register(body.name, body.phone, body.email, body.dob, body.pan))


@router.get("/users")
def profiles():
    return users.list_profiles()


@router.get("/me")
def me(user=Depends(current_user)):
    return users.public(user)


# ---------------------------------------------------------------- accounts
def _acc(a: dict) -> dict:
    return {k: v for k, v in a.items() if k != "account_no"}


@router.get("/accounts")
def list_accounts(user=Depends(current_user)):
    return [_acc(a) for a in accounts.for_user(user["id"])]


@router.post("/accounts")
def link_account(body: LinkBody, user=Depends(current_user)):
    return _acc(accounts.link(user, body.bank, body.account_no, body.holder_name, body.opening_balance, body.owner))


@router.post("/accounts/{acc_id}/balance")
def adjust_balance(acc_id: str, body: BalanceBody, user=Depends(current_user)):
    return _acc(accounts.adjust_balance(user, acc_id, body.delta))


# ---------------------------------------------------------------- funds & SIPs
@router.get("/funds")
def list_funds():
    return sips.funds()


@router.get("/funds/{fid}")
def get_fund(fid: str):
    return sips.fund(fid)


@router.get("/sips")
def list_sips(user=Depends(current_user)):
    return sips.for_user(user["id"])


@router.post("/sips")
def start_sip(body: SipBody, user=Depends(current_user)):
    return sips.start(user, body.fund_id, body.amount, body.sip_day, body.account_id, body.mandate_limit)


@router.post("/sips/{sid}/run")
def run_installment(sid: str, user=Depends(current_user)):
    return sips.run_installment(user, sid)


@router.patch("/sips/{sid}")
def update_sip(sid: str, body: SipUpdateBody, user=Depends(current_user)):
    return sips.update_amount(user, sid, body.amount)
