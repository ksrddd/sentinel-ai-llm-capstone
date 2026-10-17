---
doc_id: PB-010
title: Playbook - Unusual Outbound Connections and Possible Command-and-Control
category: detection-playbook
version: 1.8
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-08
---
# Playbook: Unusual Outbound Connections and Possible Command-and-Control

FICTIONAL POLICY NOTICE: Detection thresholds here are fictional values chosen for the SentinelAI demonstration network.

## Signals
- Regular, evenly spaced connections (beaconing) from one host to one external address, for example every 60 seconds with small payloads.
- Connections to rare destinations that no other host in the organisation contacts.
- Traffic on unusual ports such as 4444, 8443 to residential ranges, or raw TCP to addresses without a DNS lookup.
- A server that normally only receives traffic suddenly initiating outbound sessions.

## Investigation steps
1. Identify the process that owns the connection using EDR network telemetry.
2. Measure interval regularity and bytes sent versus received.
3. Check whether any other internal host talks to the same destination.
4. Review the host for recent malware or script alerts (PB-007, PB-008).

## Interpretation guidance
Software update agents, telemetry clients and monitoring tools also beacon. Confirm the owning process and its signer before concluding that the traffic is malicious. Large outbound volumes belong to the exfiltration playbook (PB-011).

## Recommended response
With approval, block the destination at the egress firewall and isolate the host if the owning process is unknown or malicious. Do not probe or scan the external address.
