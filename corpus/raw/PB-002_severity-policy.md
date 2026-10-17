---
doc_id: PB-002
title: Incident Severity Scoring Matrix
category: policy
version: 3.0
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-01
---
# Incident Severity Scoring Matrix

FICTIONAL POLICY NOTICE: This matrix belongs to the fictional organisation Kestrel Analytics. The weights are illustrative design choices for this project, not an industry standard.

## Principle
Severity is calculated, not guessed. Analysts and the AI copilot must use the same deterministic formula so that two people looking at the same facts reach the same priority. A language model may explain the result but may not override it.

## Factors
- Asset criticality tier from the asset catalogue: low = 1, medium = 2, high = 3, critical = 4. Unknown assets are scored as medium and flagged for review.
- Alert confidence: low = 1, medium = 2, high = 3.
- Observed impact: none = 0, suspected = 1, confirmed_limited = 2, confirmed_widespread = 3.
- Privileged account involved: add 2 points.

## Formula
score = criticality + confidence + (2 x impact) + privileged_bonus

## Bands
- score 0 to 4: Informational
- score 5 to 6: Low
- score 7 to 8: Medium
- score 9 to 10: High
- score 11 or more: Critical

## Overrides
Only a human incident commander may raise or lower a calculated severity, and the reason must be written into the case. A false-positive determination closes the case instead of lowering the score.

## Worked example
A high-confidence alert (3) on a critical database server (4) with suspected impact (1 x 2 = 2) and no privileged account gives 9, which is High.
