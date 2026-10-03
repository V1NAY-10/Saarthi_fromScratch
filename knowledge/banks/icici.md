# ICICI Bank (sandbox): error codes

> **Synthetic sandbox knowledge.** Every partner, error code, rule and procedure in this file is invented for the Saarthi sandbox. None of it describes the real policies, codes or systems of any bank, lender, insurer or registry.

Partner id `icici`. Wire dialect: `nach` (flat NPCI-style fields: txnStatus, respCode, respMsg).

## ECS_BOUNCE_R03: Insufficient balance in the paying account

ICICI Bank returns `ECS_BOUNCE_R03` in sip autopay and account verification journeys. The debit was returned because the account did not hold enough funds. The mandate stays active and the debit may be re-presented within the cycle (at most 3 re-presentations). Moving money between the customer's own verified accounts needs explicit approval.

- **What it means for the customer:** Insufficient balance in the paying account.
- **Likely causes:** Available balance lower than the debit amount at presentment.
- **Resolution:** retry debit, fund and retry, remind before window.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Re-presentation limit reached; No verified account can cover the shortfall for 3 days.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: ECS_BOUNCE_R03
failure_type: PAYMENT_FAILURE
analyzer: insufficient_funds
standard_code: PAY.INSUFFICIENT_FUNDS
customer_meaning: Insufficient balance in the paying account
possible_causes:
- Available balance lower than the debit amount at presentment
evidence_required:
- mandate_account_balance
- installment_amount
- mandate_status
resolution_options:
- retry_debit
- fund_and_retry
- remind_before_window
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: true
escalation_conditions:
- Re-presentation limit reached
- No verified account can cover the shortfall for 3 days
expected_outcome: Installment debited and units allotted
retry_allowed: true
action_tier: TIER_2
relevant_documents: []
```

## ECS_BOUNCE_R09: Debit amount is above the autopay limit

ICICI Bank returns `ECS_BOUNCE_R09` in sip autopay and account verification journeys. The bank refuses any debit above the maximum amount authorised on the mandate, before it checks the balance. Raising the limit authorises larger future debits and therefore needs the customer's approval.

- **What it means for the customer:** Debit amount is above the autopay limit.
- **Likely causes:** SIP stepped up above the mandate maximum; Mandate registered with a low maximum.
- **Resolution:** raise mandate limit and retry, reduce sip to limit.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Bank refuses mandate amendment.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: ECS_BOUNCE_R09
failure_type: MANDATE_LIMIT
analyzer: mandate_limit
standard_code: MANDATE.AMOUNT_EXCEEDED
customer_meaning: Debit amount is above the autopay limit
possible_causes:
- SIP stepped up above the mandate maximum
- Mandate registered with a low maximum
evidence_required:
- installment_amount
- mandate_limit
- mandate_status
- mandate_account_balance
resolution_options:
- raise_mandate_limit_and_retry
- reduce_sip_to_limit
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: true
escalation_conditions:
- Bank refuses mandate amendment
expected_outcome: Mandate limit raised and installment debited
retry_allowed: true
action_tier: TIER_2
relevant_documents: []
```

## IMPS_BENE_NAME_MM: Bank account name doesn't match PAN

ICICI Bank returns `IMPS_BENE_NAME_MM` in sip autopay and account verification journeys. A name-match score of 0.85 or above passes. Below that, ownership must be proven, for example via the PAN linked at the bank through an Account Aggregator consent. Third-party accounts may not be used for mutual fund payments.

