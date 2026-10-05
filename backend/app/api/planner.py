"""Financial Planner API endpoints."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.deps import current_user
from app.planner import agent, scenarios, service

router = APIRouter(prefix="/api/planner", tags=["planner"])


def _iso_date(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    try:
        return date.fromisoformat(v[:10]).isoformat()
    except ValueError:
        raise ValueError("target_date must be a date in YYYY-MM-DD format")


# Request models
class GoalCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = "custom"
    target_amount: float = Field(gt=0)
    current_amount: float = Field(default=0.0, ge=0)
    target_date: str
    monthly_contribution: float = Field(default=0.0, ge=0)
    priority: int = 1
    notes: Optional[str] = ""

    _date = field_validator("target_date")(_iso_date)


class GoalUpdateBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    category: Optional[str] = None
    target_amount: Optional[float] = Field(default=None, gt=0)
    current_amount: Optional[float] = Field(default=None, ge=0)
    target_date: Optional[str] = None
    monthly_contribution: Optional[float] = Field(default=None, ge=0)
    priority: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None

    _date = field_validator("target_date")(_iso_date)


class GoalLinkBody(BaseModel):
    investment_id: str
    investment_type: str = "sip"
    allocated_amount: float = Field(ge=0)


class AffordabilityBody(BaseModel):
    amount: float = Field(gt=0)
    is_recurring: bool = False
    frequency: Literal["one_time", "monthly", "yearly"] = "one_time"
    category: str = "shopping"


class WhatIfBody(BaseModel):
    income_delta_pct: float = Field(default=0.0, ge=-100)
    sip_delta_abs: float = 0.0
    expense_delta_abs: float = 0.0
    one_time_expense: float = Field(default=0.0, ge=0)


class StressTestBody(BaseModel):
    stress_type: Literal[service.STRESS_TYPES]  # type: ignore[valid-type]


class DebtExtraPaymentBody(BaseModel):
    liability_id: Optional[str] = None
    outstanding_balance: Optional[float] = Field(default=None, ge=0)
    current_emi: Optional[float] = Field(default=None, gt=0)
    annual_interest_rate_pct: Optional[float] = Field(default=None, ge=0, le=60)
    extra_monthly_payment: float = Field(default=5000.0, ge=0)


class ProfileUpdateBody(BaseModel):
    monthly_income: Optional[float] = Field(default=None, ge=0)
    essential_expenses: Optional[float] = Field(default=None, ge=0)
    discretionary_expenses: Optional[float] = Field(default=None, ge=0)
    target_runway_months: Optional[float] = Field(default=None, ge=1, le=36)
    salary_day: Optional[int] = Field(default=None, ge=1, le=28)


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------- endpoints
@router.get("/overview")
def get_overview(user=Depends(current_user)):
    return service.build_command_center(user["id"])


@router.post("/profile")
def update_profile(body: ProfileUpdateBody, user=Depends(current_user)):
    service.update_profile(user["id"], body.model_dump(exclude_unset=True))
    return service.build_command_center(user["id"])


@router.get("/goals")
def list_goals(user=Depends(current_user)):
    return service.list_goals(user["id"])


@router.post("/goals")
def create_goal(body: GoalCreateBody, user=Depends(current_user)):
    return service.create_goal(user["id"], body.model_dump())


@router.put("/goals/{goal_id}")
def update_goal(goal_id: str, body: GoalUpdateBody, user=Depends(current_user)):
    res = service.update_goal(user["id"], goal_id, body.model_dump(exclude_unset=True))
    if not res:
        raise HTTPException(404, "Goal not found")
    return res


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: str, user=Depends(current_user)):
    ok = service.delete_goal(user["id"], goal_id)
    if not ok:
        raise HTTPException(404, "Goal not found")
    return {"ok": True}


class GoalTopUpBody(BaseModel):
    amount: float = Field(gt=0, le=1e9)


@router.post("/goals/{goal_id}/add-money")
def add_money(goal_id: str, body: GoalTopUpBody, user=Depends(current_user)):
    res = service.add_money_to_goal(user["id"], goal_id, body.amount)
    if not res:
        raise HTTPException(404, "Goal not found")
    return res


@router.post("/goals/{goal_id}/link")
def link_investment(goal_id: str, body: GoalLinkBody, user=Depends(current_user)):
    res = service.link_investment_to_goal(user["id"], goal_id, body.investment_id, body.investment_type,
                                          body.allocated_amount)
    if not res:
        raise HTTPException(404, "Goal not found")
    return res


@router.get("/upcoming")
def get_upcoming(user=Depends(current_user)):
    return service.get_upcoming_obligations(user["id"])


@router.get("/calendar")
def get_calendar(user=Depends(current_user)):
    return service.get_financial_calendar(user["id"])


@router.get("/changelog")
def get_changelog(limit: int = 20, user=Depends(current_user)):
    return service.get_plan_change_log(user["id"], limit=max(1, min(limit, 100)))


@router.post("/affordability")
def check_affordability(body: AffordabilityBody, user=Depends(current_user)):
    return service.affordability(user["id"], body.amount, body.is_recurring, body.frequency)


@router.post("/what-if")
def simulate_what_if(body: WhatIfBody, user=Depends(current_user)):
    return service.what_if(user["id"], body.income_delta_pct, body.sip_delta_abs, body.expense_delta_abs,
                           body.one_time_expense)


@router.post("/stress-test")
def simulate_stress_test(body: StressTestBody, user=Depends(current_user)):
    return service.stress_test(user["id"], body.stress_type)


@router.post("/debt/extra-payment")
def simulate_debt_payment(body: DebtExtraPaymentBody, user=Depends(current_user)):
    return service.debt_payoff(user["id"], body.extra_monthly_payment, body.liability_id, body.outstanding_balance,
                               body.current_emi, body.annual_interest_rate_pct)


@router.post("/chat")
def planner_chat(body: ChatBody, user=Depends(current_user)):
    return agent.ask_planner(user["id"], body.message)


@router.post("/demo/scenario/{scenario_id}")
def run_demo_scenario(scenario_id: int, user=Depends(current_user)):
    if scenario_id not in scenarios.SCENARIO_IDS:
        raise HTTPException(404, "Unknown scenario")
    return scenarios.load_scenario(user["id"], scenario_id)
