---
doc_id: PB-006
title: Playbook - Privileged Account Compromise Indicators
category: detection-playbook
version: 2.0
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-12
---
# Playbook: Privileged Account Compromise Indicators

FICTIONAL POLICY NOTICE: Group names and procedures are fictional examples for the Kestrel Analytics demonstration.

## Why this is special
Administrative identities (domain admins, cloud root or owner roles, database administrators, backup operators) can disable defences and reach every system. Any credible sign of misuse is escalated to tier-2 regardless of the calculated score (see PB-003).

## Indicators
- An administrator account used outside its approved change window or from a workstation that is not a privileged access workstation.
- Additions to highly privileged groups, for example Windows event 4728 or 4732 for Domain Admins or Enterprise Admins.
- Creation of new administrator accounts or new access keys for a cloud root identity.
- Clearing of security event logs (event 1102) or disabling of the EDR agent by an admin account.

## Investigation steps
1. Confirm whether an approved change ticket exists for the activity.
2. Identify the originating host and check it for malware or remote-access tooling.
3. List every action the identity took in the past 72 hours.
4. Check whether other privileged identities were touched from the same origin.

## Recommended response (incident commander approval required)
Disable or rotate the affected credentials, remove unauthorised group memberships, and preserve logs before any cleanup (PB-015). Do not delete the suspicious accounts until evidence has been exported.
