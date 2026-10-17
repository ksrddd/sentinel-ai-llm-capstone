---
doc_id: PB-018
title: Asset Criticality Tiers and Catalogue Usage
category: reference
version: 1.1
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-07-30
---
# Asset Criticality Tiers and Catalogue Usage

FICTIONAL POLICY NOTICE: Tiers and hostnames are fictional; they are not drawn from any real organisation.

## Tiers
- critical: systems whose compromise would stop the business or expose regulated customer data, for example the customer records database, domain controllers and the payment gateway.
- high: important internal servers such as file servers, the source code repository and the HR application.
- medium: standard employee laptops and internal tools. Unknown assets default to this tier.
- low: test machines, kiosks and lab equipment without production data.

## Using the catalogue
The catalogue maps hostnames to tier, owner and data classification. The severity calculator reads the tier from the catalogue rather than from the alert, because alerts can be wrong about what a machine is.

## Naming convention in the demo environment
Hostnames start with a site code and a role, for example HQ-DC01 (domain controller), DB-CUST-01 (customer database), WEB-PORTAL-02 (public web portal), WS-FIN-114 (finance laptop) and LAB-TEST-07 (lab machine).

## Keeping it current
Asset owners must update the catalogue when systems change role. Mismatches discovered during an investigation are reported to IT asset management.
