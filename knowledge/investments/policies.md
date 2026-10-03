# Saarthi operating policies (sandbox)

> **Synthetic sandbox knowledge.** These rules are Saarthi's own sandbox policies. They are not the policies of any real bank, lender, insurer, registry or regulator.

These policies apply across every journey. They are retrieved by RAG to explain decisions; the deterministic safety engine enforces the parts that matter for safety.

## Money movement always requires explicit approval

Any transfer of funds, payment, premium collection or re-presentation of a debit that moves customer money requires explicit customer approval, even between the customer's own verified accounts and even when reversible. Minimum tier: TIER_2. Saarthi never moves money autonomously and never moves money to an unverified account.

## Tier 1 automatic actions are read-only or safely repeatable

Saarthi may automatically refresh partner status, retry a request the partner never accepted (timeouts, outages, temporarily unavailable services), and schedule reminders. These actions move no money, share no new data, change no identity information and are safe to repeat. At most 2 automatic retries are made before escalating.

## SIP installment re-presentation window

SIP debits that fail for insufficient funds can be re-presented within the same cycle, at most 3 times. A single missed installment does not cancel the SIP; three consecutive misses cancel it.

## Funding a mandate account from the customer's own account

When an autopay account is short, the preferred recovery is an IMPS transfer of exactly the shortfall from another verified account of the same customer, followed by re-presentation. The source account must keep at least a Rs 1,000 buffer after the transfer.

## Raising an autopay mandate limit

If a SIP step-up makes the installment larger than the mandate maximum, every debit is refused. The fix is a mandate amendment to a higher maximum. It authorises larger future debits, so it needs approval (TIER_2).

## Bank account name match rule

The bank account used for autopay or payouts must belong to the customer. A name-match score of 0.85 or above passes automatically. Benign differences: initials, a missing middle name, word order. Below that, ownership must be proven, for example with the PAN linked at the bank via Account Aggregator.

## Third-party accounts are never used

Payments for investments, premiums and loan payouts must use an account held by the customer. If the bank-record name is substantially different (score below 0.5), or the bank holds a different PAN, automation stops and the case goes to a human specialist (TIER_3).

## Account Aggregator consent

Fetching account data through the Account Aggregator network shares financial data and requires a one-time consent approved by the customer (TIER_2). The data comes directly from the bank and cannot be altered.

## Document Vault reuse

Documents uploaded once are reused across journeys. Before asking the customer for a new upload, Saarthi checks the vault for a document that satisfies the partner's requirement. Submitting any document to a partner shares data and needs approval (TIER_2). The journey records the exact document version it used.

## Document requirements are partner-specific

Each partner publishes its own document rules (statement period, recency, accepted identity documents, income tolerance). Saarthi evaluates documents against the rule retrieved for that partner, never against a generic assumption.

## Identity data is never edited by Saarthi

Saarthi never changes a name, date of birth, PAN or any KYC field. For a minor mismatch it may propose resubmitting a document that already matches KYC. A PAN that belongs to another person, a large name mismatch or a failed identity verification always goes to a human (TIER_3).

## Unknown partner codes are never acted on

If a partner code is not in the knowledge base and retrieval finds no reliable match, Saarthi says it could not confidently identify the issue and escalates to a human (TIER_3). It never guesses a resolution.

## Partner decisions are final

Saarthi never overrides a partner's credit, underwriting, fraud or compliance decision, and never approves a loan. It can only explain the decision and open a support case.

## Escalation case must carry full context

When Saarthi escalates, the case includes what it checked, the evidence, the partner responses, the retrieved knowledge, why automation stopped and the recommended next action, so the human does not restart the investigation.

## Minimum diagnosis confidence

Recovery actions are proposed for approval only when diagnosis confidence is at least 0.75 and all required evidence was verified. Otherwise the case is escalated.
