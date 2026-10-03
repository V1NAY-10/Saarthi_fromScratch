# IdentiVerify KYC Registry (sandbox): rules and error codes

> **Synthetic sandbox knowledge.** Every partner, error code, rule and procedure in this file is invented for the Saarthi sandbox. None of it describes the real policies, codes or systems of any bank, lender, insurer or registry.

Partner id `identiverify`. Wire dialect: `flat`.

## Partner profile: document requirements

IdentiVerify KYC Registry (sandbox) evaluates every kyc verification application against these document rules, in order. The first failing rule is returned as a partner code.

- `IDENTITY`: accepted_types=['PAN', 'AADHAAR', 'DRIVING_LICENCE'], name_match=True, dob_match=True, unexpired=True

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
profile: true
journey_type: kyc
product: KYC verification
dialect: flat
requirements:
  IDENTITY:
    accepted_types:
    - PAN
    - AADHAAR
    - DRIVING_LICENCE
    name_match: true
    dob_match: true
    unexpired: true
```

## KYC_PAN_MISMATCH: PAN on the document doesn't match your KYC

IdentiVerify KYC Registry (sandbox) returns `KYC_PAN_MISMATCH` in kyc verification journeys. The PAN on documents must equal the KYC PAN.

- **What it means for the customer:** PAN on the document doesn't match your KYC.
- **Likely causes:** Wrong PAN document attached.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** PAN belongs to another person.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_PAN_MISMATCH
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

## KYC_NAME_MISMATCH: Name on the document doesn't match your KYC

IdentiVerify KYC Registry (sandbox) returns `KYC_NAME_MISMATCH` in kyc verification journeys. Minor formatting differences can be fixed by submitting a document whose name matches KYC. A substantially different name is never auto-resolved.

- **What it means for the customer:** Name on the document doesn't match your KYC.
- **Likely causes:** Initials or a missing middle name; Document of a different person.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Name similarity below 0.5.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_NAME_MISMATCH
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

## KYC_DOB_MISMATCH: Date of birth doesn't match your KYC

IdentiVerify KYC Registry (sandbox) returns `KYC_DOB_MISMATCH` in kyc verification journeys. Saarthi never edits a date of birth. It can only resubmit a document that already shows the KYC date of birth, with approval.

- **What it means for the customer:** Date of birth doesn't match your KYC.
- **Likely causes:** Document shows a different date of birth.
- **Resolution:** submit existing document, escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** No document with the KYC date of birth.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_DOB_MISMATCH
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

## KYC_PAN_OTHER_PERSON: The PAN belongs to a different person

IdentiVerify KYC Registry (sandbox) returns `KYC_PAN_OTHER_PERSON` in kyc verification journeys. High-risk identity issues are never auto-resolved. Identity data is never edited by Saarthi.

- **What it means for the customer:** The PAN belongs to a different person.
- **Likely causes:** Identity misuse; Data-entry error at registration.
- **Resolution:** escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Always.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_PAN_OTHER_PERSON
failure_type: PAN_OTHER_PERSON
analyzer: human_only
standard_code: ID.PAN_OTHER_PERSON
customer_meaning: The PAN belongs to a different person
possible_causes:
- Identity misuse
- Data-entry error at registration
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
expected_outcome: Specialist verifies identity
retry_allowed: false
action_tier: TIER_3
relevant_documents: []
```

## KYC_DOC_UNREADABLE: Identity document unreadable

IdentiVerify KYC Registry (sandbox) returns `KYC_DOC_UNREADABLE` in kyc verification journeys. The partner's reader needs a text-based PDF. Photos or scans without a text layer are rejected.

- **What it means for the customer:** Identity document unreadable.
- **Likely causes:** Scanned image without text; Password-protected or corrupt file.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** Repeated unreadable uploads.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_DOC_UNREADABLE
failure_type: STATEMENT_UNREADABLE
analyzer: document_requirement
standard_code: DOC.UNREADABLE
customer_meaning: Identity document unreadable
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

