"""Unit and edge-case tests for the AI Financial Planner engine."""
from datetime import date, timedelta

from app.planner import engine


def test_net_worth_calculation_standard():
    nw = engine.calculate_net_worth(
        bank_balances=150000.0,
        investments_value=300000.0,
        other_assets=50000.0,
        loans_outstanding=100000.0,
        credit_card_outstanding=20000.0,
    )
    assert nw["total_assets"] == 500000.0
    assert nw["total_liabilities"] == 120000.0
    assert nw["net_worth"] == 380000.0
    assert nw["asset_breakdown"]["liquid_pct"] == 30.0
    assert nw["asset_breakdown"]["investments_pct"] == 60.0


def test_net_worth_edge_cases():
    # Zero assets and zero liabilities
    nw = engine.calculate_net_worth(0.0, 0.0)
    assert nw["total_assets"] == 0.0
    assert nw["total_liabilities"] == 0.0
    assert nw["net_worth"] == 0.0

    # Negative inputs guarded to 0
    nw_neg = engine.calculate_net_worth(-50.0, -100.0)
    assert nw_neg["total_assets"] == 0.0


def test_cash_flow_and_surplus_standard():
    cf = engine.calculate_cash_flow(
        monthly_income=85000.0,
        fixed_expenses=30000.0,
        emis=12000.0,
        sips=10000.0,
        insurance_monthly=2500.0,
        discretionary_expenses=12000.0,
    )
    assert cf["committed_outflow"] == 54500.0
    assert cf["total_outflow"] == 66500.0
    assert cf["estimated_surplus"] == 18500.0
    assert abs(cf["savings_rate_pct"] - 33.5) < 1.0


def test_cash_flow_edge_cases():
    # Negative cash flow / deficit
    cf = engine.calculate_cash_flow(
        monthly_income=40000.0,
        fixed_expenses=30000.0,
        emis=15000.0,
        sips=5000.0,
        insurance_monthly=0.0,
    )
    assert cf["estimated_surplus"] == -10000.0
    # Zero income
    cf_zero = engine.calculate_cash_flow(
        monthly_income=0.0,
        fixed_expenses=20000.0,
        emis=0.0,
        sips=0.0,
        insurance_monthly=0.0,
    )
    assert cf_zero["estimated_surplus"] == -20000.0
    assert cf_zero["savings_rate_pct"] == 0.0


def test_runway_and_emergency_fund():
    # Standard 6-month runway check
    rw = engine.calculate_runway(
        liquid_funds=210000.0,
        essential_monthly_expenses=35000.0,
        target_months=6.0,
    )
    assert rw["current_runway_months"] == 6.0
    assert rw["target_emergency_fund"] == 210000.0
    assert rw["funding_gap"] == 0.0
    assert rw["status"] == "ADEQUATE"

    # Vulnerable runway
    rw_low = engine.calculate_runway(
        liquid_funds=35000.0,
        essential_monthly_expenses=35000.0,
        target_months=6.0,
    )
    assert rw_low["current_runway_months"] == 1.0
    assert rw_low["funding_gap"] == 175000.0
    assert rw_low["status"] == "VULNERABLE"

    # Zero expenses edge case
    rw_zero = engine.calculate_runway(liquid_funds=50000.0, essential_monthly_expenses=0.0)
    assert rw_zero["current_runway_months"] == 99.0


def test_goal_projection_and_gap():
    today = date(2026, 1, 1)
    target = date(2028, 1, 1).isoformat()  # 24 months

    proj = engine.calculate_goal_projection(
        target_amount=1200000.0,
        current_amount=240000.0,
        target_date_iso=target,
        monthly_contribution=20000.0,
        as_of=today,
    )
    # Remaining = 960,000 across ~24 months -> Required ~40,000/mo
    assert proj["remaining_amount"] == 960000.0
    assert abs(proj["required_monthly_contribution"] - 40000.0) < 2000
    assert proj["contribution_gap"] > 0
    assert proj["status"] == "BEHIND"
    assert proj["progress_pct"] == 20.0


