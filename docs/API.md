# API reference

The API and UI share an origin. All source text is returned as plain JSON strings. There is no answer-generation endpoint. Interactive documentation is available at `/docs`, with OpenAPI at `/openapi.json`.

## GET /api/health

Returns HTTP 200 when initialization is complete:

```json
{"status":"ready","notice_count":10,"embedding_provider":"fastembed"}
```

The process does not accept normal traffic until the model and index initialize. Startup failure prevents healthy deployment.

## POST /api/search

```json
{"query":"What should I bring to the workshop?"}
```

`query` is a string of 1–500 characters before whitespace normalization. The maximum request body is 4096 bytes. Example response shape (scores below are illustrative):

```json
{
  "query": "What should I bring to the workshop?",
  "found": true,
  "results": [{
    "notice_id": "notice_01",
    "title": "AI Tools Workshop for Students",
    "publication_date": "2026-09-01",
    "category": "Workshop",
    "source_filename": "Notice_01.txt",
    "chunk_id": "notice_01:1",
    "passage": "Participants must bring their laptop, college ID card and a notebook. Please install a modern web browser before arriving.",
    "start": 160,
    "end": 282,
    "score": 0.6539,
    "highlights": [[24, 68]],
    "passages": []
  }],
  "conflicts": []
}
```

Actual `start`/`end`, scores and highlights depend on source text and model. Offsets are Unicode code-point indices, end-exclusive. The `passages` array contains the grouped evidence objects (up to three) including the top passage. Each result repeats its highest-scoring passage at the top level for convenience. `score` is a relevance score, not factual confidence.

`conflicts` entries contain `kind`, `message`, `earlier` and `newer`; both evidence objects have the same shape as a passage. Kinds are `explicit_revision`, `possible_revision`, `possible_conflict`. Linked counterparts may appear even when their individual score is below the threshold or beyond `TOP_K`, so that older evidence remains visible.

Unsupported response:

```json
{"query":"What is today's weather?","found":false,"results":[],"conflicts":[],"message":"No matching information found."}
```

If there are no available notices, the message is `No notices are currently available.` The normal dataset and import contract require exactly ten.

## GET /api/notices

Returns `{"notices":[...]}` containing all notices with complete content and metadata.

## GET /api/notices/{notice_id}

Returns one notice object. Unknown IDs return 404. This endpoint never reads a path supplied by the client; IDs are dictionary keys into the active validated collection.

## POST /api/index

Protected by `Authorization: Bearer <ADMIN_TOKEN>`. Disabled with HTTP 503 if no server admin token is configured. Missing or incorrect authorization returns 401. Submit:

```json
{"notices":["Exactly ten Notice objects, using the schema in README.md"]}
```

The above shows the wrapper only; array elements must be objects, not strings. IDs must be unique and revision links must identify earlier existing notices. Request size is limited to 300,000 bytes. Validation errors return 422. A concurrent import returns 409.

Success:

```json
{"status":"indexed","notice_count":10,"chunk_count":31}
```

The actual chunk count depends on the submitted paragraphs. Imports build a candidate index, persist the new collection atomically, then switch the running service. Index/embedding failure keeps the old collection active and returns a friendly 503. The imported collection survives restarts when `INDEX_DIR` is on persistent storage.

## Errors

Validation and unhandled errors use `{"message":"..."}`; FastAPI HTTP errors use `{"detail":"..."}`. The frontend accepts either format. Client-facing errors never contain internal exception text, paths, credentials or stack traces. Server logs retain diagnostics for operators.
