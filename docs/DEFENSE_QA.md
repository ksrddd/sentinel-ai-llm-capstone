# Defense preparation — likely questions and answers

**Why this architecture?**
Thin layers with one responsibility each (routers / services / repositories / LLM adapter / agent / RAG / eval).
Everything that must be reproducible — severity, evidence, citation metadata — is deterministic code; the LLM only
does language tasks. Static HTML + FastAPI avoids a build chain and keeps the demo reliable. The reference repo's
single-adapter idea is reused so swapping or mocking the model touches one file.

**Why BM25 with fixed chunks as the baseline?**
It is the naive, widely used lexical approach with no learned components and no tuning, so any improvement is
attributable to a design choice. Fixed windows are what a first implementation typically does.

**How do the metrics work?**
For each answerable query, Recall@3 = |relevant ∩ top-3| / |relevant|; MRR@5 = 1/rank of the first relevant
document in the top 5 (0 if none). Both are averaged over answerable queries only (recall is undefined with no relevant
documents). Abstention accuracy is over all queries: correct when the retriever abstains exactly when no relevant
document exists. Precision@3 divides by 3, so it is capped at 0.33–0.67 when a query has 1–2 relevant documents.

**What design choice improved, and how do you know?**
Retrieval configuration: chunking (fixed → heading-aware) and method (BM25 → hybrid MiniLM α=0.3). Selected on dev
by mean(Recall@3, MRR@5), thresholds tuned on dev, then compared with the baseline on the held-out test split:
Recall@3 0.679 → 0.750, MRR@5 0.696 → 0.729 (2 wins / 1 loss / 11 ties per query). It is a small effect on 14
queries; I would not claim significance.

**`dense-sbert-fixed` is better on test — why not use it?**
Choosing it now would be tuning on the test set. The selection rule was fixed in advance and applied to dev. The gap
shows high variance with tiny splits; the right fix is a larger dev set, not re-selecting.

**How do I reproduce a reported number?**
`pip install -e ".[dev,neural]"` then `python -m eval.run_retrieval_eval`. Compare with
`eval/results/retrieval_summary.json`; per-query rows are in `per_example.csv`. Dataset hash and seeds are in the
`meta` block. LSA uses `random_state=42`; BM25 and MiniLM inference are deterministic on CPU.

**How does the agent terminate safely?**
Hard limits: 6 model calls, 150 s wall clock, 3 consecutive invalid actions/tool errors, any transport error; also
duplicate calls are refused and at most 3 tool calls per turn are executed. Tools are read-only and allow-listed; the
worst a manipulated model can do is search playbooks or read synthetic history. Tests cover each stop condition.

**What happens when the LLM produces invalid output?**
JSON is extracted (code fences/prose tolerated) and validated with Pydantic; on failure the validator error is sent
back and the model retries (max 3 attempts). The report step also rejects citations not in the retrieved set. If
repair fails the API returns `502` with the stage and error — no placeholder report is fabricated. Extracted values
not present in the alert text are removed and listed as limitations.

**Native tool calling or not?**
`auto` mode tries native OpenAI-compatible tools first; if the proxy rejects them it switches to a documented JSON
action protocol and records that in the trace. The trace's `mode` field shows which one ran; it is never labelled
native when it was not. `python -m scripts.check_proxy` confirmed native tool calls on the class proxy, and every
end-to-end run used native mode (rate 1.000).

**How do you handle prompt injection?**
Untrusted content is tagged as data in prompts; injection phrases are detected and flagged for human review; but the
real control is architectural — no dangerous tools exist, arguments are schema-validated, severity is computed by
code, and citations are checked against retrieval results.

**What can the project NOT reliably do?**
Generalise to real logs; confirm compromise; correlate across multiple alerts; handle paraphrased values in
grounding (it drops them); rate impact perfectly (Gemma still under-rates confirmed execution on some holdout alerts); defend a
multi-user deployment (no auth). Retrieval still fails on vocabulary mismatch (Q26 "cut off the network" vs
"isolate") and entity-name distraction (Q02 hostname pulling the asset catalogue).

**Did you tune the LLM pipeline on the test set?**
The first run showed severity accuracy of 0.571 on the test split. Those failures were inspected, so the test split is
no longer blind after round 0; we say so explicitly. To still measure honestly, we wrote and labelled a new 16-alert
holdout set before each improvement round: v2 before r1, v3 before r2, v4 before r3. On these blind sets, severity
went 0.462 → 0.615 (r1), 0.923 → 0.923 (r2) and 0.615 → 0.846 (r3). A repeat run showed identical severities, so
the differences are not noise. All rounds are in `docs/EXPERIMENT_LOG.md`.

**Why derive confidence in code instead of asking the model?**
Asked for low/medium/high, Gemma hedged to "medium" on most alerts. Asked what kind of evidence the alert contains
(specific telemetry, anomaly, vague), it answered more consistently, and the mapping to PB-002 confidence is fixed
and testable. The same idea drives the yes/no "malicious outcome confirmed" flag, which can only raise impact.

**Why a separate embedding model when Gemma is required?**
Gemma is used for all reasoning and generation as required. Embeddings are a retrieval component; MiniLM is small,
CPU-friendly, documented, and evaluated against BM25 on the same data.
