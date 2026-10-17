---
doc_id: PB-003
title: Escalation and Notification Matrix
category: process
version: 1.4
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-08-15
---
# Escalation and Notification Matrix

FICTIONAL POLICY NOTICE: Roles, timings and contacts in this document are fictional and exist only for the SentinelAI academic project.

## Who is told, and how fast
- Informational: no escalation. Document and close within the shift.
- Low: tier-1 analyst owns the case. Review at the daily stand-up.
- Medium: notify the tier-2 duty analyst within 60 minutes.
- High: page the tier-2 duty analyst within 15 minutes and inform the SOC lead.
- Critical: page the SOC lead and the on-call incident commander immediately; open a bridge call; inform the CISO office within 30 minutes.

## Special triggers
Regardless of score, escalate to tier-2 when a domain administrator or cloud root identity is involved, when data from the customer records environment may have left the network, or when ransomware notes are observed.

## Hand-over content
An escalation message must include the case number, the calculated severity and its factors, the observed evidence, what has already been done, and what decision is needed from the receiver. Do not paste credentials or full customer records into chat channels.

## De-escalation
A case may be de-escalated only by the person who currently owns it at the higher tier, with a written justification.
