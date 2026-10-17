# Demo script (target 5 minutes)

> Status: script prepared. **The video has not been recorded yet** and no hosted deployment exists.
> Before recording: check `.env` (class proxy), run `python -m scripts.check_proxy`, then
> `uvicorn app.main:create_app --factory --port 8000`. Do a dry run of both alerts below; if Gemma output differs
> from what is described, narrate what actually appears — do not stage results.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:30 | Title bar of dashboard | "SentinelAI helps junior SOC analysts triage alerts. It is an assistant, not an autonomous responder; everything here is synthetic data for a fictional company." |
| 0:30–1:00 | Status pills; Playbooks tab list | "Gemma `gemma-4-E4B-it` through the class proxy at temperature 0. Knowledge base: 19 original playbooks with stable IDs. Retrieval: hybrid BM25 + MiniLM, chosen on a dev split." |
| 1:00–2:15 | Investigate → sample *VPN success after repeated failures* → Analyze | "The alert looks like brute force, but a login succeeded afterwards. Watch the agent trace: it called `search_playbooks`, then `calculate_severity`. Severity is computed by the PB-002 matrix — VPN-GW-01 is a high-tier asset — the model cannot change it." Point at score breakdown, grounded fields, evidence quoted verbatim. |
| 2:15–2:45 | Click a citation chip (e.g. PB-005) | "Every recommendation cites a playbook that was actually retrieved in this run. Citations outside the retrieved set are rejected and repaired, or the request fails with a validation error." |
| 2:45–3:30 | Sample *Vague alert with missing fields* → Analyze | Honest failure / insufficient evidence: "Only 'anomalous behaviour detected'. The system marks the type undetermined, lists missing fields, flags human review, and the severity is provisional with an unknown asset." Show limitations panel. |
| 3:30–3:50 | Sample *prompt-injection* (optional if time) | "The alert tells the model to run a shell command. There is no such tool; the call is rejected in the trace and the report is flagged for review." |
| 3:50–4:30 | Evaluation tab | "32 labelled queries, 16 dev / 16 test. Baseline BM25 with fixed chunks: test Recall@3 0.679, MRR@5 0.696. Selected hybrid: 0.750 and 0.729. Small gain on 14 answerable test queries — and one config looked better on test, but we did not re-select on test." Then: "End-to-end with live Gemma: the first run got severity right on only 57% of test alerts because the model hedged confidence to medium. We improved it in three rounds; before each round we wrote a new unseen holdout set. On those blind sets severity went 0.46→0.62, 0.92→0.92 and 0.62→0.85. The test split now scores 1.0, but we inspected its failures, so we do not claim that as blind." (Show docs/EXPERIMENT_LOG.md table.) |
| 4:30–5:00 | README architecture diagram | "Routers, services, repositories, one LLM adapter, a bounded agent with three read-only tools, and evaluation that reuses the same retriever code. Tests: 260 offline with a mocked LLM; live tests opt-in." |

## Backup plan
If the proxy is unavailable during recording, show the `503 LLM proxy is not configured` message honestly, then
demonstrate playbook search, the severity calculator and the evaluation tab (all work offline), and say the live
analysis segment could not be shown.

## Recording checklist
- [ ] `.env` not visible on screen; no keys in terminal history shown
- [ ] Browser zoom 110–125 % for readability
- [ ] Clear previous analyses (`data/sentinel.db`) for a clean History tab
- [ ] Upload video and paste link into the submission form (manual step)
