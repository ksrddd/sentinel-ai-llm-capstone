# SentinelAI architecture

![architecture](architecture.png)

## Layers

| Layer | Module | Responsibility | Never does |
|---|---|---|---|
| Routers | `app/api/routes.py` | HTTP validation, status codes (422/400/404/502/503) | business logic |
| Services | `app/services/analysis.py`, `severity.py`, `grounding.py` | orchestration, policy, anti-fabrication | talk HTTP |
| Repositories | `app/repositories/` | SQLite analyses + incident history, asset catalogue | accept raw SQL |
| LLM adapter | `app/llm/client.py` | the **only** code that calls the model | decide severity |
| Agent | `app/agent/loop.py`, `tools.py` | model-selected tool execution under bounds | write, scan, execute |
| RAG | `app/rag/` | corpus parsing, chunking, BM25, embeddings, retriever, index | call the LLM |
| Evaluation | `eval/` | reproducible experiments using the same retriever code | tune on test |

`app/core/container.py` builds the object graph once at start-up; `create_app(settings, llm)` lets tests inject a
scripted fake LLM.

## Request sequence (`POST /api/analyze`)

```
Browser → routes.analyze → AnalysisService.analyze
  1  generate_validated(extraction prompt, ExtractedIncident)      ≤3 LLM calls
  2  ground_extraction(...) + detect_injection(...)                deterministic
  3  AgentRunner.run(...)                                           ≤6 LLM calls, 150 s
       └ ToolRegistry.execute(name, args)   validate → run read-only tool → <tool_result> back to model
  4  enforce search_playbooks / calculate_severity if missing or inconsistent
  5  generate_validated(report prompt, ReportDraft, citation check) ≤3 LLM calls
  6  assemble IncidentReport (severity/evidence/citations from code) → SQLite → JSON response
```
Worst case: 12 model calls per analysis.

## Trust boundaries

* **Untrusted:** alert text, retrieved playbook text, tool results, model output.
* Alert and excerpts are wrapped in `<untrusted_alert>`, `<playbook_excerpt>`, `<tool_result>` tags and the system
  prompts state that content inside is data.
* Model output is never executed. Tool names go through an allow-list; arguments through Pydantic models with
  `extra="forbid"`, bounded integers, enumerations and a hostname regex.
* The only side effect of an analysis is one row in the local SQLite `analyses` table.

## Retrieval design

* Chunking: `section` = one chunk per `##` heading, prefixed with `title. heading.` (≤220 words, 30 overlap);
  `fixed` = 120-word windows with 20 overlap (baseline). Chunk IDs: `PB-004#c02` (stable, deterministic).
* The repeated "FICTIONAL POLICY NOTICE" banner is removed from indexed text (kept for display).
* Scores: BM25 (k1 1.5, b 0.75); cosine on L2-normalised MiniLM embeddings; hybrid
  `α·cos + (1−α)·bm25/(bm25+8)` — the saturating transform keeps the lexical part in 0..1 so one abstention
  threshold works across queries.
* Document ranking = best chunk per document; abstain when the top score < dev-tuned threshold.

## Severity policy (PB-002)

`score = tier(1–4) + confidence(1–3) + 2·impact(0–3) + 2·privileged`;
bands: 0–4 Informational, 5–6 Low, 7–8 Medium, 9–10 High, ≥11 Critical. Asset tier comes from
`data/synthetic/assets.json`; unknown assets default to *medium* and are flagged.

## Agent protocols

* **native** — OpenAI `tools=[...]`, `tool_choice="auto"`, assistant `tool_calls` echoed back with `role: tool` results.
* **json** — documented text protocol (`{"action":"call_tool",...}` / `{"action":"finish",...}`), used only if the
  proxy rejects tool definitions (`auto` mode switches and records a trace step). This is *not* presented as native
  function calling.

## Why this architecture

Plain FastAPI + static JS keeps the demo dependency-light and reviewable; one adapter module isolates the class proxy;
deterministic code owns everything that must be reproducible (severity, citations metadata, evidence), and the LLM
is used only where language understanding is needed (extraction, tool choice, prose).
