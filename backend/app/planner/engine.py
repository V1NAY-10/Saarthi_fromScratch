"""Deterministic financial calculations engine.

Single source of truth for:
- Net worth & asset/liability breakdown
- Cash flow, commitments, surplus
- Runway & emergency fund coverage
- Goal progress, required contributions, timeline projections
- Cash-flow collision detection (7, 30, 90 days)
- Affordability simulation
- What-if scenario analysis
- Financial stress tests
- Debt amortization and extra-payment impact

NO LLM calls here. Pure mathematical and deterministic logic.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def calculate_net_worth(
    bank_balances: float,
    investments_value: float,
    other_assets: float = 0.0,
    loans_outstanding: float = 0.0,
    credit_card_outstanding: float = 0.0,
    other_liabilities: float = 0.0,
) -> Dict[str, Any]:
    total_assets = max(0.0, bank_balances + investments_value + other_assets)
    total_liabilities = max(0.0, loans_outstanding + credit_card_outstanding + other_liabilities)
    net_worth = total_assets - total_liabilities

    asset_breakdown = {
        "liquid_cash": bank_balances,
        "investments": investments_value,
        "other_assets": other_assets,
        "total_assets": total_assets,
        "liquid_pct": round((bank_balances / total_assets * 100), 1) if total_assets > 0 else 0.0,
        "investments_pct": round((investments_value / total_assets * 100), 1) if total_assets > 0 else 0.0,
    }

    liability_breakdown = {
        "loans": loans_outstanding,
        "credit_cards": credit_card_outstanding,
        "other_liabilities": other_liabilities,
        "total_liabilities": total_liabilities,
        "debt_to_asset_pct": round((total_liabilities / total_assets * 100), 1) if total_assets > 0 else 0.0,
    }

    return {
        "net_worth": net_worth,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "asset_breakdown": asset_breakdown,
        "liability_breakdown": liability_breakdown,
    }


def calculate_cash_flow(
    monthly_income: float,
    fixed_expenses: float,
    emis: float,
    sips: float,
    insurance_monthly: float,
    discretionary_expenses: float = 0.0,
    planned_goal_contributions: float = 0.0,
) -> Dict[str, Any]:
    committed_outflow = fixed_expenses + emis + sips + insurance_monthly
    total_outflow = committed_outflow + discretionary_expenses + planned_goal_contributions
    estimated_surplus = monthly_income - total_outflow

    savings_pool = sips + planned_goal_contributions + max(0.0, estimated_surplus)
    savings_rate = round((savings_pool / monthly_income * 100), 1) if monthly_income > 0 else 0.0
    investment_rate = round((sips / monthly_income * 100), 1) if monthly_income > 0 else 0.0
    debt_to_income = round((emis / monthly_income * 100), 1) if monthly_income > 0 else 0.0

    return {
        "monthly_income": monthly_income,
        "fixed_expenses": fixed_expenses,
        "emis": emis,
        "sips": sips,
        "insurance_monthly": insurance_monthly,
        "discretionary_expenses": discretionary_expenses,
        "planned_goal_contributions": planned_goal_contributions,
        "committed_outflow": committed_outflow,
        "total_outflow": total_outflow,
        "estimated_surplus": estimated_surplus,
        "savings_rate_pct": savings_rate,
        "investment_rate_pct": investment_rate,
        "debt_to_income_pct": debt_to_income,
    }


def calculate_runway(
    liquid_funds: float,
    essential_monthly_expenses: float,
    target_months: float = 6.0,
) -> Dict[str, Any]:
    if essential_monthly_expenses <= 0:
        current_runway = 99.0 if liquid_funds > 0 else 0.0
    else:
        current_runway = round(liquid_funds / essential_monthly_expenses, 1)

    target_emergency_fund = round(essential_monthly_expenses * target_months, 0)
    gap = max(0.0, target_emergency_fund - liquid_funds)
    coverage_pct = min(100.0, round((liquid_funds / target_emergency_fund * 100), 1)) if target_emergency_fund > 0 else 100.0

    status = "ADEQUATE" if current_runway >= target_months else ("VULNERABLE" if current_runway < 3.0 else "BUILDING")

    return {
        "liquid_funds": liquid_funds,
        "essential_monthly_expenses": essential_monthly_expenses,
        "current_runway_months": current_runway,
        "target_months": target_months,
        "target_emergency_fund": target_emergency_fund,
        "funding_gap": gap,
        "coverage_pct": coverage_pct,
        "status": status,
    }


def calculate_goal_projection(
    target_amount: float,
    current_amount: float,
    target_date_iso: str,
    monthly_contribution: float,
    annual_growth_pct: float = 0.0,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    today = as_of or date.today()
    try:
        t_date = date.fromisoformat(target_date_iso[:10])
    except Exception:
        t_date = today + timedelta(days=365)

    remaining_amount = max(0.0, target_amount - current_amount)
    days_left = (t_date - today).days
    months_left = max(1.0, days_left / 30.4375)

    # Required monthly contribution without market risk (linear)
    required_monthly = round(remaining_amount / months_left, 0) if months_left > 0 else remaining_amount

    # If growth rate assumption is applied (e.g. 8% p.a. for equity SIP)
    r_monthly = (annual_growth_pct / 100.0) / 12.0
    if r_monthly > 0 and months_left > 1:
        compounded_current = current_amount * ((1 + r_monthly) ** months_left)
        needed_from_sip = max(0.0, target_amount - compounded_current)
        growth_factor = (((1 + r_monthly) ** months_left) - 1) / r_monthly
        required_monthly_with_growth = round(needed_from_sip / growth_factor, 0)
    else:
        required_monthly_with_growth = required_monthly

    contribution_gap = round(required_monthly - monthly_contribution, 0)

    # Projected completion date based on current monthly contribution
    if remaining_amount <= 0:
        projected_months = 0.0
        projected_completion = today.isoformat()
        status = "COMPLETED"
    elif monthly_contribution <= 0:
        projected_months = 999.0
        projected_completion = None
        status = "UNFUNDED"
    else:
        projected_months = remaining_amount / monthly_contribution
        comp_date = today + timedelta(days=int(projected_months * 30.4375))
        projected_completion = comp_date.isoformat()
        if contribution_gap <= 50:
            status = "ON_TRACK"
        else:
            status = "BEHIND"

    progress_pct = min(100.0, round((current_amount / target_amount * 100), 1)) if target_amount > 0 else 0.0

    return {
        "target_amount": target_amount,
        "current_amount": current_amount,
        "remaining_amount": remaining_amount,
        "target_date": t_date.isoformat(),
        "months_left": round(months_left, 1),
        "current_monthly_contribution": monthly_contribution,
        "required_monthly_contribution": required_monthly,
        "required_monthly_with_growth": required_monthly_with_growth,
        "contribution_gap": contribution_gap,
        "projected_completion_date": projected_completion,
        "projected_months": round(projected_months, 1) if projected_months < 900 else None,
        "progress_pct": progress_pct,
        "status": status,
    }


def detect_cash_flow_collisions(
    liquid_balance: float,
    upcoming_obligations: List[Dict[str, Any]],
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    today = as_of or date.today()
    windows = [7, 30, 90]
    results = {}
    any_collision = False

    for w in windows:
        cutoff = today + timedelta(days=w)
        in_window = []
        total_outflow = 0.0

        for ob in upcoming_obligations:
            try:
                d_str = ob.get("due") or ob.get("due_date") or ""
                ob_date = date.fromisoformat(d_str[:10])
            except Exception:
                continue

            if today <= ob_date <= cutoff:
                amt = float(ob.get("amount") or 0.0)
                in_window.append({
                    "title": ob.get("title") or ob.get("name") or "Obligation",
                    "amount": amt,
                    "due_date": ob_date.isoformat(),
                    "kind": ob.get("kind") or "debit",
                    "partner_id": ob.get("partner_id"),
                    "journey_id": ob.get("journey_id"),
                })
                total_outflow += amt

        shortfall = max(0.0, total_outflow - liquid_balance)
        has_collision = shortfall > 0

        if has_collision:
            any_collision = True

        results[f"{w}d"] = {
            "window_days": w,
            "obligations_count": len(in_window),
            "total_obligations": total_outflow,
            "available_liquidity": liquid_balance,
            "shortfall": shortfall,
            "has_collision": has_collision,
            "affected_obligations": in_window,
        }

    return {
        "has_collision": any_collision,
        "windows": results,
    }


def simulate_affordability(
    purchase_amount: float,
    is_recurring: bool,
    frequency: str,  # "one_time" | "monthly" | "yearly"
    current_liquid: float,
    monthly_income: float,
    monthly_surplus: float,
    essential_monthly_expenses: float,
    active_goals: List[Dict[str, Any]],
    upcoming_7d_obligations: float = 0.0,
) -> Dict[str, Any]:
    """Calculates multi-dimensional impact of a planned purchase."""
    one_time_impact = purchase_amount if not is_recurring else 0.0
    monthly_impact = purchase_amount if is_recurring and frequency == "monthly" else (
        (purchase_amount / 12.0) if is_recurring and frequency == "yearly" else 0.0
    )

    new_liquid = max(0.0, current_liquid - one_time_impact)
    new_surplus = monthly_surplus - monthly_impact

    # Runway effect
    runway_before = round(current_liquid / essential_monthly_expenses, 1) if essential_monthly_expenses > 0 else 99.0
    runway_after = round(new_liquid / essential_monthly_expenses, 1) if essential_monthly_expenses > 0 else 99.0

    # Collision test: will new liquid cover upcoming 7d commitments?
    immediate_shortfall = max(0.0, upcoming_7d_obligations - new_liquid)

    # Goal delay effect: how does this purchase delay active goals?
    goal_impacts = []
    for g in active_goals:
        cur_contrib = float(g.get("monthly_contribution") or 0.0)
        rem_amt = float(g.get("remaining_amount") or (float(g.get("target_amount", 0)) - float(g.get("current_amount", 0))))
        if cur_contrib <= 0 or rem_amt <= 0:
            continue

        if one_time_impact > 0:
            delay_months = round(one_time_impact / cur_contrib, 1)
        elif monthly_impact > 0 and new_surplus < 0:
            deficit = abs(new_surplus)
            cur_net_contrib = max(0.0, cur_contrib - deficit)
            if cur_net_contrib > 0:
                delay_months = round((rem_amt / cur_net_contrib) - (rem_amt / cur_contrib), 1)
            else:
                delay_months = 24.0
        else:
            delay_months = 0.0

        goal_impacts.append({
            "goal_id": g.get("id"),
            "goal_name": g.get("name"),
            "target_amount": g.get("target_amount"),
            "projected_delay_months": delay_months,
        })

    verdict = "AFFORDABLE"
    warnings = []
    uncovered = max(0.0, one_time_impact - current_liquid)
    if uncovered > 0:
        verdict = "HIGH_RISK"
        warnings.append(f"Exceeds your available bank balance by ₹{int(uncovered):,}.")
    elif immediate_shortfall > 0:
        verdict = "HIGH_RISK"
        warnings.append(f"Leaves you ₹{int(immediate_shortfall):,} short for obligations in the next 7 days.")
    elif runway_after < 3.0:
        verdict = "CAUTION"
        warnings.append(f"Reduces your financial runway to {runway_after} months (below recommended 3-6 months).")
    elif new_surplus < 0:
        verdict = "CAUTION"
        warnings.append(f"Creates a monthly deficit of ₹{abs(int(new_surplus)):,} under current income.")

    return {
        "purchase_amount": purchase_amount,
        "is_recurring": is_recurring,
        "liquid_before": current_liquid,
        "liquid_after": new_liquid,
        "surplus_before": monthly_surplus,
        "surplus_after": new_surplus,
        "runway_before_months": runway_before,
        "runway_after_months": runway_after,
        "immediate_shortfall_7d": immediate_shortfall,
        "verdict": verdict,
        "warnings": warnings,
        "goal_impacts": goal_impacts,
    }


def simulate_what_if(
    base_income: float,
    base_fixed_expenses: float,
    base_emis: float,
    base_sips: float,
    base_liquid: float,
    active_goals: List[Dict[str, Any]],
    income_delta_pct: float = 0.0,
    sip_delta_abs: float = 0.0,
    expense_delta_abs: float = 0.0,
    one_time_expense: float = 0.0,
    base_other_outflow: float = 0.0,
) -> Dict[str, Any]:
    """base_other_outflow: discretionary spend, insurance and goal contributions. It reduces
    surplus on both sides but is not part of the essential runway denominator."""
    new_income = max(0.0, base_income * (1.0 + income_delta_pct / 100.0))
    new_sips = max(0.0, base_sips + sip_delta_abs)
    new_expenses = max(0.0, base_fixed_expenses + expense_delta_abs)
    new_liquid = max(0.0, base_liquid - one_time_expense)

    base_surplus = base_income - (base_fixed_expenses + base_emis + base_sips + base_other_outflow)
    new_surplus = new_income - (new_expenses + base_emis + new_sips + base_other_outflow)

    runway_before = round(base_liquid / (base_fixed_expenses + base_emis), 1) if (base_fixed_expenses + base_emis) > 0 else 99.0
    runway_after = round(new_liquid / (new_expenses + base_emis), 1) if (new_expenses + base_emis) > 0 else 99.0

    r_yr = 0.07
    projected_nw_1y_base = base_liquid + (base_sips * 12 * 1.035) + max(0.0, base_surplus * 12)
    projected_nw_1y_sim = new_liquid + (new_sips * 12 * 1.035) + max(0.0, new_surplus * 12)
    projected_nw_3y_base = base_liquid * ((1 + r_yr)**3) + (base_sips * 36 * 1.1) + max(0.0, base_surplus * 36)
    projected_nw_3y_sim = new_liquid * ((1 + r_yr)**3) + (new_sips * 36 * 1.1) + max(0.0, new_surplus * 36)

    goals_sim = []
    for g in active_goals:
        cur_contrib = float(g.get("monthly_contribution") or 0.0)
        rem_amt = float(g.get("remaining_amount") or 0.0)
        adjusted_contrib = max(100.0, cur_contrib + (sip_delta_abs if len(active_goals) == 1 else (sip_delta_abs / max(1, len(active_goals)))))
        new_months = round(rem_amt / adjusted_contrib, 1) if adjusted_contrib > 0 else None
        base_months = round(rem_amt / cur_contrib, 1) if cur_contrib > 0 else None
        months_saved = round(base_months - new_months, 1) if base_months and new_months else 0.0

        goals_sim.append({
            "goal_id": g.get("id"),
            "name": g.get("name"),
            "base_months": base_months,
            "new_months": new_months,
            "months_saved": months_saved,
        })

    return {
        "inputs": {
            "income_delta_pct": income_delta_pct,
            "sip_delta_abs": sip_delta_abs,
            "expense_delta_abs": expense_delta_abs,
            "one_time_expense": one_time_expense,
        },
        "base": {
            "income": base_income,
            "surplus": base_surplus,
            "sips": base_sips,
            "runway_months": runway_before,
            "net_worth_1y": round(projected_nw_1y_base, 0),
            "net_worth_3y": round(projected_nw_3y_base, 0),
        },
        "simulated": {
            "income": new_income,
            "surplus": new_surplus,
            "sips": new_sips,
            "runway_months": runway_after,
            "net_worth_1y": round(projected_nw_1y_sim, 0),
            "net_worth_3y": round(projected_nw_3y_sim, 0),
        },
        "deltas": {
            "surplus_change": new_surplus - base_surplus,
            "runway_change_months": round(runway_after - runway_before, 1),
            "net_worth_1y_delta": round(projected_nw_1y_sim - projected_nw_1y_base, 0),
        },
        "goals": goals_sim,
    }


def run_stress_test(
    stress_type: str,
    monthly_income: float,
    fixed_expenses: float,
    emis: float,
    sips: float,
    liquid_funds: float,
    active_goals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    scenario_titles = {
        "INCOME_DROP_10": "10% Income Cut",
        "INCOME_DROP_20": "20% Income Cut",
        "INCOME_ZERO": "Complete Income Disruption (0 Income)",
        "UNEXPECTED_EXPENSE_50K": "Sudden ₹50,000 Emergency Outflow",
        "UNEXPECTED_EXPENSE_1L": "Sudden ₹1,00,000 Emergency Outflow",
        "EMI_HIKE_15": "Interest Rate Shock (+15% EMI)",
    }

    test_income = monthly_income
    test_expenses = fixed_expenses
    test_emis = emis
    test_sips = sips
    test_liquid = liquid_funds

    if stress_type == "INCOME_DROP_10":
        test_income = monthly_income * 0.90
    elif stress_type == "INCOME_DROP_20":
        test_income = monthly_income * 0.80
    elif stress_type == "INCOME_ZERO":
        test_income = 0.0
    elif stress_type == "UNEXPECTED_EXPENSE_50K":
        test_liquid = max(0.0, liquid_funds - 50000.0)
    elif stress_type == "UNEXPECTED_EXPENSE_1L":
        test_liquid = max(0.0, liquid_funds - 100000.0)
    elif stress_type == "EMI_HIKE_15":
        test_emis = emis * 1.15

    essential_outflow = test_expenses + test_emis
    total_committed = essential_outflow + test_sips
    surplus_deficit = test_income - total_committed

    survival_runway = round(test_liquid / essential_outflow, 1) if essential_outflow > 0 else 99.0

    base_surplus = monthly_income - (fixed_expenses + emis + sips)
    recovery_months = None
    if "UNEXPECTED_EXPENSE" in stress_type and base_surplus > 0:
        cost = 50000.0 if "50K" in stress_type else 100000.0
        recovery_months = round(cost / base_surplus, 1)

    if test_income == 0.0 or survival_runway < 2.0 or surplus_deficit < -15000:
        risk_level = "CRITICAL"
    elif survival_runway < 4.0 or surplus_deficit < 0:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    recommendations = []
    if surplus_deficit < 0:
        shortfall = abs(surplus_deficit)
        if test_sips > 0:
            if test_sips >= shortfall:
                recommendations.append(f"Pausing discretionary SIPs (₹{int(test_sips):,}) immediately neutralizes the monthly deficit.")
            else:
                recommendations.append(f"Pausing SIPs reduces the deficit to ₹{int(shortfall - test_sips):,}/month.")
        recommendations.append(f"Essential commitments (Rent/EMI) require minimum ₹{int(essential_outflow):,}/month.")
    else:
        recommendations.append(f"Plan absorbs this shock with ₹{int(surplus_deficit):,} monthly surplus still intact.")

    return {
        "stress_type": stress_type,
        "title": scenario_titles.get(stress_type, stress_type),
        "tested_income": test_income,
        "tested_essential_outflow": essential_outflow,
        "tested_liquid_funds": test_liquid,
        "surplus_deficit": surplus_deficit,
        "survival_runway_months": survival_runway,
        "recovery_months": recovery_months,
        "risk_level": risk_level,
        "recommendations": recommendations,
        "goals_impacted": len(active_goals) if surplus_deficit < 0 else 0,
    }


def simulate_debt_extra_payment(
    outstanding_balance: float,
    current_emi: float,
    annual_interest_rate_pct: float,
    extra_monthly_payment: float = 5000.0,
) -> Dict[str, Any]:
    r = (annual_interest_rate_pct / 100.0) / 12.0
    if outstanding_balance <= 0 or current_emi <= (outstanding_balance * r):
        return {
            "outstanding_balance": max(0.0, outstanding_balance),
            "current_emi": current_emi,
            "extra_payment": extra_monthly_payment,
            "annual_interest_rate": annual_interest_rate_pct,
            "base_months_remaining": 0,
            "accelerated_months_remaining": 0,
            "months_saved": 0,
            "base_total_interest": 0.0,
            "accelerated_total_interest": 0.0,
            "interest_saved": 0.0,
            "amortizes": outstanding_balance <= 0,
        }

    def _amortize(p: float, emi: float, monthly_r: float) -> Tuple[int, float]:
        bal = p
        months = 0
        total_interest = 0.0
        while bal > 0.01 and months < 360:
            months += 1
            interest = bal * monthly_r
            total_interest += interest
            principal_paid = min(bal, emi - interest)
            bal -= principal_paid
        return months, round(total_interest, 0)

    base_months, base_interest = _amortize(outstanding_balance, current_emi, r)
    new_months, new_interest = _amortize(outstanding_balance, current_emi + extra_monthly_payment, r)

    months_saved = max(0, base_months - new_months)
    interest_saved = max(0.0, base_interest - new_interest)

    return {
        "outstanding_balance": outstanding_balance,
        "current_emi": current_emi,
        "extra_payment": extra_monthly_payment,
        "annual_interest_rate": annual_interest_rate_pct,
        "base_months_remaining": base_months,
        "accelerated_months_remaining": new_months,
        "months_saved": months_saved,
        "base_total_interest": base_interest,
        "accelerated_total_interest": new_interest,
        "interest_saved": interest_saved,
        "amortizes": True,
    }
