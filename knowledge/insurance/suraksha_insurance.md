# Suraksha General Insurance (sandbox): rules and error codes

> **Synthetic sandbox knowledge.** Every partner, error code, rule and procedure in this file is invented for the Saarthi sandbox. None of it describes the real policies, codes or systems of any bank, lender, insurer or registry.

Partner id `suraksha_insurance`. Wire dialect: `nested`.

## Partner profile: document requirements

Suraksha General Insurance (sandbox) evaluates every health insurance application against these document rules, in order. The first failing rule is returned as a partner code.

- `IDENTITY`: accepted_types=['PAN', 'AADHAAR', 'DRIVING_LICENCE'], name_match=True, dob_match=True, unexpired=True
- `MEDICAL_REPORT`: when_age_over=45

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
profile: true
journey_type: insurance
product: Health insurance
dialect: nested
requirements:
  IDENTITY:
    accepted_types:
    - PAN
    - AADHAAR
    - DRIVING_LICENCE
    name_match: true
    dob_match: true
    unexpired: true
  MEDICAL_REPORT:
    when_age_over: 45
```

## SGI_KYC_NAME_11: Name on the document doesn't match your KYC

Suraksha General Insurance (sandbox) returns `SGI_KYC_NAME_11` in health insurance journeys. Minor formatting differences can be fixed by submitting a document whose name matches KYC. A substantially different name is never auto-resolved.

- **What it means for the customer:** Name on the document doesn't match your KYC.
- **Likely causes:** Initials or a missing middle name; Document of a different person.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Name similarity below 0.5.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_KYC_NAME_11
failure_type: NAME_MISMATCH
analyzer: identity_mismatch
standard_code: ID.NAME_MISMATCH
customer_meaning: Name on the document doesn't match your KYC
possible_causes:
- Initials or a missing middle name
- Document of a different person
evidence_required:
- kyc_identity
- submitted_identity
relevant_documents:
- PAN
- AADHAAR
resolution_options:
- submit_existing_document
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: high
reversible: true
escalation_conditions:
- Name similarity below 0.5
expected_outcome: Matching identity document accepted
retry_allowed: true
action_tier: TIER_2
```

## SGI_KYC_DOB_12: Date of birth doesn't match your KYC

Suraksha General Insurance (sandbox) returns `SGI_KYC_DOB_12` in health insurance journeys. Saarthi never edits a date of birth. It can only resubmit a document that already shows the KYC date of birth, with approval.

- **What it means for the customer:** Date of birth doesn't match your KYC.
- **Likely causes:** Document shows a different date of birth.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** No document with the KYC date of birth.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_KYC_DOB_12
failure_type: DOB_MISMATCH
analyzer: identity_mismatch
standard_code: ID.DOB_MISMATCH
customer_meaning: Date of birth doesn't match your KYC
possible_causes:
- Document shows a different date of birth
evidence_required:
- kyc_identity
- submitted_identity
relevant_documents:
- PAN
- AADHAAR
resolution_options:
- submit_existing_document
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: high
reversible: true
escalation_conditions:
- No document with the KYC date of birth
expected_outcome: Matching document accepted
retry_allowed: true
action_tier: TIER_2
```

## SGI_KYC_MISMATCH_10: PAN on the document doesn't match your KYC

Suraksha General Insurance (sandbox) returns `SGI_KYC_MISMATCH_10` in health insurance journeys. The PAN on documents must equal the KYC PAN.

- **What it means for the customer:** PAN on the document doesn't match your KYC.
- **Likely causes:** Wrong PAN document attached.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** PAN belongs to another person.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_KYC_MISMATCH_10
failure_type: PAN_MISMATCH
analyzer: identity_mismatch
standard_code: ID.PAN_MISMATCH
customer_meaning: PAN on the document doesn't match your KYC
possible_causes:
- Wrong PAN document attached
evidence_required:
- kyc_identity
- submitted_identity
relevant_documents:
- PAN
resolution_options:
- submit_existing_document
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: high
reversible: true
escalation_conditions:
- PAN belongs to another person
expected_outcome: Correct PAN document accepted
retry_allowed: true
action_tier: TIER_2
```

