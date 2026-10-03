"""Saarthi knowledge base.

Two kinds of knowledge live here:
  * failure_code entries - structured partner-code mappings (the backbone of the
    Failure Knowledge Graph and the partner normalization layer). Every sandbox
    bank speaks its own code dialect; all of them map onto a handful of standard
    failures.
  * policy / rule / requirement entries - free-text knowledge retrieved with BM25
    to ground diagnoses, decisions and explanations.

This is reference knowledge (what a code *means*), not user data. Nothing here
says that any particular user has a problem.
"""

FAILURE_TYPES = {
    "PAYMENT_FAILURE": {
        "standard_code": "PAY.INSUFFICIENT_FUNDS",
        "meaning": "Insufficient balance in the autopay account",
        "root_cause": "Available balance < installment amount",
        "evidence_required": ["mandate_account_balance", "installment_amount", "mandate_status"],
        "retry_allowed": True,
        "recovery_actions": ["retry_debit", "fund_and_retry", "remind_before_window"],
        "action_tier": "TIER_2",
        "expected_outcome": "Installment debited and units allotted",
        "body": "returned when an autopay (NACH / e-mandate) debit is presented but the available balance in the "
                "mandate account is lower than the installment. The mandate stays active and the debit can be "
                "re-presented within the SIP cycle.",
    },
    "MANDATE_LIMIT": {
        "standard_code": "MANDATE.AMOUNT_EXCEEDED",
        "meaning": "Installment is above the autopay limit",
        "root_cause": "SIP amount > mandate maximum amount",
        "evidence_required": ["installment_amount", "mandate_limit", "mandate_status", "mandate_account_balance"],
        "retry_allowed": True,
        "recovery_actions": ["raise_mandate_limit_and_retry", "reduce_sip_to_limit"],
        "action_tier": "TIER_2",
        "expected_outcome": "Mandate limit raised, installment debited",
        "body": "returned when the debit amount presented is higher than the maximum amount the customer "
                "authorised on the mandate. Funds are irrelevant: the bank refuses before checking balance. "
                "A mandate amendment with a higher limit is required.",
    },
    "ACCOUNT_VERIFICATION": {
        "standard_code": "BAV.NAME_MISMATCH",
        "meaning": "Bank account name doesn't match PAN",
        "root_cause": "Account holder name on bank record differs from the investor's PAN name",
        "evidence_required": ["pan_name", "bank_record_name", "name_similarity"],
        "retry_allowed": False,
        "recovery_actions": ["verify_ownership_via_aa", "escalate_to_specialist"],
        "action_tier": "TIER_2",
        "expected_outcome": "Account ownership proven, account verified for autopay",
        "body": "returned by bank account verification (penny drop) when the beneficiary name on the bank's record "
                "does not match the name the investor registered with. It can be a formatting difference (initials, "
                "missing middle name, order) or an account that belongs to someone else.",
    },
}

# bank -> (failure type -> partner code)
BANK_CODES = {
    "axis": {"PAYMENT_FAILURE": "AUTOPAY_DEBIT_FAILED_07", "MANDATE_LIMIT": "AUTOPAY_DEBIT_FAILED_12",
             "ACCOUNT_VERIFICATION": "PD_NAME_MISMATCH_04"},
    "icici": {"PAYMENT_FAILURE": "ECS_BOUNCE_R03", "MANDATE_LIMIT": "ECS_BOUNCE_R09",
              "ACCOUNT_VERIFICATION": "IMPS_BENE_NAME_MM"},
    "hdfc": {"PAYMENT_FAILURE": "ACH_DR_RTN_01", "MANDATE_LIMIT": "ACH_DR_RTN_AMT",
             "ACCOUNT_VERIFICATION": "BAV_NM_02"},
    "sbi": {"PAYMENT_FAILURE": "NACH_RTN_51", "MANDATE_LIMIT": "NACH_RTN_54",
            "ACCOUNT_VERIFICATION": "PENNYDROP_NAME_NOMATCH"},
}

BANK_NAMES = {"axis": "Axis Bank", "icici": "ICICI Bank", "hdfc": "HDFC Bank", "sbi": "SBI"}


