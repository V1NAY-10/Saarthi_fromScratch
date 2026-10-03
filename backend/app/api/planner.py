"""Financial Planner API endpoints."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import current_user
from app.planner import agent, engine, scenarios, service

router = APIRouter(prefix="/api/planner", tags=["planner"])


# Request models
class GoalCreateBody(BaseModel):
    name: str
    category: str = "custom"
    target_amount: float
    current_amount: float = 0.0
    target_date: str
    monthly_contribution: float = 0.0
    priority: int = 1
    notes: Optional[str] = ""


class GoalUpdateBody(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    target_amount: Optional[float] = None
    current_amount: Optional[float] = None
    target_date: Optional[str] = None
    monthly_contribution: Optional[float] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class GoalLinkBody(BaseModel):
    investment_id: str
    investment_type: str = "sip"
    allocated_amount: float


class AffordabilityBody(BaseModel):
    amount: float
    is_recurring: bool = False
    frequency: str = "one_time"  # "one_time" | "monthly" | "yearly"
    category: str = "shopping"


class WhatIfBody(BaseModel):
    income_delta_pct: float = 0.0
    sip_delta_abs: float = 0.0
    expense_delta_abs: float = 0.0
    one_time_expense: float = 0.0


class StressTestBody(BaseModel):
    stress_type: str  # "INCOME_DROP_10" | "INCOME_DROP_20" | "INCOME_ZERO" | "UNEXPECTED_EXPENSE_50K" | "UNEXPECTED_EXPENSE_1L" | "EMI_HIKE_15"


class DebtExtraPaymentBody(BaseModel):
    liability_id: Optional[str] = None
    outstanding_balance: Optional[float] = None
    current_emi: Optional[float] = None
    annual_interest_rate_pct: Optional[float] = None
    extra_monthly_payment: float = 5000.0


class ProfileUpdateBody(BaseModel):
    monthly_income: Optional[float] = None
    essential_expenses: Optional[float] = None
    discretionary_expenses: Optional[float] = None
    target_runway_months: Optional[float] = None


class ChatBody(BaseModel):
    message: str


# ---------------------------------------------------------------- endpoints
@router.get("/overview")
def get_overview(user=Depends(current_user)):
    return service.build_command_center(user["id"])


@router.post("/profile")
def update_profile(body: ProfileUpdateBody, user=Depends(current_user)):
    return service.update_profile(user["id"], body.model_dump(exclude_unset=True))


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


@router.post("/goals/{goal_id}/link")
def link_investment(goal_id: str, body: GoalLinkBody, user=Depends(current_user)):
    return service.link_investment_to_goal(goal_id, body.investment_id, body.investment_type, body.allocated_amount)


@router.get("/upcoming")
def get_upcoming(user=Depends(current_user)):
    return service.get_upcoming_obligations(user["id"])


@router.get("/calendar")
def get_calendar(user=Depends(current_user)):
    return service.get_financial_calendar(user["id"])


@router.get("/changelog")
def get_changelog(limit: int = 20, user=Depends(current_user)):
    return service.get_plan_change_log(user["id"], limit=limit)


@router.post("/affordability")
def check_affordability(body: AffordabilityBody, user=Depends(current_user)):
    cc = service.build_command_center(user["id"])
    liquid = cc["net_worth"]["asset_breakdown"]["liquid_cash"]
    income = cc["profile"]["monthly_income"]
    surplus = cc["cash_flow"]["estimated_surplus"]
    essential = cc["profile"]["essential_expenses"] + cc["cash_flow"]["emis"]
    goals = cc["goals"]

    upcoming_7d = sum(
        o["amount"] for o in cc["obligations"]
        if o["due"] <= (engine.date.today() + engine.timedelta(days=7)).isoformat()
    )

    return engine.simulate_affordability(
        purchase_amount=body.amount,
        is_recurring=body.is_recurring,
        frequency=body.frequency,
        current_liquid=liquid,
        monthly_income=income,
        monthly_surplus=surplus,
        essential_monthly_expenses=essential,
        active_goals=goals,
        upcoming_7d_obligations=upcoming_7d,
    )


@router.post("/what-if")
def simulate_what_if(body: WhatIfBody, user=Depends(current_user)):
    cc = service.build_command_center(user["id"])
    return engine.simulate_what_if(
        base_income=cc["profile"]["monthly_income"],
        base_fixed_expenses=cc["profile"]["essential_expenses"],
        base_emis=cc["cash_flow"]["emis"],
        base_sips=cc["cash_flow"]["sips"],
        base_liquid=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
        active_goals=cc["goals"],
        income_delta_pct=body.income_delta_pct,
        sip_delta_abs=body.sip_delta_abs,
        expense_delta_abs=body.expense_delta_abs,
        one_time_expense=body.one_time_expense,
    )


@router.post("/stress-test")
def simulate_stress_test(body: StressTestBody, user=Depends(current_user)):
    cc = service.build_command_center(user["id"])
    return engine.run_stress_test(
        stress_type=body.stress_type,
        monthly_income=cc["profile"]["monthly_income"],
        fixed_expenses=cc["profile"]["essential_expenses"],
        emis=cc["cash_flow"]["emis"],
        sips=cc["cash_flow"]["sips"],
        liquid_funds=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
        active_goals=cc["goals"],
    )


@router.post("/debt/extra-payment")
def simulate_debt_payment(body: DebtExtraPaymentBody, user=Depends(current_user)):
    balance = body.outstanding_balance
    emi = body.current_emi
    rate = body.annual_interest_rate_pct

    if body.liability_id:
        lib = service.db.query_one("SELECT * FROM financial_liabilities WHERE id=? AND user_id=?", (body.liability_id, user["id"]))
        if lib:
            balance = balance or lib["outstanding_amount"]
            emi = emi or lib["emi_amount"]
            rate = rate or lib["interest_rate"]

    balance = balance or 350000.0
    emi = emi or 12000.0
    rate = rate or 12.0

    return engine.simulate_debt_extra_payment(
        outstanding_balance=balance,
        current_emi=emi,
        annual_interest_rate_pct=rate,
        extra_monthly_payment=body.extra_monthly_payment,
    )


@router.post("/chat")
def planner_chat(body: ChatBody, user=Depends(current_user)):
    return agent.ask_planner(user["id"], body.message)


@router.post("/demo/scenario/{scenario_id}")
def run_demo_scenario(scenario_id: int, user=Depends(current_user)):
    return scenarios.load_scenario(user["id"], scenario_id)