## SGI_ID_DOC_MISSING_20: Identity document missing

Suraksha General Insurance (sandbox) returns `SGI_ID_DOC_MISSING_20` in health insurance journeys. Applications stay on hold until every mandatory document is attached.

- **What it means for the customer:** Identity document missing.
- **Likely causes:** Required document not attached to the application.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** Document cannot be provided.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_ID_DOC_MISSING_20
failure_type: DOCUMENT_MISSING
analyzer: document_requirement
standard_code: DOC.MISSING
customer_meaning: Identity document missing
possible_causes:
- Required document not attached to the application
evidence_required:
- document_requirement
- attached_document
- vault_candidates
relevant_documents:
- SALARY_SLIP
resolution_options:
- submit_existing_document
- request_document_upload
automatic_action_allowed: false
approval_required: true
risk_level: low
reversible: true
escalation_conditions:
- Document cannot be provided
expected_outcome: Missing document supplied and application continues
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: IDENTITY
  accepted_types:
  - PAN
  - AADHAAR
  - DRIVING_LICENCE
  present: true
```

## SGI_DOC_UNSUPPORTED_21: That document type isn't accepted

Suraksha General Insurance (sandbox) returns `SGI_DOC_UNSUPPORTED_21` in health insurance journeys. Only the listed document types satisfy this requirement.

- **What it means for the customer:** That document type isn't accepted.
- **Likely causes:** Wrong document attached for this requirement.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** No accepted document available.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_DOC_UNSUPPORTED_21
failure_type: DOC_UNSUPPORTED
analyzer: document_requirement
standard_code: DOC.UNSUPPORTED_TYPE
customer_meaning: That document type isn't accepted
possible_causes:
- Wrong document attached for this requirement
evidence_required:
- document_requirement
- attached_document
- vault_candidates
relevant_documents:
- PAN
- AADHAAR
resolution_options:
- submit_existing_document
- request_document_upload
automatic_action_allowed: false
approval_required: true
risk_level: low
reversible: true
escalation_conditions:
- No accepted document available
expected_outcome: Accepted document type submitted
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: IDENTITY
  accepted_types:
  - PAN
  - AADHAAR
  - DRIVING_LICENCE
```

## SGI_DOC_EXPIRED_22: The document has expired or is too old

Suraksha General Insurance (sandbox) returns `SGI_DOC_EXPIRED_22` in health insurance journeys. Documents must be current: identity documents unexpired, salary slips and statements recent.

- **What it means for the customer:** The document has expired or is too old.
- **Likely causes:** Document past its expiry date; Statement or slip older than allowed.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** No current document available.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_DOC_EXPIRED_22
failure_type: DOC_EXPIRED
analyzer: document_requirement
standard_code: DOC.EXPIRED
customer_meaning: The document has expired or is too old
possible_causes:
- Document past its expiry date
- Statement or slip older than allowed
evidence_required:
- document_requirement
- attached_document
- vault_candidates
relevant_documents:
- SALARY_SLIP
resolution_options:
- submit_existing_document
- request_document_upload
automatic_action_allowed: false
approval_required: true
risk_level: low
reversible: true
escalation_conditions:
- No current document available
expected_outcome: Current document accepted
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: IDENTITY
  accepted_types:
  - PAN
  - AADHAAR
  - DRIVING_LICENCE
  unexpired: true
