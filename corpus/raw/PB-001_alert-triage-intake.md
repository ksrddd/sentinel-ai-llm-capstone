---
doc_id: PB-001
title: Alert Triage Intake Procedure
category: process
version: 2.1
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-01
---
# Alert Triage Intake Procedure

FICTIONAL POLICY NOTICE: This document describes procedures of a fictional organisation, Kestrel Analytics. It is written for academic demonstration and is not a universal security standard.

## Purpose
This procedure tells a tier-1 analyst what to do in the first fifteen minutes after an alert lands in the queue. The goal is to turn a raw detection into a documented case with a clear owner, an initial classification and a list of open questions.

## Intake steps
1. Acknowledge the alert in the case tracker so that no other analyst duplicates the work.
2. Record the detection source (EDR, SIEM correlation rule, firewall, mail gateway, DNS resolver, web application firewall) and the rule name.
3. Copy the raw event fields into the case without editing them. Normalised fields are useful, but the raw record is the evidence.
4. Identify the affected asset by hostname and look up its criticality tier in the asset catalogue (see PB-018).
5. Identify any user account involved and note whether it is a privileged account.
6. Write down which facts are observed in the telemetry and which are assumptions.

## Initial classification
Pick the closest incident category from the playbook library. If two categories fit, record both and choose the one with the higher potential impact for routing. An alert that does not match any playbook should be routed to the insufficient-evidence procedure (PB-014) rather than forced into a category.

## What not to do at intake
Do not run active scans against external addresses, do not contact the suspected attacker infrastructure, and do not reimage or power off a machine during intake. Containment decisions follow PB-016 and require the approvals described there.

## Output of intake
At the end of intake the case must contain: the alert category, the affected asset and its tier, the involved identities, a preliminary severity calculated with the matrix in PB-002, and a list of missing information.
