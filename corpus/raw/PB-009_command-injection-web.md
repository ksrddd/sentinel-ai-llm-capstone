---
doc_id: PB-009
title: Playbook - Web Application Command Injection Attempts
category: detection-playbook
version: 1.5
source: SentinelAI synthetic corpus - fictional Kestrel Analytics SOC handbook (original text written for this project)
last_reviewed: 2026-09-02
---
# Playbook: Web Application Command Injection Attempts

FICTIONAL POLICY NOTICE: The application names in this playbook are fictional and exist only within the SentinelAI demonstration.

## What the alert looks like
The web application firewall or application log shows request parameters containing shell metacharacters such as ;, |, &&, backticks or $( ) together with operating system commands like id, whoami, uname, cat /etc/passwd, or curl to an external host.

## Attempt versus success
Most of these alerts are attempts by automated scanners. Evidence of success includes: the HTTP response contains command output, the web server process spawns a shell, new files appear in the web root, or the server makes an outbound connection shortly after the request.

## Investigation steps
1. Record the full request line, parameters, source address and the response status and size.
2. Check whether the WAF blocked the request or only logged it.
3. On the server, look for child processes of the web server user created at the request time.
4. Review outbound connections from the server around the same time (PB-010).

## Recommended response
For blocked attempts with no sign of execution, record and close as an attempted attack with Low severity unless the asset tier raises the score. For any sign of execution, treat the server as compromised, request isolation per PB-016 and notify the application owner.
