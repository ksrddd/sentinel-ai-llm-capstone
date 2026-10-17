---
doc_id: PB-015
title: Evidence Preservation and Chain of Custody
category: process
version: 1.5
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-08-18
---
# Evidence Preservation and Chain of Custody

FICTIONAL POLICY NOTICE: These procedures are fictional and simplified for academic demonstration.

## Principle
Evidence must be collected before it is changed. Cleanup, reimaging and account deletion destroy information that the investigation and any later legal process may need.

## What to preserve
- Raw log exports for the relevant window, with the query used to produce them.
- EDR triage packages (process list, network connections, autoruns) and, where approved, memory images.
- Copies of suspicious emails in their original format.
- Firewall and proxy flow records.

## Chain of custody record
For each item record: what it is, where it came from, who collected it, when, the SHA-256 hash of the exported file, and where it is stored. Store evidence only in the restricted evidence share, never on personal drives or chat tools.

## Volatile data first
Collect memory and live network state before isolation or shutdown when the incident commander approves, because isolation can change the state of the machine.

## Retention
Evidence for closed cases is retained for one year in this fictional organisation, unless legal hold applies.
