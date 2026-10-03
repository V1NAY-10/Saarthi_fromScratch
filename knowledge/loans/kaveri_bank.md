# Kaveri Bank Personal Loans (sandbox): rules and error codes

> **Synthetic sandbox knowledge.** Every partner, error code, rule and procedure in this file is invented for the Saarthi sandbox. None of it describes the real policies, codes or systems of any bank, lender, insurer or registry.

Partner id `kaveri_bank`. Wire dialect: `flat`.

## Partner profile: document requirements

Kaveri Bank Personal Loans (sandbox) evaluates every personal loan application against these document rules, in order. The first failing rule is returned as a partner code.

- `PAN`: required
- `BANK_STATEMENT`: min_months=3, max_age_days=45, name_match=True
- `SALARY_SLIP`: max_age_days=62, income_tolerance=0.25

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
profile: true
journey_type: loan
product: Personal loan
dialect: flat
requirements:
  PAN: {}
  BANK_STATEMENT:
    min_months: 3
    max_age_days: 45
    name_match: true
  SALARY_SLIP:
    max_age_days: 62
    income_tolerance: 0.25
```

## BANK_STATEMENT_PERIOD_INSUFFICIENT: The bank statement doesn't cover enough months

Kaveri Bank Personal Loans (sandbox) returns `BANK_STATEMENT_PERIOD_INSUFFICIENT` in personal loan journeys. The partner requires a statement covering the latest 3 complete months. A shorter statement is rejected even if every other check passes. Submitting a different document shares data with the partner and needs the customer's approval.

- **What it means for the customer:** The bank statement doesn't cover enough months.
- **Likely causes:** Statement covers fewer months than the partner requires.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Customer cannot obtain a statement of the required period.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: BANK_STATEMENT_PERIOD_INSUFFICIENT
failure_type: STATEMENT_PERIOD_INSUFFICIENT
analyzer: document_requirement
standard_code: DOC.PERIOD_INSUFFICIENT
customer_meaning: The bank statement doesn't cover enough months
possible_causes:
- Statement covers fewer months than the partner requires
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
risk_level: medium
reversible: true
escalation_conditions:
- Customer cannot obtain a statement of the required period
expected_outcome: Statement accepted and application continues
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: BANK_STATEMENT
  min_months: 3
```

## LOAN_DOC_REJECTED_21: The bank statement was rejected

Kaveri Bank Personal Loans (sandbox) returns `LOAN_DOC_REJECTED_21` in personal loan journeys. The statement's account holder must match the applicant's PAN name (score 0.85 or above).

- **What it means for the customer:** The bank statement was rejected.
- **Likely causes:** Account holder name differs from the applicant; Statement is from an unlinked account.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Statement name belongs to a different person.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_DOC_REJECTED_21
failure_type: STATEMENT_REJECTED
analyzer: document_requirement
standard_code: DOC.STATEMENT_REJECTED
customer_meaning: The bank statement was rejected
possible_causes:
- Account holder name differs from the applicant
- Statement is from an unlinked account
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
risk_level: medium
reversible: true
escalation_conditions:
- Statement name belongs to a different person
expected_outcome: Valid statement accepted
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: BANK_STATEMENT
  name_match: true
```

## LOAN_DOC_UNREADABLE_24: The document couldn't be read

Kaveri Bank Personal Loans (sandbox) returns `LOAN_DOC_UNREADABLE_24` in personal loan journeys. The partner's reader needs a text-based PDF. Photos or scans without a text layer are rejected.

- **What it means for the customer:** The document couldn't be read.
- **Likely causes:** Scanned image without text; Password-protected or corrupt file.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** Repeated unreadable uploads.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_DOC_UNREADABLE_24
failure_type: STATEMENT_UNREADABLE
analyzer: document_requirement
standard_code: DOC.UNREADABLE
customer_meaning: The document couldn't be read
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
  doc_type: BANK_STATEMENT
  readable: true
```

## LOAN_DOC_MISSING_20: A required document is missing

Kaveri Bank Personal Loans (sandbox) returns `LOAN_DOC_MISSING_20` in personal loan journeys. Applications stay on hold until every mandatory document is attached.

- **What it means for the customer:** A required document is missing.
- **Likely causes:** Required document not attached to the application.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** Document cannot be provided.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_DOC_MISSING_20
failure_type: DOCUMENT_MISSING
analyzer: document_requirement
standard_code: DOC.MISSING
customer_meaning: A required document is missing
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
  doc_type: SALARY_SLIP
  present: true
