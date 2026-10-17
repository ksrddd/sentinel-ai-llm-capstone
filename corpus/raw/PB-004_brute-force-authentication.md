---
doc_id: PB-004
title: Playbook - Password Guessing and Brute-Force Authentication
category: detection-playbook
version: 2.3
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-10
---
# Playbook: Password Guessing and Brute-Force Authentication

FICTIONAL POLICY NOTICE: Thresholds below are fictional examples for the Kestrel Analytics demonstration environment.

## Recognising the pattern
Repeated failed sign-in attempts against one account from one origin (vertical guessing), or a small number of failures against many accounts from one origin (password spraying). Typical telemetry: Windows event 4625, SSH "Failed password" lines, VPN or identity-provider failure logs. In this environment the correlation rule fires at 20 failures within 10 minutes.

## Key questions
- Did any attempt succeed after the failures? A success following a burst of failures changes the case to a possible account takeover; continue with PB-005.
- Is the source address internal or external? Internal sources can indicate a misconfigured service with a stale password.
- How many distinct usernames were targeted?

## Investigation steps
1. Count failures per username and per source address over the window.
2. Check for a successful authentication from the same source within 24 hours.
3. Check whether the targeted accounts exist; attempts against non-existent names suggest automated spraying.
4. Review whether the service is exposed to the internet.

## Recommended response (requires approval per PB-016)
- Temporarily block the source address at the perimeter if it is external.
- Force a password reset and session revocation only if a success was observed.
- Confirm multi-factor authentication is enforced for the targeted accounts.

## Common false positives
Service accounts with expired passwords, users who changed a password but still have an old one cached on a phone, and vulnerability scanners run by the internal red team with an approved ticket.