## KYC_DOC_EXPIRED: The document has expired or is too old

IdentiVerify KYC Registry (sandbox) returns `KYC_DOC_EXPIRED` in kyc verification journeys. Documents must be current: identity documents unexpired, salary slips and statements recent.

- **What it means for the customer:** The document has expired or is too old.
- **Likely causes:** Document past its expiry date; Statement or slip older than allowed.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** No current document available.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_DOC_EXPIRED
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

## KYC_DOC_MISSING: A required document is missing

IdentiVerify KYC Registry (sandbox) returns `KYC_DOC_MISSING` in kyc verification journeys. Applications stay on hold until every mandatory document is attached.

- **What it means for the customer:** A required document is missing.
- **Likely causes:** Required document not attached to the application.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** Document cannot be provided.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_DOC_MISSING
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
  doc_type: IDENTITY
  accepted_types:
  - PAN
  - AADHAAR
  - DRIVING_LICENCE
  present: true
```

## KYC_DOC_UNSUPPORTED: That document type isn't accepted

IdentiVerify KYC Registry (sandbox) returns `KYC_DOC_UNSUPPORTED` in kyc verification journeys. Only the listed document types satisfy this requirement.

- **What it means for the customer:** That document type isn't accepted.
- **Likely causes:** Wrong document attached for this requirement.
- **Resolution:** submit existing document, request document upload.
- **Automatic action allowed:** no; approval required: yes; risk: low.
- **Escalate when:** No accepted document available.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_DOC_UNSUPPORTED
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

## KYC_IDV_TIMEOUT: Identity verification timed out

IdentiVerify KYC Registry (sandbox) returns `KYC_IDV_TIMEOUT` in kyc verification journeys. Re-running the same verification request is safe: it shares no new data and changes no identity information.

- **What it means for the customer:** Identity verification timed out.
- **Likely causes:** Registry did not respond.
- **Resolution:** retry with partner.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Times out after 2 automatic retries.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_IDV_TIMEOUT
failure_type: IDV_TIMEOUT
analyzer: transient
standard_code: ID.VERIFICATION_TIMEOUT
customer_meaning: Identity verification timed out
possible_causes:
- Registry did not respond
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
- Times out after 2 automatic retries
expected_outcome: Verification completes on retry
retry_allowed: true
action_tier: TIER_1
relevant_documents: []
```

## KYC_IDV_PENDING: Identity verification is still pending

IdentiVerify KYC Registry (sandbox) returns `KYC_IDV_PENDING` in kyc verification journeys. Status is re-checked automatically.

- **What it means for the customer:** Identity verification is still pending.
- **Likely causes:** Registry queue.
- **Resolution:** refresh status.
- **Automatic action allowed:** yes; approval required: no; risk: low.
- **Escalate when:** Pending more than 24 hours.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_IDV_PENDING
failure_type: IDV_PENDING
analyzer: monitor
standard_code: ID.VERIFICATION_PENDING
customer_meaning: Identity verification is still pending
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

## KYC_IDV_FAILED: Identity verification failed

IdentiVerify KYC Registry (sandbox) returns `KYC_IDV_FAILED` in kyc verification journeys. Failed identity verification always needs a human.

- **What it means for the customer:** Identity verification failed.
- **Likely causes:** Registry could not confirm identity.
- **Resolution:** escalate to specialist.
- **Automatic action allowed:** no; approval required: yes; risk: high.
- **Escalate when:** Always.

```yaml
partner: identiverify
partner_name: IdentiVerify KYC Registry (sandbox)
journey_type: kyc
product: KYC verification
error_code: KYC_IDV_FAILED
failure_type: IDV_FAILED
analyzer: human_only
standard_code: ID.VERIFICATION_FAILED
customer_meaning: Identity verification failed
possible_causes:
- Registry could not confirm identity
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
expected_outcome: Specialist completes verification
retry_allowed: false
action_tier: TIER_3
relevant_documents: []
```