```

## LOAN_DOC_UNSUPPORTED_25: That document type isn't accepted

Kaveri Bank Personal Loans (sandbox) returns `LOAN_DOC_UNSUPPORTED_25` in personal loan journeys. Only the listed document types satisfy this requirement.

- **What it means for the customer:** That document type isn't accepted.
- **Likely causes:** Wrong document attached for this requirement.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** No accepted document available.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_DOC_UNSUPPORTED_25
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
  doc_type: PAN
  accepted_types:
  - PAN
```

## LOAN_DOC_EXPIRED_26: The document has expired or is too old

Kaveri Bank Personal Loans (sandbox) returns `LOAN_DOC_EXPIRED_26` in personal loan journeys. Documents must be current: identity documents unexpired, salary slips and statements recent.

- **What it means for the customer:** The document has expired or is too old.
- **Likely causes:** Document past its expiry date; Statement or slip older than allowed.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** No current document available.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_DOC_EXPIRED_26
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
  doc_type: SALARY_SLIP
  max_age_days: 62
```

## LOAN_INCOME_MISMATCH_31: Declared income doesn't match the salary slip

Kaveri Bank Personal Loans (sandbox) returns `LOAN_INCOME_MISMATCH_31` in personal loan journeys. Declared income must be within 25% of the latest salary slip's net pay. Saarthi never edits declared income on the customer's behalf.

- **What it means for the customer:** Declared income doesn't match the salary slip.
- **Likely causes:** Declared monthly income differs from net pay by more than the tolerance.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Mismatch persists with the latest slip.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_INCOME_MISMATCH_31
failure_type: INCOME_MISMATCH
analyzer: document_requirement
standard_code: DOC.INCOME_MISMATCH
customer_meaning: Declared income doesn't match the salary slip
possible_causes:
- Declared monthly income differs from net pay by more than the tolerance
evidence_required:
- document_requirement
- attached_document
- vault_candidates
relevant_documents:
- SALARY_SLIP
resolution_options:
- submit_existing_document
- escalate_to_specialist
automatic_action_allowed: false
approval_required: true
risk_level: high
reversible: true
escalation_conditions:
- Mismatch persists with the latest slip
expected_outcome: Income verified
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: SALARY_SLIP
  income_tolerance: 0.25
```

## LOAN_SALARY_NOT_FOUND_32: No salary credits found in the statement

Kaveri Bank Personal Loans (sandbox) returns `LOAN_SALARY_NOT_FOUND_32` in personal loan journeys. The statement must show at least one salary credit.

- **What it means for the customer:** No salary credits found in the statement.
- **Likely causes:** Statement is from a non-salary account.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** Customer is self-employed.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_SALARY_NOT_FOUND_32
failure_type: SALARY_CREDIT_NOT_DETECTED
analyzer: document_requirement
standard_code: DOC.SALARY_NOT_DETECTED
customer_meaning: No salary credits found in the statement
possible_causes:
- Statement is from a non-salary account
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
risk_level: medium
reversible: true
escalation_conditions:
- Customer is self-employed
expected_outcome: Salary account statement accepted
retry_allowed: true
action_tier: TIER_2
requirement:
  doc_type: BANK_STATEMENT
  salary_credits: 1
