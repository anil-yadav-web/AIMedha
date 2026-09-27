# Verification report

Recorded: **27 September 2026**. Environment: Windows, CPython 3.12.13, Node.js 22.16.0, npm 11.6.2. Local CPU inference with FastEmbed 0.8.1, `BAAI/bge-small-en-v1.5`, and FAISS. No Docker was installed or used.

## Completed checks

| Check | Result |
|---|---|
| Dataset | Exactly 10 synthetic notices and 31 source passages |
| Backend tests | **44 passed** |
| Frontend interaction tests | **6 passed** (Vitest/jsdom) |
| Retrieval evaluation | **24 of 24 passed** |
| Hit@1 / Hit@3 | **100% / 100%** across 17 supported questions |
| Recall@5 | **100%** of expected notice IDs |
| Unsupported queries | **7 of 7 rejected** |
| Explicit deadline revision checks | **2 of 2 passed**, with both source passages |
| Production TypeScript/Vite build | Passed |
| npm dependency audit | **0 known vulnerabilities** in the final locked dependencies |
| Live local HTTP smoke test | Passed |

Detailed query-level measurements: [evaluation-results.json](evaluation-results.json).

The live smoke test checks the homepage, readiness, all ten notices, the workshop materials query, source substring consistency, full notice API, revised deadline pair, unsupported weather question, validation, unknown notice handling and OpenAPI. Run it against a local or public service with `python -m scripts.smoke URL`.

Backend tests cover real embeddings and retrieval, exact evidence offsets, unique IDs and revision link validation, cached indexing, empty collections, unrelated deadlines, neutral handling of unlinked differences, explicit source references without optional relationship metadata, authorization, invalid/oversized requests, import persistence across restarts and friendly embedding/index failure responses.

Frontend tests cover example searches, source dialog opening/closing, focus restoration, keyboard submission, empty input, no-result behavior, both sides of a revision, and non-JSON upstream errors with retry. These use mocked network responses; real HTTP retrieval is covered separately.

One backend test dependency emits a Starlette/httpx deprecation warning. All tests pass. This is not an application request failure.

## Architecture and AI use

The React frontend and FastAPI backend deploy together as a native Python service. A local pretrained BGE encoder embeds document passages at initialization and questions during search. Normalized vectors are searched with FAISS and reranked with BM25. SQLite caches document embeddings; a bounded cache stores query vectors. No language-model completion, answer generation, web search or document-content execution is used.

Paragraph chunks retain exact source offsets, title, date, ID and filename metadata. The interface renders escaped source text and can open the complete notice. Retrieval thresholds and requested-detail checks reject weak or unsupported matches; a displayed score is not a probability of truth.

Explicit revision links or named source references plus revision wording identify updates. Same-topic, same-facet differences without a proven relationship are shown neutrally. Both earlier and newer passages remain available; the app never decides authority from date alone.

## Scope and remaining acceptance checks

- The 24-query dataset was used to calibrate relevance rejection. Its perfect score is **not a held-out generalization result**. Arbitrary queries and other collections can still produce incomplete evidence or false negatives.
- Actual browser layout, mobile viewport behavior, native dialog keyboard behavior and screen-reader operation have **not** been visually verified. The session's browser integration returned no available browser. Responsive CSS and jsdom tests are not substitutes for those checks.
- A GitHub Actions workflow is provided but has **not** run on GitHub in this session.
- Render's native deployment configuration is complete, but an account/repository connection is still required. **No cloud resource or public HTTPS URL has been provisioned or verified.**
- The Render blueprint selects a **paid Starter service and 1 GB persistent disk**. Review the displayed charges before applying it.
- Docker checks do not apply: Docker was explicitly excluded by the user.

Local URL: **http://127.0.0.1:8000** (available while the local Python process is running).

Public deployment URL: **pending**.

## Final manual demo after deployment

1. Load the public HTTPS URL on desktop and a narrow mobile viewport.
2. Search `What should I bring to the workshop?`; check title, date, exact materials passage and highlighting.
3. Open **View full notice**; close with the button and Escape and check keyboard focus.
4. Search `When is the registration deadline?`; verify the 15 September original and 20 September explicit update both remain visible.
5. Search `What is today's weather?`; verify the no-matching-information state.
6. Run `python -m scripts.smoke https://YOUR-SERVICE.onrender.com` and record the URL and result here.
