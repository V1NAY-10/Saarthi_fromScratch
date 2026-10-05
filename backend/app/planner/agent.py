"""AI Financial Planner Agent.

Uses Gemini (via app.agents.llm) to provide conversational intelligence over
structured planner data.

Guarantees:
- The LLM NEVER invents balances, transactions, investments, or arithmetic.
- All numbers come from deterministic calculations in service.py and engine.py.
- If LLM is unavailable or fails, returns structured deterministic answers.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app import config
from app.agents import llm
from app.planner import service
from app.services.fmt import inr

PLANNER_SYSTEM_PROMPT = """You are Saarthi's AI Financial Planner Agent.
You assist the user by answering questions about their financial situation, goals, cash flow, upcoming obligations, and simulations.

CRITICAL RULES:
1. NEVER invent or hallucinate financial numbers, balances, or transaction dates.
2. Rely strictly on the structured data provided in the context or returned by tools.
3. If an input is missing (e.g. for a new goal target amount or date), ask the user clearly for it.
4. Always distinguish verified facts (from bank accounts or salary slips) from estimates or assumptions.
5. Highlight any financial risks (cash-flow collisions, underfunded emergency runway, goal shortfall) proactively.
6. Format currency in Indian Rupees (INR) e.g., ₹50,000, ₹1.5L.
7. Be concise, direct, helpful, and transparent.
"""


def _get_context_summary(user_id: str) -> Dict[str, Any]:
    cc = service.build_command_center(user_id)
    p = cc["profile"]
    cf = cc["cash_flow"]
    nw = cc["net_worth"]
    rw = cc["runway"]
    col = cc["collisions"]

    return {
        "monthly_income": p["monthly_income"],
        "income_source": p["income_source"],
        "income_verified": bool(p["income_verified"]),
        "net_worth": nw["net_worth"],
        "liquid_cash": nw["asset_breakdown"]["liquid_cash"],
        "investments_value": nw["asset_breakdown"]["investments"],
        "liabilities_total": nw["total_liabilities"],
        "monthly_surplus": cf["estimated_surplus"],
        "committed_outflow": cf["committed_outflow"],
        "fixed_expenses": cf["fixed_expenses"],
        "sips_monthly": cf["sips"],
        "emis_monthly": cf["emis"],
        "runway_months": rw["current_runway_months"],
        "target_runway_months": rw["target_months"],
        "emergency_fund_gap": rw["funding_gap"],
        "has_7d_collision": col["windows"]["7d"]["has_collision"],
        "collision_7d_shortfall": col["windows"]["7d"]["shortfall"],
        "goals_count": len(cc["goals"]),
        "goals": [{
            "id": g["id"],
            "name": g["name"],
            "target": g["target_amount"],
            "current": g["current_amount"],
            "target_date": g["target_date"],
            "monthly_contrib": g["monthly_contribution"],
            "required_contrib": g["required_monthly_contribution"],
            "gap": g["contribution_gap"],
            "status": g["status"],
            "progress_pct": g["progress_pct"],
        } for g in cc["goals"]],
        "safe_to_spend_per_day": cc["pulse"]["per_day"],
        "safe_to_spend_until_payday": cc["pulse"]["total_until_payday"],
        "next_payday": cc["pulse"]["next_payday"],
        "committed_before_payday": cc["pulse"]["committed_before_payday"],
        "forecast_lowest_balance": cc["forecast"]["lowest"],
        "upcoming_obligations_count": len(cc["obligations"]),
        "upcoming_sample": [{
            "title": o["title"],
            "amount": o["amount"],
            "due": o["due"][:10],
            "kind": o["kind"],
        } for o in cc["obligations"][:5]],
    }


_AMOUNT_RE = re.compile(r"(₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?|l|crores?|cr)?\b")
_UNITS = {"k": 1e3, "thousand": 1e3, "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
          "cr": 1e7, "crore": 1e7, "crores": 1e7}


def _purchase_amount(text: str) -> Optional[float]:
    """The rupee amount in a purchase question. Prefers numbers marked with ₹/Rs or a unit
    ("1.5L", "75k") so model numbers like "iPhone 15" aren't read as prices."""
    best, best_marked = None, False
    for m in _AMOUNT_RE.finditer(text):
        try:
            value = float(m.group(2).replace(",", "")) * _UNITS.get(m.group(3) or "", 1.0)
        except ValueError:
            continue
        marked = bool(m.group(1) or m.group(3))
        if (marked, value) > (best_marked, best or 0.0):
            best, best_marked = value, marked
    return best if best and best >= 100 else None


