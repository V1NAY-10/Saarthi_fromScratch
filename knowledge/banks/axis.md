# Axis Bank (sandbox): error codes

> **Synthetic sandbox knowledge.** Every partner, error code, rule and procedure in this file is invented for the Saarthi sandbox. None of it describes the real policies, codes or systems of any bank, lender, insurer or registry.

Partner id `axis`. Wire dialect: `nach` (flat NPCI-style fields: txnStatus, respCode, respMsg).

## AUTOPAY_DEBIT_FAILED_07: Insufficient balance in the paying account

Axis Bank returns `AUTOPAY_DEBIT_FAILED_07` in sip autopay and account verification journeys. The debit was returned because the account did not hold enough funds. The mandate stays active and the debit may be re-presented within the cycle (at most 3 re-presentations). Moving money between the customer's own verified accounts needs explicit approval.

- **What it means for the customer:** Insufficient balance in the paying account.
- **Likely causes:** Available balance lower than the debit amount at presentment.
- **Resolution:** retry debit, fund and retry, remind before window.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Re-presentation limit reached; No verified account can cover the shortfall for 3 days.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AUTOPAY_DEBIT_FAILED_07
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

## AUTOPAY_DEBIT_FAILED_12: Debit amount is above the autopay limit

Axis Bank returns `AUTOPAY_DEBIT_FAILED_12` in sip autopay and account verification journeys. The bank refuses any debit above the maximum amount authorised on the mandate, before it checks the balance. Raising the limit authorises larger future debits and therefore needs the customer's approval.

- **What it means for the customer:** Debit amount is above the autopay limit.
- **Likely causes:** SIP stepped up above the mandate maximum; Mandate registered with a low maximum.
- **Resolution:** raise mandate limit and retry, reduce sip to limit.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Bank refuses mandate amendment.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AUTOPAY_DEBIT_FAILED_12
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

## PD_NAME_MISMATCH_04: Bank account name doesn't match PAN

Axis Bank returns `PD_NAME_MISMATCH_04` in sip autopay and account verification journeys. A name-match score of 0.85 or above passes. Below that, ownership must be proven, for example via the PAN linked at the bank through an Account Aggregator consent. Third-party accounts may not be used for mutual fund payments.

- **What it means for the customer:** Bank account name doesn't match PAN.
- **Likely causes:** Initials or missing middle name at the bank; Account belongs to someone else.
- **Resolution:** verify ownership via aa, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Name similarity below 0.5; Account Aggregator returns a different PAN.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: PD_NAME_MISMATCH_04
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

## AUTOPAY_MANDATE_EXP_21: The autopay mandate has expired

Axis Bank returns `AUTOPAY_MANDATE_EXP_21` in sip autopay and account verification journeys. An expired mandate cannot be used for any further debits. A new mandate must be registered, which creates a new standing authorisation and needs the customer's approval.

- **What it means for the customer:** The autopay mandate has expired.
- **Likely causes:** Mandate end date passed.
- **Resolution:** create new mandate.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** New mandate registration rejected.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AUTOPAY_MANDATE_EXP_21
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

## AUTOPAY_MANDATE_CXL_22: The autopay mandate was cancelled

Axis Bank returns `AUTOPAY_MANDATE_CXL_22` in sip autopay and account verification journeys. A cancelled mandate cannot be revived. Saarthi may propose a new mandate, but only the customer can approve creating it.

- **What it means for the customer:** The autopay mandate was cancelled.
- **Likely causes:** Customer or bank cancelled the mandate.
- **Resolution:** create new mandate.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Customer did not intend to keep the SIP.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AUTOPAY_MANDATE_CXL_22
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

## AX_SVC_DOWN_503: The bank's systems were temporarily down

Axis Bank returns `AX_SVC_DOWN_503` in sip autopay and account verification journeys. During an outage nothing is debited. Retrying after recovery is safe and automatic.

- **What it means for the customer:** The bank's systems were temporarily down.
- **Likely causes:** Unplanned bank outage.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Outage continues after 2 automatic retries.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AX_SVC_DOWN_503
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