```

## SGI_DOC_QUALITY_23: Identity document quality too poor to read

Suraksha General Insurance (sandbox) returns `SGI_DOC_QUALITY_23` in health insurance journeys. The partner's reader needs a text-based PDF. Photos or scans without a text layer are rejected.

- **What it means for the customer:** Identity document quality too poor to read.
- **Likely causes:** Scanned image without text; Password-protected or corrupt file.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** Repeated unreadable uploads.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_DOC_QUALITY_23
failure_type: STATEMENT_UNREADABLE
analyzer: document_requirement
standard_code: DOC.UNREADABLE
customer_meaning: Identity document quality too poor to read
possible_causes:
- Scanned image without text
- Password-protected or corrupt file
evidence_required:
- document_requirement
- attached_document
- vault_candidates
relevant_documents:
- BANK_STATEMENT
resolution_options:
- submit_existing_document
- request_document_upload
automatic_action_allowed: false
approval_required: true
risk_level: low
reversible: true
escalation_conditions:
- Repeated unreadable uploads
expected_outcome: Readable document accepted
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: IDENTITY
  accepted_types:
  - PAN
  - AADHAAR
  - DRIVING_LICENCE
  readable: true
```

## SGI_PREMIUM_FAIL_30: The premium payment failed

Suraksha General Insurance (sandbox) returns `SGI_PREMIUM_FAIL_30` in health insurance journeys. Collecting a premium moves money and always needs approval.

- **What it means for the customer:** The premium payment failed.
- **Likely causes:** Insufficient balance in the paying account.
- **Resolution:** retry payment, fund and retry payment.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Payment fails twice.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_PREMIUM_FAIL_30
failure_type: PREMIUM_PAYMENT_FAILED
analyzer: payment_retry
standard_code: PAY.PREMIUM_FAILED
customer_meaning: The premium payment failed
possible_causes:
- Insufficient balance in the paying account
evidence_required:
- paying_account_balance
- payment_amount
resolution_options:
- retry_payment
- fund_and_retry_payment
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: true
escalation_conditions:
- Payment fails twice
expected_outcome: Premium collected, policy proceeds
retry_allowed: true
action_tier: TIER_2
relevant_documents: []
```

## SGI_UW_PENDING_40: Application stuck in underwriting

Suraksha General Insurance (sandbox) returns `SGI_UW_PENDING_40` in health insurance journeys. Saarthi re-checks status automatically and escalates after the SLA.

- **What it means for the customer:** Application stuck in underwriting.
- **Likely causes:** Partner verification backlog.
- **Resolution:** refresh status, escalate to specialist.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** No progress for 24 hours.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_UW_PENDING_40
failure_type: APPLICATION_STUCK
analyzer: monitor
standard_code: APP.STUCK_IN_VERIFICATION
customer_meaning: Application stuck in underwriting
possible_causes:
- Partner verification backlog
evidence_required:
- partner_status
- time_with_partner
resolution_options:
- refresh_status
- escalate_to_specialist
automatic_action_allowed: true
approval_required: false
risk_level: low
reversible: true
escalation_conditions:
- No progress for 24 hours
expected_outcome: Verification completes
retry_allowed: false
action_tier: TIER_1
relevant_documents: []
```

## SGI_MANUAL_UW_41: The partner is reviewing the application manually

Suraksha General Insurance (sandbox) returns `SGI_MANUAL_UW_41` in health insurance journeys. Saarthi cannot influence a partner's manual review. It monitors and can open a support case with full context.

- **What it means for the customer:** The partner is reviewing the application manually.
- **Likely causes:** Partner risk rules.
- **Resolution:** refresh status, escalate to specialist.
- **Automatic action allowed:** yes; approval required: no; risk: medium.
- **Escalate when:** Review exceeds 48 hours.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_MANUAL_UW_41
failure_type: MANUAL_REVIEW
analyzer: monitor
standard_code: APP.MANUAL_REVIEW
customer_meaning: The partner is reviewing the application manually
possible_causes:
- Partner risk rules
evidence_required:
- partner_status
- time_with_partner
resolution_options:
- refresh_status
- escalate_to_specialist
automatic_action_allowed: true
approval_required: false
risk_level: medium
reversible: true
escalation_conditions:
- Review exceeds 48 hours
expected_outcome: Partner completes review
retry_allowed: false
action_tier: TIER_1
relevant_documents: []
```

## SGI_ISSUANCE_PENDING_50: Policy issuance pending

Suraksha General Insurance (sandbox) returns `SGI_ISSUANCE_PENDING_50` in health insurance journeys. Disbursals settle the same working day.

- **What it means for the customer:** Policy issuance pending.
- **Likely causes:** Disbursal batch.
- **Resolution:** refresh status.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Not credited within 1 working day.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_ISSUANCE_PENDING_50
failure_type: DISBURSEMENT_PENDING
analyzer: monitor
standard_code: LOAN.DISBURSEMENT_PENDING
customer_meaning: Policy issuance pending
possible_causes:
- Disbursal batch
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
- Not credited within 1 working day
expected_outcome: Loan amount credited
retry_allowed: false
action_tier: TIER_1
relevant_documents: []
```

