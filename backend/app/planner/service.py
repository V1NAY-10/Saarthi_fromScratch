"""Financial Planner data service.

Integrates:
- Bank accounts & balances (accounts table)
- Portfolio & SIPs (funds, sips tables)
- Document Vault metadata & verified income (documents, document_versions)
- Loans & Insurance journeys (journeys, financial_liabilities)
- Financial goals & goal-to-investment mapping (financial_goals, goal_investments)
- Planner change logs (planner_change_logs)

Ensures calculations are deterministic and data is drawn directly from Saarthi's live tables.
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.database import db
from app.planner import engine
from app.product import accounts, sips, vault


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


DEFAULT_INCOME_SOURCE = "User estimate"


def _verified_income(user_id: str) -> Optional[Dict[str, Any]]:
    """Net monthly pay from the latest verified salary slip in the Document Vault, if any."""
    for d in vault.latest_versions(user_id):
        if (d.get("doc_type") or "").upper() != "SALARY_SLIP" or d.get("status") != "VERIFIED":
            continue
        try:
            net_pay = float((d.get("fields") or {}).get("net_pay") or 0)
        except (TypeError, ValueError):
            continue
        if net_pay > 0:
            return {"monthly_income": net_pay, "income_source": f"Verified from {d.get('name') or 'salary slip'}"}
    return None


def get_or_create_profile(user_id: str) -> Dict[str, Any]:
    row = db.query_one("SELECT * FROM financial_profiles WHERE user_id=?", (user_id,))
    if row:
        # An estimate the user never edited is upgraded once a verified salary slip lands in the vault.
        if not row.get("income_verified") and row.get("income_source") == DEFAULT_INCOME_SOURCE:
            v = _verified_income(user_id)
            if v:
                row = {**row, **v, "income_verified": 1, "updated_at": _now_iso()}
                db.insert("financial_profiles", row)
        return row

    v = _verified_income(user_id)
    profile = {
        "user_id": user_id,
        "monthly_income": v["monthly_income"] if v else 85000.0,
        "income_source": v["income_source"] if v else DEFAULT_INCOME_SOURCE,
        "income_verified": 1 if v else 0,
        "essential_expenses": 32000.0,
        "discretionary_expenses": 12000.0,
        "target_runway_months": 6.0,
        "emergency_fund_target": 32000.0 * 6.0,
        "salary_day": 1,
        "updated_at": _now_iso(),
    }
    db.insert("financial_profiles", profile)
    return profile


def update_profile(user_id: str, updates: Dict[str, Any], reason: str = "User profile update") -> Dict[str, Any]:
    curr = get_or_create_profile(user_id)
    updates = {k: v for k, v in updates.items() if v is not None}
    prev_income = curr.get("monthly_income")

    new_income = max(0.0, float(updates.get("monthly_income", curr["monthly_income"])))
    essential = max(0.0, float(updates.get("essential_expenses", curr["essential_expenses"])))
    discretionary = max(0.0, float(updates.get("discretionary_expenses", curr["discretionary_expenses"])))
    target_runway = max(1.0, float(updates.get("target_runway_months", curr["target_runway_months"])))
    salary_day = min(28, max(1, int(updates.get("salary_day", curr.get("salary_day") or 1))))

    income_edited = "monthly_income" in updates and new_income != prev_income
    updated = {
        "user_id": user_id,
        "monthly_income": new_income,
        "income_source": "User entered" if income_edited else curr["income_source"],
        "income_verified": 0 if income_edited else curr["income_verified"],
        "essential_expenses": essential,
        "discretionary_expenses": discretionary,
        "target_runway_months": target_runway,
        "emergency_fund_target": essential * target_runway,
        "salary_day": salary_day,
        "updated_at": _now_iso(),
    }
    db.insert("financial_profiles", updated)

    # Log change if income changed
    if prev_income != new_income:
        delta = new_income - prev_income
        log_plan_change(
            user_id=user_id,
            change_type="INCOME_CHANGED",
            prev_val=f"₹{int(prev_income):,}",
            new_val=f"₹{int(new_income):,}",
            reason=reason,
            impact_summary=f"Monthly cash-flow surplus {'increased' if delta > 0 else 'decreased'} by ₹{abs(int(delta)):,}.",
        )

    return updated


def _next_monthly_due(due_iso: Optional[str], today: date) -> str:
    try:
        d = date.fromisoformat((due_iso or "")[:10])
    except ValueError:
        return (today + timedelta(days=7)).isoformat()
    while d < today:
        d = date(d.year + (1 if d.month == 12 else 0), d.month % 12 + 1, min(d.day, 28))
    return d.isoformat()


def list_liabilities(user_id: str) -> List[Dict[str, Any]]:
    # 1. Stored liabilities
    liabilities = db.query("SELECT * FROM financial_liabilities WHERE user_id=?", (user_id,))
    today = date.today()
    for lib in liabilities:
        rolled = _next_monthly_due(lib.get("next_due_date"), today)
        if rolled != lib.get("next_due_date"):
            db.execute("UPDATE financial_liabilities SET next_due_date=? WHERE id=?", (rolled, lib["id"]))
            lib["next_due_date"] = rolled

    # 2. Derive liabilities from loan journeys - only once the money was actually disbursed.
    #    An application still collecting documents is not debt.
    loan_journeys = db.query(
        "SELECT * FROM journeys WHERE user_id=? AND category='loan' AND stage='Disbursed'", (user_id,)
    )
    disbursed = {j["id"] for j in loan_journeys}
    stale = [l for l in liabilities if l.get("journey_id") and l["journey_id"] not in disbursed]
    for l in stale:  # rows an older version derived from undisbursed applications
        db.execute("DELETE FROM financial_liabilities WHERE id=?", (l["id"],))
    liabilities = [l for l in liabilities if l not in stale]
    existing_jids = {l.get("journey_id") for l in liabilities if l.get("journey_id")}

    for j in loan_journeys:
        if j["id"] in existing_jids:
            continue
        state = j.get("state") or {}
        app = state.get("application") or {}
        amt = float(app.get("amount") or j.get("amount") or 0.0)
        emi = float(app.get("emi") or (amt * 0.035))
        rate = float(app.get("rate") or 12.5)
        tenure = int(app.get("tenure_months") or 36)

        # Create liability record
        new_lib = {
            "id": f"lib-{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "name": j.get("title") or "Personal Loan",
            "lender": j.get("subtitle") or "Lender",
            "kind": "personal_loan",
            "total_amount": amt,
            "outstanding_amount": amt,  # freshly disbursed: full principal outstanding
            "emi_amount": emi,
            "interest_rate": rate,
            "tenure_months": tenure,
            "start_date": (j.get("created_at") or _now_iso())[:10],
            "next_due_date": (date.today() + timedelta(days=7)).isoformat(),
            "journey_id": j["id"],
            "created_at": _now_iso(),
        }
        db.insert("financial_liabilities", new_lib)
        liabilities.append(new_lib)

    return liabilities


def list_goals(user_id: str) -> List[Dict[str, Any]]:
    rows = db.query("SELECT * FROM financial_goals WHERE user_id=? ORDER BY priority ASC, created_at ASC", (user_id,))
    out = []
    today = date.today()

    for r in rows:
        proj = engine.calculate_goal_projection(
            target_amount=float(r["target_amount"]),
            current_amount=float(r["current_amount"]),
            target_date_iso=r["target_date"],
            monthly_contribution=float(r["monthly_contribution"]),
            annual_growth_pct=8.0 if r.get("category") in ("retirement", "house", "education") else 0.0,
            as_of=today,
        )

        # Mapped investments
        mappings = db.query("SELECT * FROM goal_investments WHERE goal_id=?", (r["id"],))

        on_track = proj["status"] in ("ON_TRACK", "COMPLETED")
        out.append({
            **r,
            **proj,
            "lifecycle_status": r.get("status") or "ACTIVE",  # stored ACTIVE / PAUSED; "status" is the projection
            "mappings": mappings,
            "linked_investments": mappings,
            "mapped_investments_count": len(mappings),
            "months_remaining": proj["months_left"],
            "monthly_required": proj["required_monthly_contribution"],
            "on_track": on_track,
            "shortfall_projected": 0.0 if on_track else round(max(0.0, proj["contribution_gap"]) * proj["months_left"], 0),
        })

    return out


def create_goal(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    gid = f"goal-{uuid.uuid4().hex[:8]}"
    now = _now_iso()
    goal = {
        "id": gid,
        "user_id": user_id,
        "name": data["name"],
        "category": data.get("category", "custom"),
        "target_amount": float(data["target_amount"]),
        "current_amount": float(data.get("current_amount", 0.0)),
        "target_date": data["target_date"],
        "monthly_contribution": float(data.get("monthly_contribution", 0.0)),
        "priority": int(data.get("priority", 1)),
        "status": "ACTIVE",
        "notes": data.get("notes", ""),
        "created_at": now,
        "updated_at": now,
    }
    db.insert("financial_goals", goal)

    log_plan_change(
        user_id=user_id,
        change_type="GOAL_CREATED",
        prev_val="None",
        new_val=f"{goal['name']} (₹{int(goal['target_amount']):,})",
        reason="User created new financial goal",
        impact_summary=f"Requires monthly planned contribution of ₹{int(goal['monthly_contribution']):,}.",
        affected_goals=[gid],
    )
    return goal


def update_goal(user_id: str, goal_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    curr = db.query_one("SELECT * FROM financial_goals WHERE id=? AND user_id=?", (goal_id, user_id))
    if not curr:
        return None
    updates = {k: v for k, v in updates.items() if v is not None}

    prev_contrib = curr.get("monthly_contribution", 0.0)
    new_contrib = float(updates.get("monthly_contribution", prev_contrib))

    row = {
        "id": goal_id,
        "user_id": user_id,
        "name": updates.get("name", curr["name"]),
        "category": updates.get("category", curr["category"]),
        "target_amount": float(updates.get("target_amount", curr["target_amount"])),
        "current_amount": float(updates.get("current_amount", curr["current_amount"])),
        "target_date": updates.get("target_date", curr["target_date"]),
        "monthly_contribution": new_contrib,
        "priority": int(updates.get("priority", curr["priority"])),
        "status": updates.get("status", curr["status"]),
        "notes": updates.get("notes", curr.get("notes", "")),
        "created_at": curr["created_at"],
        "updated_at": _now_iso(),
    }
    db.insert("financial_goals", row)

    if prev_contrib != new_contrib:
        log_plan_change(
            user_id=user_id,
            change_type="GOAL_CONTRIBUTION_CHANGED",
            prev_val=f"₹{int(prev_contrib):,}/mo",
            new_val=f"₹{int(new_contrib):,}/mo",
            reason="User adjusted goal monthly savings",
            impact_summary=f"Timeline for {row['name']} updated.",
            affected_goals=[goal_id],
        )

    return row


def add_money_to_goal(user_id: str, goal_id: str, amount: float) -> Optional[Dict[str, Any]]:
    curr = db.query_one("SELECT * FROM financial_goals WHERE id=? AND user_id=?", (goal_id, user_id))
    if not curr:
        return None
    new_amount = round(float(curr["current_amount"] or 0.0) + amount, 2)
    db.update("financial_goals", "id", goal_id, {"current_amount": new_amount, "updated_at": _now_iso()})
    remaining = max(0.0, float(curr["target_amount"]) - new_amount)
    log_plan_change(
        user_id=user_id,
        change_type="GOAL_TOPUP",
        prev_val=f"₹{int(curr['current_amount'] or 0):,}",
        new_val=f"₹{int(new_amount):,}",
        reason=f"Added money to {curr['name']}",
        impact_summary="Goal fully funded!" if remaining <= 0 else f"₹{int(remaining):,} left to reach the target.",
        affected_goals=[goal_id],
    )
    return next((g for g in list_goals(user_id) if g["id"] == goal_id), None)


def delete_goal(user_id: str, goal_id: str) -> bool:
    curr = db.query_one("SELECT * FROM financial_goals WHERE id=? AND user_id=?", (goal_id, user_id))
    if not curr:
        return False
    db.execute("DELETE FROM financial_goals WHERE id=? AND user_id=?", (goal_id, user_id))
    db.execute("DELETE FROM goal_investments WHERE goal_id=?", (goal_id,))
    log_plan_change(
        user_id=user_id,
        change_type="GOAL_DELETED",
        prev_val=curr["name"],
        new_val="Deleted",
        reason="User removed financial goal",
        impact_summary=f"Freed up ₹{int(curr['monthly_contribution']):,}/month in surplus.",
    )
    return True


def link_investment_to_goal(user_id: str, goal_id: str, investment_id: str, investment_type: str,
                            allocated_amount: float) -> Optional[Dict[str, Any]]:
    if not db.query_one("SELECT id FROM financial_goals WHERE id=? AND user_id=?", (goal_id, user_id)):
        return None
    row = {
        "goal_id": goal_id,
        "investment_id": investment_id,
        "investment_type": investment_type,
        "allocated_amount": allocated_amount,
    }
    db.insert("goal_investments", row)
    return row


def get_upcoming_obligations(user_id: str) -> List[Dict[str, Any]]:
    """Aggregates all upcoming financial obligations from SIPs, loans, insurance and recurring payments."""
    obligations = []
    today = date.today()

    # 1. SIP installments
    my_sips = sips.for_user(user_id)
    for s in my_sips:
        if s["status"] == "ACTIVE":
            due_str = s.get("next_due") or (today + timedelta(days=s.get("sip_day", 5))).isoformat()
            obligations.append({
                "id": f"sip-{s['id']}",
                "title": f"SIP: {s['fund']['name']}",
                "kind": "sip",
                "amount": float(s["amount"]),
                "due": due_str,
                "partner_id": (s.get("account") or {}).get("bank"),
                "status": "failed" if s.get("journey_status") == "ATTENTION" else "upcoming",
                "journey_id": s.get("journey_id"),
                "icon": "sip",
                "category": "sip",
                "source": " ".join(filter(None, ["Autopay ·", (s.get("account") or {}).get("bank"), (s.get("account") or {}).get("masked")])),
            })

    # 2. Loan EMIs
    libs = list_liabilities(user_id)
    for lib in libs:
        emi = float(lib.get("emi_amount") or 0.0)
        if emi > 0:
            due_str = lib.get("next_due_date") or (today + timedelta(days=7)).isoformat()
            obligations.append({
                "id": f"emi-{lib['id']}",
                "title": f"EMI: {lib['name']}",
                "kind": "emi",
                "amount": emi,
                "due": due_str,
                "partner_id": lib.get("lender"),
                "status": "upcoming",
                "journey_id": lib.get("journey_id"),
                "icon": "loan",
                "category": "insurance" if lib.get("kind") == "insurance" else "emi",
                "recipient": lib.get("lender"),
            })

    # 3. Active Insurance journeys
    ins_journeys = db.query(
        "SELECT * FROM journeys WHERE user_id=? AND category='insurance' AND stage='Policy issued'",
        (user_id,)
    )
    for j in ins_journeys:
        state = j.get("state") or {}
        app = state.get("application") or {}
        prem = float(app.get("premium") or (j.get("amount") or 0.0))
        if prem > 0:
            due_str = (today + timedelta(days=15)).isoformat()
            obligations.append({
                "id": f"ins-{j['id']}",
                "title": f"Insurance: {j.get('title')}",
                "kind": "insurance",
                "amount": prem,
                "due": due_str,
                "partner_id": j.get("partner_id"),
                "status": "upcoming",
                "journey_id": j["id"],
                "icon": "shield",
                "category": "insurance",
                "recipient": j.get("subtitle"),
            })

    return sorted(obligations, key=lambda o: o["due"])


def get_financial_calendar(user_id: str, month: Optional[str] = None) -> List[Dict[str, Any]]:
    """Builds calendar event dots and event list for financial obligations and milestones."""
    obligations = get_upcoming_obligations(user_id)
    calendar_events = []

    for ob in obligations:
        calendar_events.append({
            "id": ob["id"],
            "date": ob["due"][:10],
            "title": ob["title"],
            "amount": ob["amount"],
            "kind": ob["kind"],
            "status": ob.get("status", "upcoming"),
            "journey_id": ob.get("journey_id"),
        })

    # Add goal target dates
    goals = list_goals(user_id)
    for g in goals:
        calendar_events.append({
            "id": f"goal-milestone-{g['id']}",
            "date": g["target_date"][:10],
            "title": f"Goal Milestone: {g['name']}",
            "amount": g["target_amount"],
            "kind": "goal_milestone",
            "status": g["status"],
        })

    return sorted(calendar_events, key=lambda e: e["date"])


def log_plan_change(
    user_id: str,
    change_type: str,
    prev_val: str,
    new_val: str,
    reason: str,
    impact_summary: str,
    affected_goals: Optional[List[str]] = None,
) -> None:
    row = {
        "user_id": user_id,
        "ts": _now_iso(),
        "change_type": change_type,
        "previous_val": prev_val,
        "new_val": new_val,
        "reason": reason,
        "impact_summary": impact_summary,
        "affected_goals_json": affected_goals or [],
    }
    db.insert("planner_change_logs", row)


def get_plan_change_log(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    rows = db.query(
        "SELECT * FROM planner_change_logs WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    return rows


def build_command_center(user_id: str) -> Dict[str, Any]:
    """Assembles the complete Financial Command Center snapshot."""
    profile = get_or_create_profile(user_id)
    user_accs = accounts.for_user(user_id)
    user_sips = sips.for_user(user_id)
    goals = list_goals(user_id)
    liabilities = list_liabilities(user_id)
    obligations = get_upcoming_obligations(user_id)

    # 1. Balances & Net Worth
    liquid_cash = sum(a["balance"] for a in user_accs)
    investments_val = sum(s["current_value"] for s in user_sips)
    loans_total = sum(l["outstanding_amount"] for l in liabilities)

    net_worth = engine.calculate_net_worth(
        bank_balances=liquid_cash,
        investments_value=investments_val,
        loans_outstanding=loans_total,
    )

    # 2. Monthly Outflows & Cash Flow
    emis_total = sum(l["emi_amount"] for l in liabilities)
    sips_total = sum(s["amount"] for s in user_sips if s["status"] == "ACTIVE")
    insurance_monthly = sum(ob["amount"] for ob in obligations if ob["kind"] == "insurance") / 12.0
    planned_goals = sum(g["monthly_contribution"] for g in goals if g["lifecycle_status"] == "ACTIVE")

    cash_flow = engine.calculate_cash_flow(
        monthly_income=profile["monthly_income"],
        fixed_expenses=profile["essential_expenses"],
        emis=emis_total,
        sips=sips_total,
        insurance_monthly=insurance_monthly,
        discretionary_expenses=profile["discretionary_expenses"],
        planned_goal_contributions=planned_goals,
    )
    # Aliases the planner UI reads
    cash_flow.update({
        "income": cash_flow["monthly_income"],
        "essential_expenses": cash_flow["fixed_expenses"],
        "total_expenses": cash_flow["fixed_expenses"] + cash_flow["discretionary_expenses"],
        "total_obligations": cash_flow["committed_outflow"],
        "free_cash_flow": cash_flow["estimated_surplus"],
    })

    # 3. Runway & Emergency Fund
    essential_monthly = profile["essential_expenses"] + emis_total
    runway = engine.calculate_runway(
        liquid_funds=liquid_cash,
        essential_monthly_expenses=essential_monthly,
        target_months=profile["target_runway_months"],
    )

    # 3b. Safe-to-spend until payday, and the 30-day balance forecast
    profile = {**profile, "salary_day": int(profile.get("salary_day") or 1)}
    pulse = engine.calculate_safe_to_spend(
        liquid_balance=liquid_cash,
        upcoming_obligations=obligations,
        essential_monthly_expenses=profile["essential_expenses"],
        discretionary_monthly=profile["discretionary_expenses"],
        salary_day=profile["salary_day"],
    )
    forecast = engine.forecast_balance(
        liquid_balance=liquid_cash,
        upcoming_obligations=obligations,
        monthly_income=profile["monthly_income"],
        monthly_living_costs=profile["essential_expenses"] + profile["discretionary_expenses"],
        salary_day=profile["salary_day"],
    )

    # 4. Collisions
    collisions = engine.detect_cash_flow_collisions(
        liquid_balance=liquid_cash,
        upcoming_obligations=obligations,
    )

    # 5. Goal Conflict & Allocation Gap
    # If planned goal contributions exceed estimated surplus (before goal contributions)
    uncommitted_surplus = cash_flow["monthly_income"] - cash_flow["committed_outflow"] - cash_flow["discretionary_expenses"]
    allocation_gap = max(0.0, planned_goals - uncommitted_surplus)
    has_goal_conflict = allocation_gap > 0

    # 6. Contextual Financial Attention Cards
    attention_cards = []

    # Check cash-flow collision
    c_7d = collisions["windows"].get("7d", {})
    if c_7d.get("has_collision"):
        attention_cards.append({
            "id": "attn-collision-7d",
            "type": "COLLISION",
            "level": "critical",
            "title": f"Cash-flow collision in next 7 days: ₹{int(c_7d['shortfall']):,} shortfall",
            "detail": f"Upcoming obligations total ₹{int(c_7d['total_obligations']):,} against available bank balance of ₹{int(liquid_cash):,}.",
            "action_label": "Review obligations",
            "action_type": "NAVIGATE_TAB",
            "action_target": "calendar",
        })

    # Projected balance dips below zero within the forecast window
    if forecast["first_negative_date"] and not c_7d.get("has_collision"):
        attention_cards.append({
            "id": "attn-forecast-negative",
            "type": "FORECAST_NEGATIVE",
            "level": "critical",
            "title": f"Balance projected to run out on {date.fromisoformat(forecast['first_negative_date']):%d %b}",
            "detail": f"At your usual spending, debits and living costs outrun income; the lowest point is "
                      f"₹{int(forecast['lowest']['balance']):,} on {date.fromisoformat(forecast['lowest']['date']):%d %b}.",
            "action_label": "See forecast",
            "action_type": "NAVIGATE_TAB",
            "action_target": "calendar",
        })

    # Check emergency fund below target
    if runway["coverage_pct"] < 60.0:
        attention_cards.append({
            "id": "attn-emergency-fund",
            "type": "EMERGENCY_FUND",
            "level": "warning",
            "title": f"Emergency fund covers {runway['current_runway_months']:g} of {runway['target_months']:g} months",
            "detail": f"Funding gap of ₹{int(runway['funding_gap']):,} to reach {runway['target_months']:g}-month resilience.",
            "action_label": "Fund emergency buffer",
            "action_type": "SIMULATE",
            "action_target": "emergency",
        })

    # Check goal behind target
    for g in goals:
        if g.get("status") == "BEHIND" and g.get("contribution_gap", 0) > 1000:
            attention_cards.append({
                "id": f"attn-goal-{g['id']}",
                "type": "GOAL_BEHIND",
                "level": "warning",
                "title": f"{g['name']} is ₹{int(g['contribution_gap']):,}/month behind schedule",
                "detail": f"Currently contributing ₹{int(g['current_monthly_contribution']):,}/mo. Needs ₹{int(g['required_monthly_contribution']):,}/mo to reach it by {date.fromisoformat(g['target_date'][:10]):%b %Y}.",
                "action_label": "Adjust contribution",
                "action_type": "EDIT_GOAL",
                "action_target": g["id"],
            })

    # Check goal allocation conflict
    if has_goal_conflict:
        attention_cards.append({
            "id": "attn-goal-conflict",
            "type": "GOAL_CONFLICT",
            "level": "warning",
            "title": f"Goal budget exceeds surplus by ₹{int(allocation_gap):,}/month",
            "detail": f"Planned goal allocations total ₹{int(planned_goals):,}, but available surplus is ₹{int(uncommitted_surplus):,}.",
            "action_label": "Rebalance goals",
            "action_type": "NAVIGATE_TAB",
            "action_target": "goals",
        })

    # Active journey integration (e.g. loan application progressing)
    active_journeys = db.query(
        "SELECT * FROM journeys WHERE user_id=? AND status IN ('ON_TRACK', 'ATTENTION')",
        (user_id,)
    )
    for j in active_journeys:
        if j["category"] == "loan":
            attention_cards.append({
                "id": f"attn-journey-{j['id']}",
                "type": "JOURNEY_PROGRESS",
                "level": "info",
                "title": f"Loan journey in progress: {j['title']}",
                "detail": f"{j['subtitle']} · Current stage: {j['stage']}",
                "action_label": "View journey",
                "action_type": "OPEN_JOURNEY",
                "action_target": j["id"],
            })

    # Data Provenance and Confidence metadata
    provenance = {
        "income": {
            "value": profile["monthly_income"],
            "source": profile["income_source"],
            "verified": bool(profile["income_verified"]),
            "confidence": "High" if profile["income_verified"] else "User-entered",
        },
        "bank_balances": {
            "value": liquid_cash,
            "source": f"{len(user_accs)} linked bank accounts (Sandbox/AA live feed)",
            "verified": True,
            "confidence": "Verified",
        },
        "investments": {
            "value": investments_val,
            "source": f"{len(user_sips)} active SIPs (Fund Registrar/Sandbox)",
            "verified": True,
            "confidence": "Verified",
        },
        "liabilities": {
            "value": loans_total,
            "source": "Lender API / active journey registry",
            "verified": len(liabilities) > 0,
            "confidence": "Verified" if len(liabilities) > 0 else "None",
        },
    }

    # 7. Comprehensive Health Score (0-100)
    runway_m = runway["current_runway_months"]
    target_m = runway["target_months"]
    runway_score = min(30, int(round((runway_m / max(1.0, target_m)) * 30)))
    runway_status = "EXCELLENT" if runway_score >= 25 else ("GOOD" if runway_score >= 18 else ("NEEDS_WORK" if runway_score >= 10 else "CRITICAL"))

    dti = cash_flow.get("debt_to_income_pct", 0.0)
    if dti <= 15:
        debt_score = 25
    elif dti <= 30:
        debt_score = 20
    elif dti <= 45:
        debt_score = 12
    else:
        debt_score = 5
    # EMIs can be affordable while debt still outweighs everything owned: cap the score then.
    debt_exceeds_assets = net_worth["total_liabilities"] > net_worth["total_assets"]
    if debt_exceeds_assets:
        debt_score = min(debt_score, 10)
    debt_status = "EXCELLENT" if debt_score >= 22 else ("GOOD" if debt_score >= 18 else ("NEEDS_WORK" if debt_score >= 10 else "CRITICAL"))

    sav_rate = cash_flow.get("savings_rate_pct", 0.0)
    if sav_rate >= 30:
        sav_score = 25
    elif sav_rate >= 20:
        sav_score = 20
    elif sav_rate >= 10:
        sav_score = 14
    else:
        sav_score = 5
    sav_status = "EXCELLENT" if sav_score >= 22 else ("GOOD" if sav_score >= 15 else "NEEDS_WORK")

    has_collision_7d = collisions["windows"].get("7d", {}).get("has_collision", False)
    if has_collision_7d:
        goal_score = 5
    elif has_goal_conflict:
        goal_score = 12
    else:
        goal_score = 20
    goal_status = "EXCELLENT" if goal_score >= 18 else ("GOOD" if goal_score >= 12 else "CRITICAL")

    overall_score = runway_score + debt_score + sav_score + goal_score
    overall_band = "EXCELLENT" if overall_score >= 85 else ("HEALTHY" if overall_score >= 70 else ("MODERATE" if overall_score >= 50 else "VULNERABLE"))

    health_score = {
        "overall": overall_score,
        "band": overall_band,
        "factors": [
            {
                "key": "runway",
                "name": "Emergency Runway",
                "score": runway_score,
                "max_score": 30,
                "status": runway_status,
                "comment": f"{runway_m} months liquid buffer (target: {target_m} mo).",
            },
            {
                "key": "debt",
                "name": "Debt Burden (DTI)",
                "score": debt_score,
                "max_score": 25,
                "status": debt_status,
                "comment": f"EMIs consume {dti:.0f}% of income" + (", but debt exceeds what you own." if debt_exceeds_assets else "."),
            },
            {
                "key": "savings",
                "name": "Savings Rate",
                "score": sav_score,
                "max_score": 25,
                "status": sav_status,
                "comment": f"Saving {sav_rate:.0f}% of monthly income via investments & surplus.",
            },
            {
                "key": "goals",
                "name": "Commitment Buffer",
                "score": goal_score,
                "max_score": 20,
                "status": goal_status,
                "comment": "No imminent cash-flow collisions detected." if not has_collision_7d else "Shortfall imminent in next 7 days.",
            },
        ],
    }

    emergency_fund = {
        "current_liquid": runway["liquid_funds"],
        "monthly_essential": runway["essential_monthly_expenses"],
        "current_runway_months": runway["current_runway_months"],
        "target_runway_months": runway["target_months"],
        "recommended_corpus": runway["target_emergency_fund"],
        "gap": runway["funding_gap"],
        "status": "ADEQUATE" if runway["status"] == "ADEQUATE" else ("DEFICIT" if runway["current_runway_months"] >= 2 else "CRITICAL_DEFICIT"),
        "status_label": f"{runway['current_runway_months']} mo runway" if runway["status"] == "ADEQUATE" else f"{runway['current_runway_months']} mo (Shortfall)",
    }

    inc = max(1.0, profile["monthly_income"])
    needs = cash_flow["fixed_expenses"] + cash_flow["emis"]
    wants = cash_flow["discretionary_expenses"]
    savings_amount = cash_flow["sips"] + max(0.0, cash_flow["estimated_surplus"])

    auto_budget = {
        "needs_pct": round(needs / inc * 100, 1),
        "wants_pct": round(wants / inc * 100, 1),
        "savings_pct": round(savings_amount / inc * 100, 1),
        "rule": "50-30-20 Rule",
        "compliant": (needs / inc <= 0.55) and (savings_amount / inc >= 0.18),
    }

    recommendations = []
    if runway["funding_gap"] > 10000:
        recommendations.append({
            "id": "rec-runway",
            "category": "EMERGENCY BUFFER",
            "urgency": "HIGH" if runway_m < 3 else "MEDIUM",
            "title": f"Reinforce Emergency Fund by ₹{int(runway['funding_gap']):,}",
            "description": f"Your current cash runway is {runway_m} months. Adding ₹{int(runway['funding_gap'] / 6):,}/mo to liquid funds bridges the gap.",
            "impact_summary": f"Increases crisis survival by +{(target_m - runway_m):.1f} months",
            "actionable_journey": "invest",
            "suggested_action": "Allocate to Liquid Fund",
        })

    if sips_total == 0:
        recommendations.append({
            "id": "rec-sips",
            "category": "WEALTH COMPOUNDING",
            "urgency": "HIGH",
            "title": "Start an automated SIP for long-term goals",
            "description": "You currently have 0 active SIPs. Automated monthly investing protects your surplus against inflation.",
            "impact_summary": "Compounds wealth at 12-14% CAGR",
            "actionable_journey": "invest",
            "suggested_action": "Start Largecap SIP",
        })
    elif sav_rate < 20:
        recommendations.append({
            "id": "rec-boost-sip",
            "category": "SAVINGS OPTIMIZATION",
            "urgency": "MEDIUM",
            "title": "Boost monthly SIPs by ₹5,000",
            "description": "Your current savings rate is below the recommended 20% benchmark.",
            "impact_summary": "Reaches retirement target 3 years earlier",
            "actionable_journey": "invest",
            "suggested_action": "Step-up SIP",
        })

    if loans_total > 0:
        recommendations.append({
            "id": "rec-debt",
            "category": "DEBT OPTIMIZATION",
            "urgency": "MEDIUM",
            "title": "Prepay High-Interest Loans with ₹5,000/mo extra",
            "description": f"Outstanding liability of ₹{int(loans_total):,}. Accelerated prepayment cuts total interest.",
            "impact_summary": "Saves up to ₹42,000 in interest charges",
            "actionable_journey": "loan",
            "suggested_action": "Debt Snowball Prepayment",
        })

    active_plan = {
        "version": 1.2,
        "name": "Dynamic Financial Baseline",
        "updated_at": _now_iso(),
    }

    insights = [
        {"tone": "ok" if overall_score >= 70 else "warn", "text": f"Overall Financial Health is {overall_band} ({overall_score}/100)."},
        {"tone": "ok" if runway["status"] == "ADEQUATE" else "warn", "text": f"Current liquid runway is {runway_m} months vs {target_m} target."},
        {"tone": "ok" if auto_budget["compliant"] else "info", "text": f"Cash flow budget: Needs {auto_budget['needs_pct']:.0f}%, Wants {auto_budget['wants_pct']:.0f}%, Savings {auto_budget['savings_pct']:.0f}%."},
    ]

    return {
        "user_id": user_id,
        "net_worth": net_worth,
        "cash_flow": cash_flow,
        "runway": runway,
        "emergency_fund": emergency_fund,
        "health_score": health_score,
        "active_plan": active_plan,
        "auto_budget": auto_budget,
        "recommendations": recommendations,
        "insights": insights,
        "collisions": collisions,
        "pulse": pulse,
        "forecast": forecast,
        "goals": goals,
        "liabilities": liabilities,
        "obligations": obligations,
        "attention_cards": attention_cards,
        "has_goal_conflict": has_goal_conflict,
        "allocation_gap": allocation_gap,
        "provenance": provenance,
        "profile": profile,
    }


# ---------------------------------------------------------------- simulations
# Each wraps a deterministic engine call with the user's live numbers and adds the
# presentation fields the planner UI reads. Engine keys are kept as-is.
STRESS_TYPES = ("INCOME_DROP_10", "INCOME_DROP_20", "INCOME_ZERO",
                "UNEXPECTED_EXPENSE_50K", "UNEXPECTED_EXPENSE_1L", "EMI_HIKE_15")


def obligations_within(cc: Dict[str, Any], days: int) -> float:
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    return sum(o["amount"] for o in cc["obligations"] if o["due"][:10] <= cutoff)


def _active_goals(cc: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [g for g in cc["goals"] if g["lifecycle_status"] == "ACTIVE"]


def affordability(user_id: str, amount: float, is_recurring: bool = False, frequency: str = "one_time",
                  cc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cc = cc or build_command_center(user_id)
    frequency = (frequency if frequency in ("monthly", "yearly") else "monthly") if is_recurring else "one_time"
    surplus = cc["cash_flow"]["estimated_surplus"]
    sim = engine.simulate_affordability(
        purchase_amount=amount,
        is_recurring=is_recurring,
        frequency=frequency,
        current_liquid=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
        monthly_income=cc["profile"]["monthly_income"],
        monthly_surplus=surplus,
        essential_monthly_expenses=cc["profile"]["essential_expenses"] + cc["cash_flow"]["emis"],
        active_goals=_active_goals(cc),
        upcoming_7d_obligations=obligations_within(cc, 7),
    )
    tone = {"AFFORDABLE": "SAFE", "CAUTION": "CAUTION"}.get(sim["verdict"], "HIGH_RISK")
    label = {"SAFE": "Affordable", "CAUTION": "Affordable with caution", "HIGH_RISK": "High risk right now"}[tone]
    delayed = [{"goal_name": g["goal_name"], "delay_months": g["projected_delay_months"]}
               for g in sim["goal_impacts"] if g["projected_delay_months"] > 0]

    recs = list(sim["warnings"])
    if tone == "SAFE":
        recs.append(f"Runway stays at {sim['runway_after_months']} months after this purchase.")
    elif not is_recurring and surplus > 0:
        months = math.ceil(amount / surplus)
        recs.append(f"Saving your ₹{int(surplus):,}/mo surplus for {months} month{'s' if months != 1 else ''} "
                    "would fund this without touching your buffer.")
    trade_offs = [f"Delays {d['goal_name']} by ~{d['delay_months']} mo" for d in delayed]
    if sim["surplus_after"] < 0:
        trade_offs.append(f"Monthly deficit of ₹{abs(int(sim['surplus_after'])):,}")

    return {
        **sim,
        "frequency": frequency,
        "can_afford": tone != "HIGH_RISK",
        "verdict_tone": tone,
        "verdict_label": label,
        "impact_on_runway": {
            "runway_before_months": sim["runway_before_months"],
            "runway_after_months": sim["runway_after_months"],
            "is_safe": sim["runway_after_months"] >= 3.0,
        },
        "impact_on_goals": {"affected_goals": delayed},
        "recommendations": recs,
        "trade_offs": trade_offs,
    }


def _savings_rate(income: float, sips_amt: float, surplus: float) -> float:
    return round((sips_amt + max(0.0, surplus)) / income * 100, 1) if income > 0 else 0.0


def what_if(user_id: str, income_delta_pct: float = 0.0, sip_delta_abs: float = 0.0,
            expense_delta_abs: float = 0.0, one_time_expense: float = 0.0,
            cc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cc = cc or build_command_center(user_id)
    cf = cc["cash_flow"]
    active = _active_goals(cc)
    sim = engine.simulate_what_if(
        base_income=cf["monthly_income"],
        base_fixed_expenses=cf["fixed_expenses"],
        base_emis=cf["emis"],
        base_sips=cf["sips"],
        base_liquid=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
        active_goals=active,
        income_delta_pct=income_delta_pct,
        sip_delta_abs=sip_delta_abs,
        expense_delta_abs=expense_delta_abs,
        one_time_expense=one_time_expense,
        # Same surplus definition as the overview: discretionary, insurance and goal savings also come out.
        base_other_outflow=cf["discretionary_expenses"] + cf["insurance_monthly"] + cf["planned_goal_contributions"],
    )
    base, new = sim["base"], sim["simulated"]
    base_rate = _savings_rate(base["income"], base["sips"], base["surplus"])
    new_rate = _savings_rate(new["income"], new["sips"], new["surplus"])
    new["expenses"] = max(0.0, cf["fixed_expenses"] + expense_delta_abs) + cf["discretionary_expenses"]
    new["obligations"] = new["expenses"] + cf["emis"] + new["sips"] + cf["insurance_monthly"]
    new["savings_rate_pct"] = new_rate

    today = date.today()
    by_id = {g["id"]: g for g in active}
    impacts = []
    for gs in sim["goals"]:
        g = by_id.get(gs["goal_id"], {})
        delta = gs["months_saved"] or 0.0
        impacts.append({
            "goal_id": gs["goal_id"],
            "goal_name": gs["name"],
            "target_amount": g.get("target_amount"),
            "months_remaining": gs["new_months"],
            "current_target_date": g.get("target_date"),
            "new_projected_date": (today + timedelta(days=int(gs["new_months"] * 30.4375))).isoformat()
            if gs["new_months"] else None,
            "delta_months": abs(delta),
            "status": "ACCELERATED" if delta > 0 else ("DELAYED" if delta < 0 else "UNCHANGED"),
        })

    return {
        **sim,
        "current": {"surplus": base["surplus"], "runway_months": base["runway_months"], "savings_rate_pct": base_rate},
        "delta": {
            "surplus_change": sim["deltas"]["surplus_change"],
            "runway_change": sim["deltas"]["runway_change_months"],
            "savings_rate_change": round(new_rate - base_rate, 1),
        },
        "goal_impacts": impacts,
    }


def stress_test(user_id: str, stress_type: str, cc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cc = cc or build_command_center(user_id)
    cf = cc["cash_flow"]
    res = engine.run_stress_test(
        stress_type=stress_type,
        monthly_income=cf["monthly_income"],
        fixed_expenses=cf["fixed_expenses"],
        emis=cf["emis"],
        sips=cf["sips"],
        liquid_funds=cc["net_worth"]["asset_breakdown"]["liquid_cash"],
        active_goals=_active_goals(cc),
    )

    # Recovery playbook: concrete levers, largest monthly saving first.
    deficit = max(0.0, -res["surplus_deficit"])
    levers = []
    if deficit > 0 and cf["sips"] > 0:
        levers.append(("Pause SIPs until income stabilises", cf["sips"]))
    if deficit > 0 and cf["discretionary_expenses"] > 0:
        levers.append(("Cut discretionary spending by half", round(cf["discretionary_expenses"] / 2, 0)))
    if deficit > 0 and cf["planned_goal_contributions"] > 0:
        levers.append(("Pause goal contributions temporarily", cf["planned_goal_contributions"]))
    levers.sort(key=lambda x: -x[1])

    playbook, covered = [], 0.0
    for action, saving in levers:
        playbook.append({"action": action, "savings_potential": saving,
                         "priority": "HIGH" if covered < deficit else "MEDIUM"})
        covered += saving
    if deficit > 0:
        playbook.append({"action": f"Bridge any remaining gap from your emergency fund "
                                   f"({res['survival_runway_months']:g} months of essentials)",
                         "savings_potential": 0.0, "priority": "HIGH" if covered < deficit else "LOW"})
    else:
        playbook.append({"action": res["recommendations"][0], "savings_potential": 0.0, "priority": "LOW"})
    if res["recovery_months"]:
        playbook.append({"action": f"Rebuild the emergency buffer from surplus in ~{res['recovery_months']:g} months",
                         "savings_potential": 0.0, "priority": "MEDIUM"})
    for i, p in enumerate(playbook, 1):
        p["step"] = i

    return {
        **res,
        "stress_name": res["title"],
        "test_income": res["tested_income"],
        "test_expenses": res["tested_essential_outflow"],
        "test_liquid": res["tested_liquid_funds"],
        "recovery_playbook": playbook,
    }


def debt_payoff(user_id: str, extra_monthly_payment: float, liability_id: Optional[str] = None,
                outstanding_balance: Optional[float] = None, current_emi: Optional[float] = None,
                annual_interest_rate_pct: Optional[float] = None) -> Dict[str, Any]:
    loans = [l for l in list_liabilities(user_id) if l.get("kind") != "insurance"]
    if liability_id:
        lib = next((l for l in loans if l["id"] == liability_id), None)
    else:
        lib = max(loans, key=lambda l: l.get("outstanding_amount") or 0.0, default=None)

    # With no loan on record the simulator runs on a sample loan, and says so.
    illustrative = lib is None and outstanding_balance is None
    lib = lib or {}
    balance = outstanding_balance if outstanding_balance is not None else (lib.get("outstanding_amount") or 350000.0)
    emi = current_emi if current_emi is not None else (lib.get("emi_amount") or 12000.0)
    rate = annual_interest_rate_pct if annual_interest_rate_pct is not None else (lib.get("interest_rate") or 12.0)

    res = engine.simulate_debt_extra_payment(
        outstanding_balance=balance,
        current_emi=emi,
        annual_interest_rate_pct=rate,
        extra_monthly_payment=extra_monthly_payment,
    )
    return {
        **res,
        "liability_id": lib.get("id"),
        "liability_name": lib.get("name") or ("Sample personal loan" if illustrative else "Loan"),
        "is_illustrative": illustrative,
        "baseline": {
            "total_interest": res["base_total_interest"],
            "payoff_months": res["base_months_remaining"],
            "payoff_years": round(res["base_months_remaining"] / 12, 1),
        },
        "with_extra": {
            "total_interest": res["accelerated_total_interest"],
            "payoff_months": res["accelerated_months_remaining"],
            "payoff_years": round(res["accelerated_months_remaining"] / 12, 1),
        },
        "savings": {
            "interest_saved": res["interest_saved"],
            "time_saved_months": res["months_saved"],
            "time_saved_years": round(res["months_saved"] / 12, 1),
        },
    }