def test_cash_flow_collision_detector():
    today = date(2026, 10, 1)
    obligations = [
        {"title": "SIP 1", "amount": 20000.0, "due": "2026-10-04"},
        {"title": "Loan EMI", "amount": 25000.0, "due": "2026-10-06"},
        {"title": "Insurance", "amount": 15000.0, "due": "2026-10-07"},
        {"title": "Late Month SIP", "amount": 10000.0, "due": "2026-10-25"},
    ]

    # Balance 50,000 vs 60,000 due in 7 days
    collisions = engine.detect_cash_flow_collisions(
        liquid_balance=50000.0,
        upcoming_obligations=obligations,
        as_of=today,
    )
    assert collisions["has_collision"] is True
    w7 = collisions["windows"]["7d"]
    assert w7["has_collision"] is True
    assert w7["total_obligations"] == 60000.0
    assert w7["shortfall"] == 10000.0
    assert len(w7["affected_obligations"]) == 3


def test_affordability_simulation():
    goals = [{"id": "g1", "name": "Travel", "target_amount": 100000.0, "current_amount": 20000.0, "monthly_contribution": 10000.0}]
    aff = engine.simulate_affordability(
        purchase_amount=75000.0,
        is_recurring=False,
        frequency="one_time",
        current_liquid=185000.0,
        monthly_income=85000.0,
        monthly_surplus=25000.0,
        essential_monthly_expenses=35000.0,
        active_goals=goals,
        upcoming_7d_obligations=10000.0,
    )
    assert aff["liquid_after"] == 110000.0
    assert abs(aff["runway_after_months"] - 3.1) < 0.5
    assert len(aff["goal_impacts"]) == 1


def test_what_if_simulation():
    goals = [{"id": "g1", "name": "House", "remaining_amount": 600000.0, "monthly_contribution": 20000.0}]
    res = engine.simulate_what_if(
        base_income=80000.0,
        base_fixed_expenses=30000.0,
        base_emis=10000.0,
        base_sips=15000.0,
        base_liquid=100000.0,
        active_goals=goals,
        sip_delta_abs=5000.0,
    )
    assert res["simulated"]["sips"] == 20000.0
    assert res["deltas"]["surplus_change"] == -5000.0
    # Goal timeline acceleration
    g_res = res["goals"][0]
    assert g_res["base_months"] == 30.0
    assert g_res["new_months"] == 24.0
    assert g_res["months_saved"] == 6.0


def test_stress_test_calculations():
    goals = [{"id": "g1", "name": "Retirement", "remaining_amount": 500000.0, "monthly_contribution": 10000.0}]
    stress_20 = engine.run_stress_test(
        stress_type="INCOME_DROP_20",
        monthly_income=100000.0,
        fixed_expenses=40000.0,
        emis=20000.0,
        sips=15000.0,
        liquid_funds=180000.0,
        active_goals=goals,
    )
    assert stress_20["tested_income"] == 80000.0
    assert stress_20["surplus_deficit"] == 5000.0
    assert stress_20["risk_level"] in ("LOW", "MODERATE")

    stress_zero = engine.run_stress_test(
        stress_type="INCOME_ZERO",
        monthly_income=100000.0,
        fixed_expenses=40000.0,
        emis=20000.0,
        sips=15000.0,
        liquid_funds=180000.0,
        active_goals=goals,
    )
    assert stress_zero["tested_income"] == 0.0
    assert stress_zero["survival_runway_months"] == 3.0
    assert stress_zero["risk_level"] == "CRITICAL"


def test_debt_extra_payment():
    debt = engine.simulate_debt_extra_payment(
        outstanding_balance=500000.0,
        current_emi=15000.0,
        annual_interest_rate_pct=11.5,
        extra_monthly_payment=5000.0,
    )
    assert debt["months_saved"] > 0
    assert debt["interest_saved"] > 0.0
    assert debt["accelerated_months_remaining"] < debt["base_months_remaining"]
