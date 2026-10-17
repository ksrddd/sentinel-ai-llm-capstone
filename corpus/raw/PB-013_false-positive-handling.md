---
doc_id: PB-013
title: False-Positive Determination and Benign Activity Closure
category: process
version: 1.3
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-08-20
---
# False-Positive Determination and Benign Activity Closure

FICTIONAL POLICY NOTICE: Closure codes in this document are fictional and specific to the SentinelAI demonstration.

## When an alert is a false positive
An alert is a false positive when the detection logic fired but the underlying activity is authorised or harmless. Examples: an approved penetration test with a ticket number, a backup job causing a traffic spike, an administrator running a documented maintenance script, or a scanner owned by the vulnerability management team.

## Evidence required to close
Closing as benign requires positive evidence, not just the absence of bad signs. Acceptable evidence: a change or test ticket matching time and source, written confirmation from the asset owner, or a documented allow-list entry. Record the evidence in the case.

## Closure codes
- FP-RULE: the rule logic is wrong; open a tuning request.
- FP-AUTH: the activity was authorised.
- BENIGN-TP: the rule worked correctly but the activity was harmless.

## Tuning feedback
Repeated false positives from the same rule should be reported to detection engineering with examples. Never disable a rule from the analyst console.

## Caution
If any part of the evidence is inconsistent with the benign explanation, keep the case open and follow the relevant detection playbook.
