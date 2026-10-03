"""Pre-configured demo scenarios for the AI Financial Planner.

Enables one-click simulation of realistic financial situations:
1. Cash-flow collision (₹50k balance vs ₹60k obligations in 7 days)
2. Goal contribution gap (₹8L Car goal underfunded)
3. Affordability simulator ("Can I afford a ₹75k phone?")
4. What-If SIP increase (+₹5k/month accelerates goals)
5. Stress test: 20% income reduction shock
6. Active loan journey integrated into financial plan
7. Reusable Document Vault evidence for financial journeys
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, Dict

from app.database import db
from app.planner import engine, service


def load_scenario(user_id: str, scenario_id: int) -> Dict[str, Any]:
    today = date.today()

    if scenario_id == 1:
        # Scenario 1: Cash-flow collision (₹50k balance vs ₹60k obligations)
        # Set account balance to ₹50,000
        acc = db.query_one("SELECT * FROM accounts WHERE user_id=? ORDER BY created_at LIMIT 1", (user_id,))
        if acc:
            db.execute("UPDATE accounts SET balance=50000.0 WHERE id=?", (acc["id"],))

        # Ensure three obligations occur in next 7 days totaling ₹60,000
        # 1. Loan EMI ₹25,000
        lib = db.query_one("SELECT * FROM financial_liabilities WHERE user_id=?", (user_id,))
        if not lib:
            db.insert("financial_liabilities", {
                "id": f"lib-{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "name": "HDFC Auto Loan",
                "lender": "HDFC Bank",
                "kind": "auto_loan",
                "total_amount": 750000.0,
                "outstanding_amount": 420000.0,
                "emi_amount": 25000.0,
                "interest_rate": 8.75,
                "tenure_months": 36,
                "start_date": (today - timedelta(days=180)).isoformat(),
                "next_due_date": (today + timedelta(days=3)).isoformat(),
                "journey_id": None,
                "created_at": service._now_iso(),
            })
        else:
            db.execute(
                "UPDATE financial_liabilities SET emi_amount=25000.0, next_due_date=? WHERE id=?",
                ((today + timedelta(days=3)).isoformat(), lib["id"]),
            )

        # 2. SIP installment ₹20,000
        sip = db.query_one("SELECT * FROM sips WHERE user_id=? AND status='ACTIVE' LIMIT 1", (user_id,))
        if sip:
            db.execute(
                "UPDATE sips SET amount=20000.0, next_due=? WHERE id=?",
                ((today + timedelta(days=5)).isoformat(), sip["id"]),
            )

        # 3. Insurance premium ₹15,000
        # Check if an insurance journey exists or insert a liability / obligation
        ins_lib = db.query_one("SELECT * FROM financial_liabilities WHERE user_id=? AND kind='insurance'", (user_id,))
        if not ins_lib:
            db.insert("financial_liabilities", {
                "id": f"lib-{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "name": "Family Health Shield Premium",
                "lender": "Suraksha Insurance",
                "kind": "insurance",
                "total_amount": 15000.0,
                "outstanding_amount": 15000.0,
                "emi_amount": 15000.0,
                "interest_rate": 0.0,
                "tenure_months": 1,
                "start_date": today.isoformat(),
                "next_due_date": (today + timedelta(days=6)).isoformat(),
                "journey_id": None,
                "created_at": service._now_iso(),
            })
        else:
            db.execute("UPDATE financial_liabilities SET emi_amount=15000.0, next_due_date=? WHERE id=?",
                       ((today + timedelta(days=6)).isoformat(), ins_lib["id"]))

        service.log_plan_change(
            user_id=user_id,
            change_type="DEMO_SCENARIO_1_LOADED",
            prev_val="Normal",
            new_val="Collision State",
            reason="Loaded Demo Scenario 1: Cash-Flow Collision",
            impact_summary="Bank balance set to ₹50,000 against ₹60,000 in obligations due within 7 days.",
        )
        return {
            "scenario": 1,
            "title": "Cash-Flow Collision Detected",
            "description": "Available balance is ₹50,000. Three upcoming obligations (SIP ₹20k, EMI ₹25k, Insurance ₹15k) total ₹60,000 in the next 7 days, creating a ₹10,000 shortfall.",
        }

    elif scenario_id == 2:
        # Scenario 2: Car goal contribution gap (₹8L in 3 years with ₹15k/mo contribution)
        # Required is ₹22,222/mo -> gap of ₹7,222/mo
        existing_goal = db.query_one("SELECT * FROM financial_goals WHERE user_id=? AND name LIKE '%Car%'", (user_id,))
        target_d = (today + timedelta(days=36 * 30)).isoformat()
        if existing_goal:
            db.execute(
                "UPDATE financial_goals SET target_amount=800000.0, current_amount=120000.0, monthly_contribution=15000.0, target_date=? WHERE id=?",
                (target_d, existing_goal["id"]),
            )
            gid = existing_goal["id"]
        else:
            g = service.create_goal(user_id, {
                "name": "Electric SUV Car",
                "category": "car",
                "target_amount": 800000.0,
                "current_amount": 120000.0,
                "target_date": target_d,
                "monthly_contribution": 15000.0,
                "priority": 2,
                "notes": "Planning for new EV in 3 years",
            })
            gid = g["id"]

        return {
            "scenario": 2,
            "goal_id": gid,
            "title": "Goal Contribution Gap",
            "description": "₹8,00,000 Car Goal in 3 years has a current contribution of ₹15,000/mo. Saarthi calculates a ₹7,222/month funding gap to reach target on schedule.",
        }

    elif scenario_id == 3:
        # Scenario 3: Affordability simulator trigger
        cc = service.build_command_center(user_id)
        sim = engine.simulate_affordability(
            purchase_amount=75000.0,
            is_recurring=False,
            frequency="one_time",
            current_liquid=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
            monthly_income=cc["profile"]["monthly_income"],
            monthly_surplus=cc["cash_flow"]["estimated_surplus"],
            essential_monthly_expenses=cc["profile"]["essential_expenses"],
            active_goals=cc["goals"],
            upcoming_7d_obligations=15000.0,
        )
        return {
            "scenario": 3,
            "title": "Can I Afford a ₹75,000 Phone?",
            "simulation": sim,
        }

    elif scenario_id == 4:
        # Scenario 4: Increase SIP by ₹5k
        cc = service.build_command_center(user_id)
        sim = engine.simulate_what_if(
            base_income=cc["profile"]["monthly_income"],
            base_fixed_expenses=cc["profile"]["essential_expenses"],
            base_emis=cc["cash_flow"]["emis"],
            base_sips=cc["cash_flow"]["sips"],
            base_liquid=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
            active_goals=cc["goals"],
            sip_delta_abs=5000.0,
        )
        return {
            "scenario": 4,
            "title": "What If I Increase SIP by ₹5,000?",
            "simulation": sim,
        }

    elif scenario_id == 5:
        # Scenario 5: Stress test - 20% income reduction shock
        cc = service.build_command_center(user_id)
        stress = engine.run_stress_test(
            stress_type="INCOME_DROP_20",
            monthly_income=cc["profile"]["monthly_income"],
            fixed_expenses=cc["profile"]["essential_expenses"],
            emis=cc["cash_flow"]["emis"],
            sips=cc["cash_flow"]["sips"],
            liquid_funds=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
            active_goals=cc["goals"],
        )
        return {
            "scenario": 5,
            "title": "Financial Stress Test: 20% Income Cut",
            "stress_test": stress,
        }

    elif scenario_id == 6:
        # Scenario 6: Active loan journey integrated into financial plan
        # Ensure a loan journey exists for user
        j = db.query_one("SELECT * FROM journeys WHERE user_id=? AND category='loan'", (user_id,))
        if not j:
            from app.product import applications
            acc = db.query_one("SELECT * FROM accounts WHERE user_id=? AND status='VERIFIED'", (user_id,))
            if acc:
                try:
                    user = db.query_one("SELECT * FROM users WHERE id=?", (user_id,))
                    applications.start(user, "vistara_finance", {
                        "amount": 350000.0,
                        "tenure_months": 36,
                        "monthly_income": 75000.0,
                        "account_id": acc["id"],
                    })
                except Exception:
                    pass
        return {
            "scenario": 6,
            "title": "Loan Journey Integrated in Plan",
            "description": "Active loan journey automatically surfaces in the Financial Planner as committed liability, upcoming EMI obligations, and impact on monthly surplus.",
        }

    elif scenario_id == 7:
        # Scenario 7: Document Vault evidence reuse
        docs = vault.list_for({"id": user_id})
        has_salary = any(d.get("doc_type") == "salary_slip" for d in docs)
        if not has_salary:
            # Upload a sample salary slip into the vault for user
            acc = db.query_one("SELECT * FROM accounts WHERE user_id=?", (user_id,))
            user = db.query_one("SELECT * FROM users WHERE id=?", (user_id,))
            from app.services import samples
            data, filename = samples.generate("salary_slip", user, acc)
            vault.upload(user, data, filename, "application/pdf", "salary_slip")

        return {
            "scenario": 7,
            "title": "Document Vault Reusable Evidence",
            "description": "Verified salary slip in Document Vault automatically grounds verified monthly income in the Financial Planner and auto-fulfills KYC/income proofs for future loan/credit journeys.",
        }

    return {"error": "Unknown scenario id"}