- **What it means for the customer:** Bank account name doesn't match PAN.
- **Likely causes:** Initials or missing middle name at the bank; Account belongs to someone else.
- **Resolution:** verify ownership via aa, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Name similarity below 0.5; Account Aggregator returns a different PAN.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: IMPS_BENE_NAME_MM
failure_type: ACCOUNT_VERIFICATION
analyzer: name_mismatch
standard_code: BAV.NAME_MISMATCH
customer_meaning: Bank account name doesn't match PAN
possible_causes:
- Initials or missing middle name at the bank
- Account belongs to someone else
evidence_required:
- pan_name
- bank_record_name
- name_similarity
resolution_options:
- verify_ownership_via_aa
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: high
reversible: true
escalation_conditions:
- Name similarity below 0.5
- Account Aggregator returns a different PAN
expected_outcome: Account ownership proven, account verified for autopay
retry_allowed: false
action_tier: TIER_2
relevant_documents: []
```

## ECS_MANDATE_R14: The autopay mandate has expired

ICICI Bank returns `ECS_MANDATE_R14` in sip autopay and account verification journeys. An expired mandate cannot be used for any further debits. A new mandate must be registered, which creates a new standing authorisation and needs the customer's approval.

- **What it means for the customer:** The autopay mandate has expired.
- **Likely causes:** Mandate end date passed.
- **Resolution:** create new mandate.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** New mandate registration rejected.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: ECS_MANDATE_R14
failure_type: MANDATE_EXPIRED
analyzer: mandate_invalid
standard_code: MANDATE.EXPIRED
customer_meaning: The autopay mandate has expired
possible_causes:
- Mandate end date passed
evidence_required:
- mandate_status
- installment_amount
- mandate_account_balance
resolution_options:
- create_new_mandate
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: true
escalation_conditions:
- New mandate registration rejected
expected_outcome: New mandate registered and installment debited
retry_allowed: false
action_tier: TIER_2
relevant_documents: []
```

## ECS_MANDATE_R15: The autopay mandate was cancelled

ICICI Bank returns `ECS_MANDATE_R15` in sip autopay and account verification journeys. A cancelled mandate cannot be revived. Saarthi may propose a new mandate, but only the customer can approve creating it.

- **What it means for the customer:** The autopay mandate was cancelled.
- **Likely causes:** Customer or bank cancelled the mandate.
- **Resolution:** create new mandate.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Customer did not intend to keep the SIP.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: ECS_MANDATE_R15
failure_type: MANDATE_CANCELLED
analyzer: mandate_invalid
standard_code: MANDATE.CANCELLED
customer_meaning: The autopay mandate was cancelled
possible_causes:
- Customer or bank cancelled the mandate
evidence_required:
- mandate_status
- installment_amount
- mandate_account_balance
resolution_options:
- create_new_mandate
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: true
escalation_conditions:
- Customer did not intend to keep the SIP
expected_outcome: New mandate registered and installment debited
retry_allowed: false
action_tier: TIER_2
relevant_documents: []
```

## IC_CORE_UNAVAILABLE: The bank's systems were temporarily down

ICICI Bank returns `IC_CORE_UNAVAILABLE` in sip autopay and account verification journeys. During an outage nothing is debited. Retrying after recovery is safe and automatic.

- **What it means for the customer:** The bank's systems were temporarily down.
- **Likely causes:** Unplanned bank outage.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Outage continues after 2 automatic retries.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: IC_CORE_UNAVAILABLE
failure_type: BANK_OUTAGE
analyzer: transient
standard_code: PARTNER.OUTAGE
customer_meaning: The bank's systems were temporarily down
possible_causes:
- Unplanned bank outage
evidence_required:
- partner_status
- retry_history
resolution_options:
- retry_with_partner
automatic_action_allowed: true
approval_required: false
risk_level: low
reversible: true
escalation_conditions:
- Outage continues after 2 automatic retries
expected_outcome: Request processed once the bank recovers
retry_allowed: true
action_tier: TIER_1
relevant_documents: []
```

## ECS_SPONSOR_UNAVBL: The mandate service was temporarily unavailable

ICICI Bank returns `ECS_SPONSOR_UNAVBL` in sip autopay and account verification journeys. Temporary unavailability is safe to retry automatically: no money moves until the bank accepts the presentment, and duplicate presentments are rejected by the bank.

