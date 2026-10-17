---
doc_id: PB-014
title: Handling Alerts With Insufficient Evidence
category: process
version: 1.2
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-01
---
# Handling Alerts With Insufficient Evidence

FICTIONAL POLICY NOTICE: This procedure is part of a fictional SOC handbook created for academic use.

## The problem
Some alerts arrive with missing fields: no hostname, no user, a truncated message, or only a vague description such as "something looks odd". Guessing the missing details creates false confidence and can send responders in the wrong direction.

## Rules
1. State explicitly which fields are missing and why they matter.
2. Do not assign a confirmed incident type. Use "undetermined" until evidence supports a category.
3. Calculate severity only with the factors that are known; use the conservative defaults from PB-002 and mark the result as provisional.
4. Request the missing data from the log owner or the detection engineer.
5. Set the case to require human review.

## Useful follow-up requests
- The full raw event, not just the alert summary.
- Host and user context from the asset catalogue.
- Surrounding events from the same source within plus or minus 30 minutes.

## Closing
If the missing evidence cannot be obtained within five working days, close the case with the code INSUFFICIENT-DATA and record what would have been needed.
