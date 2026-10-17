---
doc_id: PB-005
title: Playbook - Suspicious Successful Sign-in and Account Takeover
category: detection-playbook
version: 1.9
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-10
---
# Playbook: Suspicious Successful Sign-in and Account Takeover

FICTIONAL POLICY NOTICE: This playbook belongs to the fictional Kestrel Analytics SOC and is used only for academic demonstration.

## Indicators
- A successful sign-in from a country or network the user has never used before.
- Two successful sign-ins from locations that are physically impossible to travel between in the elapsed time ("impossible travel").
- A successful sign-in immediately after many failures from the same origin.
- A new device registration or a new mailbox forwarding rule created shortly after sign-in.

## Investigation steps
1. Compare the sign-in location, autonomous system and user agent with the user's last 30 days of history.
2. Check whether multi-factor authentication was satisfied and by which method.
3. Look for post-login activity: mailbox rules, file downloads, password changes, new OAuth consents.
4. Contact the user through a known-good channel (not by replying to the session) to confirm whether they signed in.

## Interpretation guidance
A sign-in from a new location alone is weak evidence; travel and corporate VPN egress points explain many cases. Treat it as confirmed takeover only when the user denies the activity or when malicious post-login actions are observed.

## Recommended response
Revoke active sessions and reset credentials when the user denies the sign-in. Remove any malicious forwarding rules. If the account is privileged, continue with PB-006.
