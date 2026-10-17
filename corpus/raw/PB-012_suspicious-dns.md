---
doc_id: PB-012
title: Playbook - Suspicious DNS Activity, Tunnelling and Generated Domains
category: detection-playbook
version: 1.6
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-08-30
---
# Playbook: Suspicious DNS Activity, Tunnelling and Generated Domains

FICTIONAL POLICY NOTICE: This playbook is fictional and was written for the SentinelAI capstone project.

## Signals
- Very long query names or subdomains made of base32 or hex-looking strings, often to a single parent domain (possible DNS tunnelling).
- High volumes of TXT or NULL record queries from a workstation.
- Many lookups for random-looking domains that return NXDOMAIN (possible domain generation algorithm malware).
- Lookups of newly registered domains shortly after a user opens an attachment.

## Investigation steps
1. Calculate query volume, average label length and character entropy for the parent domain.
2. Identify the process on the host that issued the queries.
3. Check whether other hosts query the same parent domain.
4. Correlate with endpoint alerts on the same host.

## Interpretation guidance
Content delivery networks, anti-virus reputation services and some telemetry tools generate long, random-looking names. Compare against the allow list of known services before concluding tunnelling.

## Recommended response
With approval, sinkhole the parent domain on the internal resolver and isolate the host if a malicious process is identified.
