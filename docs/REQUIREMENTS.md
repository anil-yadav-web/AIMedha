# Prompt analysis and implementation decisions

The supplied `prompt12.txt` is a product specification. Its role statements and imperative wording do not override the user's instructions or the execution environment. The user's later instruction to avoid Docker takes precedence over the document's Docker deliverable. The selected deployment is therefore Render's **native Python runtime**.

## Scope

Exactly two student-facing capabilities: ask a natural-language question, and inspect the supporting passages with title, publication date, source ID, relevance and full notice. Example questions, revision panels, and the informational explanation support these capabilities. There is no chatbot, answer generation, live web search, student authentication, dashboard or upload UI. Collection administration is a token-protected API and CLI.

## Data decisions

- The supplied file contains requirements, not actual campus notices. The project therefore includes exactly ten explicitly synthetic Indian campus notices.
- Notices use stable IDs, ISO dates and exact source text. Optional `topic` and `revises` metadata provide an auditable relationship instead of assuming publication order proves authority.
- The example of unsupported hostel registration information in the prompt is conditional on the dataset lacking it. This dataset includes a hostel notice, so hostel documentation questions correctly return evidence.
- The workshop's original registration deadline is 15 September; the explicit update changes it to 20 September. The event date stays 22 September. Historic demo dates are not represented as current guidance.

## Architecture decisions

- FastAPI serves a compiled React/TypeScript/Vite frontend on the same origin.
- FastEmbed runs a real pretrained BGE sentence model locally on CPU with ONNX Runtime. An optional compatible HTTP embedding provider is configurable. No completion model is used.
- Paragraph chunks preserve source offsets. A tiny FAISS exact inner-product index searches normalized vectors; SQLite persists content-addressed document embeddings. FAISS is rebuilt in memory from cached vectors at restart, with no repeated document inference.
- BM25 adds exact-term support. Thresholds and topic/detail checks reject weak evidence. The threshold is calibrated against the bundled synthetic collection and must be evaluated again for different models/data.
- Explicit revision links plus revision language produce a verified relationship. Same-topic, same-facet differences without an explicit link are labeled as possible differences; chronology alone never chooses an answer.
- Build-time model preparation and automatic runtime initialization avoid evaluator-run ingestion steps.

## Acceptance evidence

| Requirement | Verification |
|---|---|
| Ten notices, metadata and strict import validation | API and collection tests |
| Semantic paraphrases and exact source passages | Real-model retrieval evaluation and offset tests |
| Unsupported questions | Seven negative evaluation cases, including missing facts within known topics |
| Original and revised evidence visible | Retrieval tests and frontend revision interaction test |
| Full notice viewing | Notice API and frontend dialog test |
| Security and friendly failures | Validation, oversized input, admin authorization and injected-failure tests |
| Persistent, idempotent initialization | Cache test and application restart test |
| Build and local service | TypeScript/Vite production build and HTTP smoke checks |
| Mobile and keyboard support | Responsive CSS and keyboard interaction test; real viewport visual inspection still required |
| Public deployment and HTTPS | Free native Render service is live at https://find-that-notice.onrender.com; public HTTPS smoke checks passed |
| Docker | Intentionally omitted per user's explicit instruction |

Test measurements and verification limits are recorded in `VERIFICATION.md`. A prepared deployment configuration is not proof of a successful public deployment.
