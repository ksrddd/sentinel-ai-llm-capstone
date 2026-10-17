---
doc_id: PB-017
title: Playbook - Phishing Email Triage
category: detection-playbook
version: 1.6
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-08-25
---
# Playbook: Phishing Email Triage

FICTIONAL POLICY NOTICE: This playbook is fictional and intended for academic demonstration only.

## Typical reports
Users report a message through the report button, or the mail gateway flags a message for a lookalike sender domain, a credential-harvesting link or a macro-enabled attachment.

## Investigation steps
1. Review headers: return path, sending infrastructure and authentication results (SPF, DKIM, DMARC).
2. Extract links and attachment hashes without opening them on a normal workstation.
3. Find all recipients of the same message and determine who clicked or opened the attachment.
4. For users who entered credentials, continue with PB-005; for users who opened attachments that executed, continue with PB-007.

## Recommended response
Purge the message from all mailboxes after approval, block the sender domain and the landing page, and send a short awareness note to affected users.

## False positives
Legitimate marketing tools and newly onboarded suppliers often fail one authentication check. Verify with the business contact before blocking a supplier domain.