```

## LOAN_KYC_NAME_41: Name on the document doesn't match your KYC

Kaveri Bank Personal Loans (sandbox) returns `LOAN_KYC_NAME_41` in personal loan journeys. Minor formatting differences can be fixed by submitting a document whose name matches KYC. A substantially different name is never auto-resolved.

- **What it means for the customer:** Name on the document doesn't match your KYC.
- **Likely causes:** Initials or a missing middle name; Document of a different person.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Name similarity below 0.5.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_KYC_NAME_41
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

## LOAN_KYC_DOB_42: Date of birth doesn't match your KYC

Kaveri Bank Personal Loans (sandbox) returns `LOAN_KYC_DOB_42` in personal loan journeys. Saarthi never edits a date of birth. It can only resubmit a document that already shows the KYC date of birth, with approval.

- **What it means for the customer:** Date of birth doesn't match your KYC.
- **Likely causes:** Document shows a different date of birth.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** No document with the KYC date of birth.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_KYC_DOB_42
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

## LOAN_VERIFICATION_HOLD: The application is stuck in verification

Kaveri Bank Personal Loans (sandbox) returns `LOAN_VERIFICATION_HOLD` in personal loan journeys. Saarthi re-checks status automatically and escalates after the SLA.

- **What it means for the customer:** The application is stuck in verification.
- **Likely causes:** Partner verification backlog.
- **Resolution:** refresh status, escalate to specialist.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** No progress for 24 hours.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_VERIFICATION_HOLD
failure_type: APPLICATION_STUCK
analyzer: monitor
standard_code: APP.STUCK_IN_VERIFICATION
customer_meaning: The application is stuck in verification
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

## LOAN_MANUAL_REVIEW: The partner is reviewing the application manually

Kaveri Bank Personal Loans (sandbox) returns `LOAN_MANUAL_REVIEW` in personal loan journeys. Saarthi cannot influence a partner's manual review. It monitors and can open a support case with full context.

- **What it means for the customer:** The partner is reviewing the application manually.
- **Likely causes:** Partner risk rules.
- **Resolution:** refresh status, escalate to specialist.
- **Automatic action allowed:** yes; approval required: no; risk: medium.
- **Escalate when:** Review exceeds 48 hours.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_MANUAL_REVIEW
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

## LOAN_PARTNER_ERROR_500: The partner hit a technical error

Kaveri Bank Personal Loans (sandbox) returns `LOAN_PARTNER_ERROR_500` in personal loan journeys. Resubmitting the same application payload is idempotent at the partner.

- **What it means for the customer:** The partner hit a technical error.
- **Likely causes:** Partner system error.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Fails after 2 automatic retries.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_PARTNER_ERROR_500
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

## LOAN_DISBURSAL_PENDING: The loan amount is on its way

Kaveri Bank Personal Loans (sandbox) returns `LOAN_DISBURSAL_PENDING` in personal loan journeys. Disbursals settle the same working day.

- **What it means for the customer:** The loan amount is on its way.
- **Likely causes:** Disbursal batch.
- **Resolution:** refresh status.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Not credited within 1 working day.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_DISBURSAL_PENDING
failure_type: DISBURSEMENT_PENDING
analyzer: monitor
standard_code: LOAN.DISBURSEMENT_PENDING
customer_meaning: The loan amount is on its way
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

## LOAN_DISBURSAL_FAILED: The loan disbursal failed

Kaveri Bank Personal Loans (sandbox) returns `LOAN_DISBURSAL_FAILED` in personal loan journeys. Retrying a failed credit to the customer's own verified account is safe; the loan was already sanctioned with the customer's consent.

- **What it means for the customer:** The loan disbursal failed.
- **Likely causes:** Beneficiary bank rejected the credit.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: medium.
- **Escalate when:** Fails after 2 automatic retries.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_DISBURSAL_FAILED
failure_type: DISBURSEMENT_FAILED
analyzer: transient
standard_code: LOAN.DISBURSEMENT_FAILED
customer_meaning: The loan disbursal failed
possible_causes:
- Beneficiary bank rejected the credit
evidence_required:
- partner_status
- retry_history
resolution_options:
- retry_with_partner
automatic_action_allowed: true
approval_required: false
risk_level: medium
reversible: true
escalation_conditions:
- Fails after 2 automatic retries
expected_outcome: Loan amount credited
retry_allowed: true
action_tier: TIER_1
relevant_documents: []
```

## LOAN_REJECTED: The partner rejected the application

Kaveri Bank Personal Loans (sandbox) returns `LOAN_REJECTED` in personal loan journeys. Saarthi never overrides a partner's credit or compliance decision.

- **What it means for the customer:** The partner rejected the application.
- **Likely causes:** Partner credit or underwriting decision.
- **Resolution:** escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Always.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_REJECTED
failure_type: APPLICATION_REJECTED
analyzer: human_only
standard_code: APP.REJECTED
customer_meaning: The partner rejected the application
possible_causes:
- Partner credit or underwriting decision
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
expected_outcome: Customer is informed; specialist explains options
retry_allowed: false
action_tier: TIER_3
relevant_documents: []
```

## LOAN_PAYOUT_ACCT_UNVERIFIED: The payout account isn't verified

Kaveri Bank Personal Loans (sandbox) returns `LOAN_PAYOUT_ACCT_UNVERIFIED` in personal loan journeys. Money may only be paid out to a verified account in the customer's name. Switching the account needs approval.

- **What it means for the customer:** The payout account isn't verified.
- **Likely causes:** Selected account failed verification.
- **Resolution:** switch partner account, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: medium.
- **Escalate when:** No verified account available.

```yaml
partner: kaveri_bank
partner_name: Kaveri Bank Personal Loans (sandbox)
journey_type: loan
product: Personal loan
error_code: LOAN_PAYOUT_ACCT_UNVERIFIED
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
