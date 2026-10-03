"""Action catalog: the safety-relevant properties of every action Saarthi can
take. The decision engine reasons over these properties - not over prose, and
not over anything the LLM says."""

ACTIONS = {
    "fund_and_retry": {
        "label": "Top up the autopay account from your own account & retry",
        "moves_money": True, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
    "retry_debit": {
        "label": "Re-present the debit now",
        "moves_money": True, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
    "remind_before_window": {
        "label": "Watch the balance & remind before the retry window closes",
        "moves_money": False, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
    "raise_mandate_limit_and_retry": {
        "label": "Raise the autopay limit & retry",
        "moves_money": True, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": True,
    },
    "reduce_sip_to_limit": {
        "label": "Bring the SIP back within the autopay limit & retry",
        "moves_money": True, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": True,
    },
    "verify_ownership_via_aa": {
        "label": "Prove account ownership via Account Aggregator",
        "moves_money": False, "shares_data": True, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
    "escalate_to_specialist": {
        "label": "Hand over to a human specialist",
        "moves_money": False, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
    "submit_existing_document": {
        "label": "Submit a matching document from your vault",
        "moves_money": False, "shares_data": True, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
    "request_document_upload": {
        "label": "Ask you for a document that meets the rule",
        "moves_money": False, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False, "needs_customer": True,
    },
    "retry_with_partner": {
        "label": "Retry the same request with the partner",
        "moves_money": False, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False, "partner_call": True,
    },
    "refresh_status": {
        "label": "Re-check status with the partner",
        "moves_money": False, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False, "partner_call": True,
    },
    "create_new_mandate": {
        "label": "Register a new autopay mandate & retry",
        "moves_money": True, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": True,
    },
    "switch_partner_account": {
        "label": "Use a different verified account",
        "moves_money": False, "shares_data": True, "reversible": True, "changes_identity": False,
        "changes_terms": True,
    },
    "retry_payment": {
        "label": "Retry the payment",
        "moves_money": True, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
    "fund_and_retry_payment": {
        "label": "Top up from your own account & pay",
        "moves_money": True, "shares_data": False, "reversible": True, "changes_identity": False,
        "changes_terms": False,
    },
}
