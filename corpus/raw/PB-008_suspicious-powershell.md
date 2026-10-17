---
doc_id: PB-008
title: Playbook - Suspicious PowerShell and Script Interpreter Activity
category: detection-playbook
version: 1.7
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-05
---
# Playbook: Suspicious PowerShell and Script Interpreter Activity

FICTIONAL POLICY NOTICE: This guidance is part of a fictional SOC handbook created for academic use.

## Signals worth attention
- Command lines containing -EncodedCommand or -enc with long base64 strings.
- Download cradles such as Invoke-WebRequest or Net.WebClient followed by Invoke-Expression (IEX).
- Execution policy bypass combined with a hidden window style.
- PowerShell spawned by an office application, a browser or a scheduled task created minutes earlier.
- Script block logging (event 4104) showing obfuscated or reflective loading code.

## Investigation steps
1. Decode any encoded command in an offline analysis environment and record the decoded text in the case. Never execute it.
2. Identify the parent process and the user context.
3. Check whether the script reached out to a remote address; if so, pivot to PB-010.
4. Compare with the approved administration scripts list maintained by IT operations.

## Interpretation guidance
Administrators legitimately use encoded commands in some deployment tools. The combination of an unusual parent, a network download and execution in memory is far more suspicious than any single flag.

## Recommended response
Request host isolation through PB-016 when malicious intent is supported by decoded content or network evidence. Otherwise keep monitoring and ask the asset owner to confirm the activity.