- **What it means for the customer:** The mandate service was temporarily unavailable.
- **Likely causes:** Mandate registry maintenance window.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Still unavailable after 2 automatic retries.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: ECS_SPONSOR_UNAVBL
failure_type: MANDATE_UNAVAILABLE
analyzer: transient
standard_code: MANDATE.TEMP_UNAVAILABLE
customer_meaning: The mandate service was temporarily unavailable
possible_causes:
- Mandate registry maintenance window
evidence_required:
- partner_status
- retry_history
resolution_options:
- retry_with_partner
automatic_action_allowed: true
approval_required: false
risk_level: low
reversible: true
escalation_conditions:
- Still unavailable after 2 automatic retries
expected_outcome: Debit processed after the service recovers
retry_allowed: true
action_tier: TIER_1
relevant_documents: []
```

## ECS_BOUNCE_R61: The account's daily transaction limit was reached

ICICI Bank returns `ECS_BOUNCE_R61` in sip autopay and account verification journeys. The bank resets the daily limit at midnight. Saarthi monitors and re-checks; it never splits a debit into smaller debits without approval.

- **What it means for the customer:** The account's daily transaction limit was reached.
- **Likely causes:** Daily debit cap reached.
- **Resolution:** refresh status.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Limit hit on 2 consecutive days.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: ECS_BOUNCE_R61
failure_type: TXN_LIMIT_EXCEEDED
analyzer: monitor
standard_code: PAY.TXN_LIMIT
customer_meaning: The account's daily transaction limit was reached
possible_causes:
- Daily debit cap reached
evidence_required:
- partner_status
- time_with_partner
resolution_options:
- refresh_status
automatic_action_allowed: true
approval_required: false
risk_level: low
reversible: true
escalation_conditions:
- Limit hit on 2 consecutive days
expected_outcome: Debit succeeds in the next limit window
retry_allowed: true
action_tier: TIER_1
relevant_documents: []
```

## IC_REV_IN_PROGRESS: A refund or reversal is on its way

ICICI Bank returns `IC_REV_IN_PROGRESS` in sip autopay and account verification journeys. Reversals settle within 5 working days. Saarthi monitors and escalates if the money does not arrive.

- **What it means for the customer:** A refund or reversal is on its way.
- **Likely causes:** Failed debit being reversed.
- **Resolution:** refresh status.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Reversal not credited within 5 working days.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: IC_REV_IN_PROGRESS
failure_type: REVERSAL_PENDING
analyzer: monitor
standard_code: PAY.REVERSAL_PENDING
customer_meaning: A refund or reversal is on its way
possible_causes:
- Failed debit being reversed
evidence_required:
- partner_status
- time_with_partner
resolution_options:
- refresh_status
automatic_action_allowed: true
approval_required: false
risk_level: low
reversible: true
escalation_conditions:
- Reversal not credited within 5 working days
expected_outcome: Amount credited back
retry_allowed: false
action_tier: TIER_1
relevant_documents: []
```

## IMPS_BENE_PAN_DIFF: The account is registered to a different PAN

ICICI Bank returns `IMPS_BENE_PAN_DIFF` in sip autopay and account verification journeys. Third-party payments are not permitted. When the bank reports the account belongs to another PAN, automation stops and a human specialist takes over.

- **What it means for the customer:** The account is registered to a different PAN.
- **Likely causes:** Customer linked a family member's account; Possible misuse.
- **Resolution:** escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Always.

```yaml
partner: icici
partner_name: ICICI Bank
journey_type: investment
product: SIP autopay and account verification
error_code: IMPS_BENE_PAN_DIFF
failure_type: ACCOUNT_OTHER_PAN
analyzer: human_only
standard_code: BAV.OTHER_PAN
customer_meaning: The account is registered to a different PAN
possible_causes:
- Customer linked a family member's account
- Possible misuse
evidence_required:
- partner_status
resolution_options:
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: high
reversible: false
escalation_conditions:
- Always
expected_outcome: Specialist confirms ownership or the account is removed
retry_allowed: false
action_tier: TIER_3
relevant_documents: []
```