def _failure_codes() -> list[dict]:
    out = []
    for bank, codes in BANK_CODES.items():
        for ftype, code in codes.items():
            ft = FAILURE_TYPES[ftype]
            out.append({
                "id": f"kb-{bank}-{code.lower()}",
                "partner_id": bank,
                "code": code,
                "title": f"{BANK_NAMES[bank]} {code} - {ft['meaning'].lower()}",
                "body": f"{BANK_NAMES[bank]} {code} is {ft['body']}",
                "data": {"failure_type": ftype, **{k: v for k, v in ft.items() if k != "body"}},
            })
    return out


FAILURE_CODES = _failure_codes()

POLICIES = [
    {
        "id": "pol-money-movement",
        "kind": "action_constraint",
        "title": "Money movement always requires explicit user authorization",
        "body": "Any transfer of funds, payment, or re-presentation of a debit that moves user money requires "
                "explicit user approval, even if the transfer is between the user's own accounts and reversible. "
                "Minimum tier: TIER_2. Saarthi never moves money autonomously.",
    },
    {
        "id": "pol-tier1-readonly",
        "kind": "action_constraint",
        "title": "Tier 1 auto actions are read-only or reversible with no financial impact",
        "body": "Saarthi may automatically refresh partner status, schedule reminders and re-check balances. These "
                "actions are reversible, have zero financial impact and do not share new user data.",
    },
    {
        "id": "pol-sip-retry",
        "kind": "journey_policy",
        "title": "SIP installment re-presentation window",
        "body": "SIP debits that fail for insufficient funds can be re-presented within the same SIP cycle "
                "(T+3 days, at most 2 re-presentations). A single missed installment does not cancel the SIP, but "
                "three consecutive misses cancel it.",
    },
    {
        "id": "pol-own-account-transfer",
        "kind": "recovery_policy",
        "title": "Funding a mandate account from the user's own verified account",
        "body": "When a mandate account has a shortfall, the preferred recovery is an IMPS transfer of the exact "
                "shortfall from another verified account of the same user, followed by re-presentation of the "
                "debit. The source account must keep at least a Rs 1,000 safety buffer after the transfer.",
    },
    {
        "id": "pol-mandate-limit",
        "kind": "recovery_policy",
        "title": "Raising an autopay mandate limit",
        "body": "If a SIP step-up makes the installment larger than the mandate maximum, the bank rejects every "
                "debit. The fix is a mandate amendment to a higher maximum, which authorises larger future debits "
                "and therefore needs explicit user approval (TIER_2). After amendment the debit can be re-presented.",
    },
    {
        "id": "pol-account-aggregator",
        "kind": "recovery_policy",
        "title": "Account Aggregator ownership check requires consent",
        "body": "Fetching the account-holder profile through the Account Aggregator network shares financial data "
                "and therefore requires an explicit consent artefact approved by the user (TIER_2). The bank (FIP) "
                "returns the PAN linked to the account, which proves ownership even if the name is formatted "
                "differently.",
    },
    {
        "id": "req-name-match",
        "kind": "document_requirement",
        "title": "Bank account name match rule for mutual fund investments",
        "body": "The bank account used for SIP autopay must belong to the investor. A name-match score of 0.85 or "
                "above passes automatically. Common benign differences are initials, a missing middle name and "
                "word order. Below that, ownership must be proven, for example by the PAN linked at the bank.",
    },
    {
        "id": "pol-third-party",
        "kind": "action_constraint",
        "title": "Third-party payments are not permitted for mutual funds",
        "body": "SEBI rules prohibit paying for mutual fund investments from a bank account that does not belong to "
                "the investor. If the bank-record name is substantially different from the PAN name, Saarthi must "
                "not attempt automated fixes: it escalates to a human specialist (TIER_3) and the account stays "
                "blocked for autopay.",
    },
    {
        "id": "pol-escalation-pack",
        "kind": "journey_policy",
        "title": "Escalation case must carry full journey context",
        "body": "When Saarthi escalates, the support case must include what Saarthi checked, evidence collected, "
                "partner responses, the reason automation stopped and the recommended next action, so the human "
                "agent does not restart the investigation.",
    },
    {
        "id": "pol-confidence",
        "kind": "action_constraint",
        "title": "Minimum diagnosis confidence for automated recovery",
        "body": "Recovery actions may only be proposed for approval when diagnosis confidence is at least 0.75 and "
                "all evidence required by the partner rule was verified. Otherwise escalate.",
    },
]
