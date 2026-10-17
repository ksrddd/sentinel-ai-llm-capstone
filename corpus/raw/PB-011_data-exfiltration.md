---
doc_id: PB-011
title: Playbook - Data Exfiltration Indicators
category: detection-playbook
version: 2.0
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-14
---
# Playbook: Data Exfiltration Indicators

FICTIONAL POLICY NOTICE: Volumes and data classifications are fictional examples for academic purposes.

## Indicators
- Outbound transfer from a single host far above its 30-day baseline, for example more than 2 GB to an unfamiliar destination in under an hour.
- Uploads to personal cloud storage or file-sharing services from servers that hold classified data.
- Archive creation (zip, 7z, rar) of large directories shortly before a transfer.
- Database export commands or bulk queries returning unusually many rows.

## Investigation steps
1. Establish exactly how much data left, when, from which host, and to which destination.
2. Identify the user and process responsible.
3. Determine the data classification of the source system using the asset catalogue (PB-018).
4. Check for prior compromise signals on the same host such as account takeover or malware.

## Interpretation guidance
Backups, replication jobs and approved migrations generate large transfers. Confirm with the asset owner whether a scheduled job explains the volume before declaring exfiltration. Volume alone does not prove theft.

## Recommended response
Escalate immediately to tier-2 when customer records may be involved (PB-003). With approval, block the destination and preserve network flow records (PB-015). Legal and privacy teams decide on notification, not the SOC.