## SGI_POLICY_VERIF_PENDING_51: Policy verification pending

Suraksha General Insurance (sandbox) returns `SGI_POLICY_VERIF_PENDING_51` in health insurance journeys. Status is re-checked automatically.

- **What it means for the customer:** Policy verification pending.
- **Likely causes:** Registry queue.
- **Resolution:** refresh status.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Pending more than 24 hours.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_POLICY_VERIF_PENDING_51
failure_type: IDV_PENDING
analyzer: monitor
standard_code: ID.VERIFICATION_PENDING
customer_meaning: Policy verification pending
possible_causes:
- Registry queue
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
- Pending more than 24 hours
expected_outcome: Verification completes
retry_allowed: false
action_tier: TIER_1
relevant_documents: []
```

## SGI_BANK_UNVERIFIED_60: The payout account isn't verified

Suraksha General Insurance (sandbox) returns `SGI_BANK_UNVERIFIED_60` in health insurance journeys. Money may only be paid out to a verified account in the customer's name. Switching the account needs approval.

- **What it means for the customer:** The payout account isn't verified.
- **Likely causes:** Selected account failed verification.
- **Resolution:** switch partner account, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** No verified account available.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_BANK_UNVERIFIED_60
failure_type: ACCOUNT_UNVERIFIED_FOR_PAYOUT
analyzer: account_unverified
standard_code: BAV.PAYOUT_ACCOUNT_UNVERIFIED
customer_meaning: The payout account isn't verified
possible_causes:
- Selected account failed verification
evidence_required:
- paying_account
- verified_accounts
resolution_options:
- switch_partner_account
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: true
escalation_conditions:
- No verified account available
expected_outcome: Verified account accepted
retry_allowed: true
action_tier: TIER_2
relevant_documents: []
```

## SGI_DUPLICATE_70: A similar application already exists

Suraksha General Insurance (sandbox) returns `SGI_DUPLICATE_70` in health insurance journeys. Duplicate applications are resolved by the partner's operations team.

- **What it means for the customer:** A similar application already exists.
- **Likely causes:** Earlier application still open.
- **Resolution:** escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Always.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_DUPLICATE_70
failure_type: DUPLICATE_APPLICATION
analyzer: human_only
standard_code: APP.DUPLICATE
customer_meaning: A similar application already exists
possible_causes:
- Earlier application still open
evidence_required:
- partner_status
resolution_options:
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: medium
reversible: false
escalation_conditions:
- Always
expected_outcome: Specialist merges or closes the duplicate
retry_allowed: false
action_tier: TIER_3
relevant_documents: []
```

## SGI_SYS_ERROR_99: The partner hit a technical error

Suraksha General Insurance (sandbox) returns `SGI_SYS_ERROR_99` in health insurance journeys. Resubmitting the same application payload is idempotent at the partner.

- **What it means for the customer:** The partner hit a technical error.
- **Likely causes:** Partner system error.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Fails after 2 automatic retries.

```yaml
partner: suraksha_insurance
partner_name: Suraksha General Insurance (sandbox)
journey_type: insurance
product: Health insurance
error_code: SGI_SYS_ERROR_99
failure_type: PARTNER_TECH_FAILURE
analyzer: transient
standard_code: PARTNER.TECHNICAL_FAILURE
customer_meaning: The partner hit a technical error
possible_causes:
- Partner system error
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
- Fails after 2 automatic retries
expected_outcome: Application processed on retry
retry_allowed: true
action_tier: TIER_1
relevant_documents: []
```