def ask_planner(user_id: str, message: str) -> Dict[str, Any]:
    ctx = _get_context_summary(user_id)
    text = message.strip().lower()

    # Purchase questions get a deterministic affordability simulation first
    sim_result = None
    if re.search(r"\b(afford|buy|purchase|spend)\b", text):
        amount = _purchase_amount(text)
        if amount:
            sim_result = service.affordability(user_id, amount)

    # If Gemini is enabled, generate rich conversational reasoning
    if config.llm_enabled():
        try:
            sim_block = ""
            if sim_result:
                sim_block = "DETERMINISTIC SIMULATION RESULT FOR THIS PURCHASE:\n" + json.dumps(sim_result, indent=2)

            prompt = f"""User message: {message}

CURRENT FINANCIAL DATA (Verified / Deterministic):
{json.dumps(ctx, indent=2)}

{sim_block}

Answer the user directly and helpfully.
Explain the exact impact using the numbers provided above.
If they asked about affordability, state the verdict (Affordable, Caution, or High Risk) and explain the runway, goal delay, and cash buffer impacts.
If they asked why a goal is behind, explain the required monthly contribution vs current contribution gap.
"""
            reply = llm.complete(system=PLANNER_SYSTEM_PROMPT, user=prompt, max_tokens=1000)
            if reply:
                return {
                    "reply": reply,
                    "simulation": sim_result,
                    "context": ctx,
                    "agent_mode": "gemini",
                }
        except Exception:
            # Fall back to deterministic reply below
            pass

    # Deterministic fallback response builder
    if sim_result:
        verdict = sim_result["verdict"]
        pur = int(sim_result["purchase_amount"])
        liq_after = int(sim_result["liquid_after"])
        rw_after = sim_result["runway_after_months"]

        if verdict == "HIGH_RISK":
            reason = sim_result["warnings"][0] if sim_result["warnings"] else "It would strain your liquid funds."
            reply = f"A ₹{pur:,} purchase is high risk right now. {reason} It would leave ₹{liq_after:,} in liquid funds."
        elif verdict == "CAUTION":
            reply = f"You could afford ₹{pur:,}, but with caution. Your remaining liquid buffer would be ₹{liq_after:,}, reducing your emergency runway to {rw_after} months."
        else:
            reply = f"Yes, you can afford a ₹{pur:,} purchase. It leaves ₹{liq_after:,} in liquid bank balance and maintains a healthy emergency runway of {rw_after} months."

        if sim_result["goal_impacts"]:
            delays = [f"{g['goal_name']} (+{g['projected_delay_months']} mo)" for g in sim_result["goal_impacts"] if g["projected_delay_months"] > 0]
            if delays:
                reply += f" Note: This may shift your active goals: {', '.join(delays)}."
    elif "safe" in text or ("spend" in text and ("today" in text or "how much" in text)):
        reply = (f"You can safely spend about ₹{int(ctx['safe_to_spend_per_day']):,}/day "
                 f"(₹{int(ctx['safe_to_spend_until_payday']):,} in total) until your next salary on {ctx['next_payday']}. "
                 f"That already sets aside ₹{int(ctx['committed_before_payday']):,} of SIPs, EMIs and premiums due before payday, "
                 "your essential costs and a one-week safety buffer.")
    elif "runway" in text or "emergency" in text:
        reply = f"Your liquid funds (₹{int(ctx['liquid_cash']):,}) provide approximately {ctx['runway_months']} months of emergency runway against essential expenses (₹{int(ctx['fixed_expenses'] + ctx['emis_monthly']):,}/mo). Your target is {ctx['target_runway_months']} months."
    elif "collision" in text or "shortfall" in text or "conflict" in text:
        if ctx["has_7d_collision"]:
            reply = f"Alert: You have a projected ₹{int(ctx['collision_7d_shortfall']):,} cash-flow collision over the next 7 days because upcoming obligations exceed your current bank balance."
        else:
            reply = "You have no immediate cash-flow collisions detected in the next 7 days. Your upcoming obligations are covered by your liquid balance."
    elif "goal" in text:
        behind_goals = [g for g in ctx["goals"] if g["gap"] > 0]
        if behind_goals:
            g = behind_goals[0]
            reply = f"Your goal '{g['name']}' has a contribution gap of ₹{int(g['gap']):,}/month. You are saving ₹{int(g['monthly_contrib']):,}/mo, but need ₹{int(g['required_contrib']):,}/mo to meet your {g['target_date']} target."
        else:
            reply = f"You have {ctx['goals_count']} active goals, and all are currently on track based on your planned monthly contributions."
    elif "saving" in text or "surplus" in text or "income" in text:
        reply = f"Your monthly income is ₹{int(ctx['monthly_income']):,} ({ctx['income_source']}). After committed outflows of ₹{int(ctx['committed_outflow']):,} (SIPs ₹{int(ctx['sips_monthly']):,}, EMIs ₹{int(ctx['emis_monthly']):,}), your estimated surplus is ₹{int(ctx['monthly_surplus']):,}/month."
    elif "upcoming" in text or "payment" in text or "due" in text or "calendar" in text:
        if ctx["upcoming_sample"]:
            sample_str = ", ".join([f"{o['title']} (₹{int(o['amount']):,} on {o['due']})" for o in ctx["upcoming_sample"][:3]])
            n = ctx["upcoming_obligations_count"]
            reply = f"You have {n} upcoming commitment{'s' if n != 1 else ''}. Nearest: {sample_str}."
        else:
            reply = "You have no upcoming SIPs, EMIs or premiums scheduled right now."
    else:
        reply = f"Your financial snapshot: Net worth is ₹{int(ctx['net_worth']):,} with ₹{int(ctx['liquid_cash']):,} in liquid bank balances and ₹{int(ctx['investments_value']):,} invested. Monthly surplus is ₹{int(ctx['monthly_surplus']):,}. How can I help optimize your plan?"

    return {
        "reply": reply,
        "simulation": sim_result,
        "context": ctx,
        "agent_mode": "deterministic",
    }
