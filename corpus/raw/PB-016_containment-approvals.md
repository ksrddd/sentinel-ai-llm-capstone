---
doc_id: PB-016
title: Containment Actions and Approval Requirements
category: policy
version: 2.4
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-15
---
# Containment Actions and Approval Requirements

FICTIONAL POLICY NOTICE: Approval levels are fictional and exist only for the SentinelAI academic project.

## Principle
Containment limits damage but can also disrupt the business. Every containment action is a human decision. Automated tools and the AI copilot may recommend actions but must never execute them.

## Approval levels
- Block an external IP address or domain at the perimeter: tier-2 analyst.
- Isolate a workstation through EDR: tier-2 analyst.
- Isolate a server or any high or critical tier asset: incident commander plus asset owner.
- Disable a user account: tier-2 analyst; for privileged accounts, incident commander.
- Reset credentials and revoke sessions: tier-2 analyst.

## Prohibited without legal approval
Hack-back, scanning or probing attacker infrastructure, accessing third-party systems, and deleting data are not permitted.

## Before containing
Preserve volatile evidence where feasible (PB-015) and notify the asset owner, except where delay would allow obvious ongoing damage.

## Recording
Every action is logged in the case with who approved it, when it was executed and how it was verified.