## AX_SWITCH_TIMEOUT_91: The bank didn't respond in time

Axis Bank returns `AX_SWITCH_TIMEOUT_91` in sip autopay and account verification journeys. A timeout means the bank never accepted the request, so a retry cannot double-debit. Saarthi retries automatically up to twice.

- **What it means for the customer:** The bank didn't respond in time.
- **Likely causes:** Bank switch timeout.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Timeout repeats after 2 automatic retries.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AX_SWITCH_TIMEOUT_91
failure_type: BANK_TIMEOUT
analyzer: transient
standard_code: PARTNER.TIMEOUT
customer_meaning: The bank didn't respond in time
possible_causes:
- Bank switch timeout
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
- Timeout repeats after 2 automatic retries
expected_outcome: Request processed on retry
retry_allowed: true
action_tier: TIER_1
relevant_documents: []
```

## AUTOPAY_DEBIT_FAILED_99: The recurring debit failed without a specific reason

Axis Bank returns `AUTOPAY_DEBIT_FAILED_99` in sip autopay and account verification journeys. This generic code carries no reason. Saarthi must infer the cause from evidence (balance vs amount, amount vs mandate limit). If the evidence explains nothing, it must not guess and should escalate.

- **What it means for the customer:** The recurring debit failed without a specific reason.
- **Likely causes:** Insufficient balance; Amount above mandate limit; Unspecified bank-side issue.
- **Resolution:** fund and retry, retry debit, raise mandate limit and retry, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Neither balance nor limit explains the failure.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AUTOPAY_DEBIT_FAILED_99
failure_type: RECURRING_DEBIT_FAILED
analyzer: debit_inference
standard_code: PAY.RECURRING_FAILED
customer_meaning: The recurring debit failed without a specific reason
possible_causes:
- Insufficient balance
- Amount above mandate limit
- Unspecified bank-side issue
evidence_required:
- mandate_account_balance
- installment_amount
- mandate_limit
- mandate_status
resolution_options:
- fund_and_retry
- retry_debit
- raise_mandate_limit_and_retry
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: true
escalation_conditions:
- Neither balance nor limit explains the failure
expected_outcome: Cause identified and installment debited
retry_allowed: true
action_tier: TIER_2
relevant_documents: []
```

## AX_DUP_TXN_DETECTED: The bank flagged this as a possible duplicate payment

Axis Bank returns `AX_DUP_TXN_DETECTED` in sip autopay and account verification journeys. Never re-present a payment flagged as duplicate. Check the status of the original first.

- **What it means for the customer:** The bank flagged this as a possible duplicate payment.
- **Likely causes:** Same amount presented twice.
- **Resolution:** refresh status.
- **Automatic action allowed:** yes; approval required: no; risk: medium.
- **Escalate when:** Both presentments debited.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: AX_DUP_TXN_DETECTED
failure_type: DUPLICATE_TXN
analyzer: monitor
standard_code: PAY.DUPLICATE
customer_meaning: The bank flagged this as a possible duplicate payment
possible_causes:
- Same amount presented twice
evidence_required:
- partner_status
- time_with_partner
resolution_options:
- refresh_status
automatic_action_allowed: true
approval_required: false
risk_level: medium
reversible: true
escalation_conditions:
- Both presentments debited
expected_outcome: Original payment confirmed, duplicate dropped
retry_allowed: false
action_tier: TIER_1
relevant_documents: []
```

## PD_PAN_NOT_HOLDER: The account is registered to a different PAN

Axis Bank returns `PD_PAN_NOT_HOLDER` in sip autopay and account verification journeys. Third-party payments are not permitted. When the bank reports the account belongs to another PAN, automation stops and a human specialist takes over.

- **What it means for the customer:** The account is registered to a different PAN.
- **Likely causes:** Customer linked a family member's account; Possible misuse.
- **Resolution:** escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Always.

```yaml
partner: axis
partner_name: Axis Bank
journey_type: investment
product: SIP autopay and account verification
error_code: PD_PAN_NOT_HOLDER
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
