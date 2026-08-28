# UniAssist

UniAssist is a university knowledge assistant built on a **controlled, verified document corpus**. Administrators manually upload authoritative university documents; the system preserves provenance and verification state so answers can be grounded in trusted evidence.

UniAssist v1 does **not** depend on website crawling.

## Product vision

The goal is not to crawl everything and let AI decide what matters. The goal is to give UniAssist a curated set of authoritative documents and make the AI answer only from verified evidence.

## Architecture (v1)

```mermaid
flowchart TD
    Admin[Admin] --> Upload[Manual Document Upload]
    Upload --> Validation[Validation]
    Validation --> Provenance[Provenance Metadata]
    Provenance --> Store[Document Store]
    Store --> Processing[Document Processing]
    Processing --> ProcessedStore[Processed Content]
    ProcessedStore --> RAG[RAG Indexing]
    RAG --> Retrieval[Evidence Retrieval]
    Retrieval --> Groq[Groq Intelligence]
    Groq --> FutureAPI[Future API]
    FutureAPI --> Telegram[Telegram]
    FutureAPI --> MAX[MAX]
    Telegram --> Student[Student]
    MAX --> Student
```

### Future optional acquisition path

ScrapeAI remains in the repository as a **reusable, optional** acquisition component. It is not part of UniAssist v1.

```mermaid
flowchart LR
    AdminURL[Admin provides ONE URL] --> ScrapeAI[ScrapeAI single-page mode]
    Manual[Manual Upload] --> Ingestion[DocumentIngestionService]
    ScrapeAI -.->|future phase| Ingestion
```

**UniAssist v1 does not crawl the SUSU website.**

## Document lifecycle

```
UPLOAD
  ↓
DRAFT + PENDING
  ↓
future admin verification
  ↓
VERIFIED
  ↓
ACTIVE
```

New uploads default to `draft` + `pending`. A document becomes `active` only through explicit activation (Phase 3 CLI: `activate`).

## What is ScrapeAI?

ScrapeAI ([`src/uniassist/scrapeai/`](src/uniassist/scrapeai/)) is a reusable Scrapy-based acquisition engine. It is **frozen** and optional — useful for future projects or controlled single-page imports, but not required for UniAssist v1.

## Directory layout

```
Uniassist/
├── configs/susu/              # frozen SUSU connector config (optional acquisition)
├── data/
│   ├── raw/                   # immutable uploaded document blobs
│   ├── processed/             # derived normalized content (Phase 4)
│   └── metadata/
│       ├── documents.json     # corpus index
│       ├── processing.json    # processing results index
│       └── rag/               # vector index + indexing metadata
├── src/uniassist/
│   ├── core/                  # shared utilities (hashing)
│   ├── documents/             # v1 ingestion + store
│   ├── processing/            # document processing (MinerU, text)
│   ├── rag/                   # chunking, embeddings, retrieval
│   ├── ai/                    # Groq answer generation + verification
│   ├── api/                   # FastAPI application layer (Phase 7)
│   └── scrapeai/              # optional acquisition (frozen)
├── frontend/                  # React admin dashboard (Phase 8)
└── tests/
```

## Development phases

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Project foundation | Done |
| 1 | ScrapeAI acquisition engine | Done (frozen) |
| 2 | SUSU connector (optional) | Done (frozen) |
| 3 | Document ingestion + provenance store | Done |
| 4 | MinerU document processing | Done |
| 5 | RAG evidence retrieval foundation | Done |
| 6 | Groq answer generation + verification | Done |
| 6.5 | Intelligence quality + verification hardening | Done |
| 7 | FastAPI application API | Done |
| 8 | Admin document UI | Done |
| 9 | Telegram bot | Done |
| 10 | Appwrite Cloud persistence | Done |
| 11 | MAX integration | Not started |

## Getting started

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Upload a document

```bash
python -m uniassist.documents.cli upload path/to/rules.pdf \
  --title "Student Rules" \
  --source "SUSU regulations office" \
  --effective-date 2025-09-01 \
  --version "2025-1"
```

### List and inspect

```bash
python -m uniassist.documents.cli list
python -m uniassist.documents.cli show <document_id>
```

### Activate after review

```bash
python -m uniassist.documents.cli activate <document_id>
```

### Process an approved document

Only `active` + `verified` documents are processed in the production workflow.

```bash
python -m uniassist.processing.cli process <document_id>
python -m uniassist.processing.cli show <document_id>
python -m uniassist.processing.cli list
```

**Raw documents are immutable.** Files in `data/raw/` are never modified. Processed output in `data/processed/{document_id}/{source_sha256}/` is a derived artifact. The original source document and `DocumentRecord` remain authoritative for provenance.

#### Processing routing

| Source type | Processor | Notes |
|-------------|-----------|-------|
| PDF | MinerU | Requires MinerU (Python 3.10-3.13). Set `MINERU_EXECUTABLE` to an isolated CLI when UniAssist uses Python 3.14+. |
| TXT | TextProcessor | Direct UTF-8 extraction, no MinerU |
| DOCX | Deferred | Unsupported until MinerU advertises reliable DOCX support |

For a Python 3.14 UniAssist environment, keep MinerU isolated and configure it
without activating that environment for each run:

```bash
python3.12 -m venv .venv-mineru
.venv-mineru/bin/python -m pip install --upgrade pip
.venv-mineru/bin/python -m pip install 'mineru[pipeline]'
MINERU_EXECUTABLE="$PWD/.venv-mineru/bin/mineru"
```

#### Normalized output format

`data/processed/{document_id}/{source_sha256}/normalized.json`:

```json
{
  "document_id": "...",
  "title": "...",
  "source": "...",
  "source_url": "...",
  "source_sha256": "...",
  "processor": "text",
  "processor_version": "1.0.0",
  "processed_at": "2026-01-01T00:00:00+00:00",
  "blocks": [
    {"text": "...", "page_number": 1, "section": "paragraph_1"}
  ]
}
```

Provenance chain:

```
Answer → RetrievedChunk → normalized content → DocumentRecord → raw document → source
```

### Index and search evidence (Phase 5)

**Phase 5 retrieves evidence but does not generate answers.**

Only `active` + `verified` documents with completed processing are indexed.

```bash
# Index all eligible processed documents
python -m uniassist.rag.cli index

# Index one document
python -m uniassist.rag.cli index <document_id>

# Search for evidence
python -m uniassist.rag.cli search "How do I request academic leave?"

# Index statistics
python -m uniassist.rag.cli stats
```

#### RAG architecture

```mermaid
flowchart TD
    Processed[data/processed/] --> Chunker[Chunker]
    Chunker --> Embed[EmbeddingProvider]
    Embed --> VectorStore[VectorStore]
    VectorStore --> Retriever[Retriever]
    Query[User Query] --> Retriever
    Retriever --> Evidence[RetrievedChunk[]]
```

1. **Processed documents** — normalized JSON from Phase 4
2. **Chunking** — deterministic, rule-based splitting with configurable size/overlap
3. **Embeddings** — provider abstraction (`DeterministicEmbeddingProvider` by default)
4. **Vector storage** — local JSON-backed store with cosine similarity
5. **Retrieval** — ranked `RetrievedChunk` results with full provenance
6. **Eligibility filtering** — DRAFT, PENDING, REJECTED, and ARCHIVED documents are excluded

Each `RetrievedChunk` preserves `document_id`, `chunk_id`, `source_sha256`, document version, source, source_url, page, section, and similarity score — everything needed for citation and verification.

### Ask a grounded question (Phase 6)

**Phase 6 generates and verifies answers from retrieved evidence. It does not replace the document corpus as the source of truth.**

Requires `GROQ_API_KEY` (see `.env.example`) for live answers. Retrieval embeddings are local.

```bash
export GROQ_API_KEY=your_key_here

python -m uniassist.ai.cli ask "Can I take academic leave?"
python -m uniassist.ai.cli ask "Can I take academic leave?" --mock
```

Pipeline:

```
Question → Retriever → RetrievedChunk[] → Groq → CandidateAnswer → VerificationEngine → VerifiedAnswer
```

- Answers are generated only from retrieved evidence
- Claims are verified individually
- Unsupported claims, invalid citations, and contradictions cause refusal
- DRAFT / PENDING / ARCHIVED documents are excluded from verification
- Retrieved document text is treated as data, not instructions (prompt-injection resistant prompts)

### Phase 6.5 — Intelligence quality (development vs production)

Phase 6.5 hardens retrieval and verification without changing the core architecture.

**Development and production retrieval:**

- `DeterministicEmbeddingProvider` — hash-based local embeddings (no API key)
- `DeterministicSemanticVerifier` — keyword-overlap claim support checks
- Groq chat for live answer generation (`GROQ_API_KEY`)
- Vector index manifest tracks provider, model, and dimension
- Retrieval supports `min_score` thresholds and per-document diversity limits
- Layered verification: structural → evidence → citation → eligibility → semantic → contradiction
- Model confidence is never treated as proof of evidence validity

```bash
python -m uniassist.rag.cli rebuild
python -m uniassist.rag.cli search "academic leave" --min-score 0.35
```

**Refusal behavior**: UniAssist refuses when there is no relevant evidence, claims are unsupported, citations are invalid, or evidence conflicts across active documents. Out-of-domain questions must not be answered from model knowledge alone.

**Groq integration test** (optional, not part of normal CI):

```bash
export UNIASSIST_RUN_GROQ_INTEGRATION=1
export GROQ_API_KEY=your_key_here
pytest tests/e2e/test_real_fastapi_e2e.py -v
```

### REST API (Phase 7)

Phase 7 exposes UniAssist through a thin FastAPI application layer. Routes delegate to existing services — no business logic is duplicated in the API package.

Start the development server:

```bash
uvicorn uniassist.api.app:create_app --factory --reload
```

Open interactive docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

**Endpoints**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Simple health check |
| GET | `/status` | Safe system status (no secrets) |
| POST | `/ask` | Grounded question answering |
| POST | `/documents/upload` | Upload a document (multipart) |
| GET | `/documents` | List documents (optional filters) |
| GET | `/documents/{id}` | Document metadata + processing/index status |
| POST | `/documents/{id}/activate` | Activate a draft document |
| POST | `/documents/{id}/process` | Process an eligible document |
| POST | `/documents/{id}/index` | Index an ACTIVE + VERIFIED document |

**Example — ask a question**

```bash
curl -s http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Can I take academic leave?"}'
```

**Example — upload a document**

```bash
curl -s http://127.0.0.1:8000/documents/upload \
  -F file=@rules.txt \
  -F title="Student Rules" \
  -F source="Admin upload"
```

**Environment variables**

| Variable | Purpose |
|----------|---------|
| `UNIASSIST_PROJECT_ROOT` | Project root containing `data/` (default: current directory) |
| `UNIASSIST_CORS_ORIGINS` | Comma-separated CORS allowlist (empty = disabled) |
| `UNIASSIST_MAX_QUESTION_LENGTH` | Maximum `/ask` question length (default: 2000) |
| `GROQ_API_KEY` | Required for live Groq answers |

CORS is **not** enabled by default. Set `UNIASSIST_CORS_ORIGINS` explicitly for local frontends.

Every response includes an `X-Request-ID` header. Clients may supply their own with the `X-Request-ID` header (8–64 alphanumeric characters).

### Admin UI (Phase 8)

Phase 8 adds a local React admin dashboard in `frontend/` for the complete document-management workflow:

```text
UPLOAD → REVIEW → ACTIVATE → PROCESS → INDEX → VERIFY CURRENT STATE
```

**Development workflow**

Terminal 1 — API:

```bash
export UNIASSIST_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
uvicorn uniassist.api.app:create_app --factory --host 127.0.0.1 --port 8001 --reload
```

Terminal 2 — Admin UI:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

The frontend reads `VITE_API_URL` (or `VITE_API_BASE_URL`) from `frontend/.env` (default: `http://127.0.0.1:8001`). Restart `npm run dev` after changing frontend environment variables.

The UI consumes the Phase 7 API only. FastAPI remains the single source of truth for lifecycle, validation, and processing.

**Frontend commands**

```bash
cd frontend
npm run build
npm test
```

### Groq + Telegram end-to-end

UniAssist uses Groq for chat generation and local hash embeddings for retrieval. It does not download models or install GPU software.

**Port layout (avoid conflicts)**

| Service | URL |
| --- | --- |
| UniAssist FastAPI | `http://127.0.0.1:8001` |
| React admin (optional) | `http://localhost:5173` |

**1. Configure environment**

Copy `.env.example` to `.env` (`.env` is git-ignored) and set:

```bash
UNIASSIST_CHAT_PROVIDER=groq
GROQ_API_KEY=<required for Groq chat>
GROQ_CHAT_MODEL=openai/gpt-oss-20b
UNIASSIST_API_URL=http://127.0.0.1:8001
TELEGRAM_BOT_TOKEN=<your token>
UNIASSIST_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

**2. Run the local stack**

Terminal 1 — UniAssist API:

```bash
export UNIASSIST_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
uvicorn uniassist.api.app:create_app --factory --host 127.0.0.1 --port 8001 --reload
```

Terminal 2 — Telegram bot:

```bash
python -m uniassist.telegram.bot
```

**Architecture**

```text
Telegram → FastAPI :8001 /ask → RAG → Groq → Verification → Telegram
```

Check status:

```bash
curl http://127.0.0.1:8001/status
```

**Optional live integration tests**

```bash
UNIASSIST_RUN_GROQ_INTEGRATION=1 pytest tests/e2e/test_real_fastapi_e2e.py -v
UNIASSIST_RUN_TELEGRAM_INTEGRATION=1 pytest tests/telegram/test_telegram_integration.py -v
```

Both skip automatically when the required services or credentials are unavailable.

### Phase 10 — End-to-end validation

Phase 10 adds offline-safe test hardening plus optional **real** Groq/FastAPI validation.

**Default suite (offline, no external services):**

```bash
python -m pytest -v
ruff check src tests
```

Must show **0 failures** without Groq, Telegram, internet, MinerU, or live ScrapeAI.

**Synthetic E2E corpus:** `tests/fixtures/e2e/` (4 university-style test documents, clearly marked as fixtures)

**Optional live Groq E2E:**

```bash
export UNIASSIST_RUN_GROQ_INTEGRATION=1
export GROQ_API_KEY=your_key_here
pytest tests/e2e/test_real_fastapi_e2e.py -v
```

Skips with a clear reason if Groq is not configured.

**Optional live Telegram test** (calls `getMe` only, no user spam):

```bash
export UNIASSIST_RUN_TELEGRAM_INTEGRATION=1
export TELEGRAM_BOT_TOKEN="..."
pytest tests/telegram/test_telegram_integration.py -v
```

**Manual Telegram E2E** (requires real bot token):

```bash
# Terminal 1: FastAPI on :8001
# Terminal 2:
export TELEGRAM_BOT_TOKEN="..."
export UNIASSIST_API_URL=http://127.0.0.1:8001
python -m uniassist.telegram.bot
```

### Telegram student bot (Phase 9)

Phase 9 adds a production-structured Telegram client that consumes the existing FastAPI `/ask` endpoint only. The bot does **not** implement RAG, Groq calls, verification, or document processing — it is a thin client boundary.

**Architecture**

```text
Telegram Student → Telegram Bot → FastAPI /ask → AnswerPipeline → Telegram Bot → Student
```

Future channels (for example MAX in Phase 10) should reuse the same `/ask` contract.

**Environment variables**

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (required to run the bot) |
| `UNIASSIST_API_URL` | Base URL for UniAssist API (example: `http://127.0.0.1:8001`) |
| `TELEGRAM_RATE_LIMIT_PER_MINUTE` | Per-user in-memory rate limit (default: 10) |
| `TELEGRAM_REQUEST_TIMEOUT_SECONDS` | FastAPI client timeout (default: 60) |
| `TELEGRAM_NETWORK_TIMEOUT_SECONDS` | Telegram connection/read/write timeout (default: 30) |
| `TELEGRAM_POLL_TIMEOUT_SECONDS` | Telegram long-poll timeout (default: 30) |
| `TELEGRAM_BOOTSTRAP_RETRIES` | Telegram startup retries after transient network failures (default: 3) |
| `TELEGRAM_MAX_MESSAGE_LENGTH` | Telegram message split threshold (default: 4096) |
| `UNIASSIST_RUN_TELEGRAM_INTEGRATION` | Set to `1` to enable optional live Telegram integration tests |

**Bot startup (long polling)**

Terminal 1 — API:

```bash
export UNIASSIST_CORS_ORIGINS=http://localhost:5173
uvicorn uniassist.api.app:create_app --factory --host 127.0.0.1 --port 8001 --reload
```

Terminal 2 — Telegram bot:

```bash
export TELEGRAM_BOT_TOKEN="..."
export UNIASSIST_API_URL="http://127.0.0.1:8001"
python -m uniassist.telegram.bot
```

**Supported commands**

- `/start` — welcome message
- `/help` — usage and safety guidance
- `/status` — UniAssist online/offline via `/health`
- normal text — grounded question answering via `/ask`

**Rate limiting and privacy**

Rate limiting is an in-memory, per-user sliding window suitable for single-process Phase 9 deployment. It is not distributed and resets when the bot process restarts.

The bot stores only lightweight in-memory session metadata (`session_id`, `last_request_id`, timestamp) for operational tracing. It does not persist full Telegram message history. Logs avoid bot tokens, authorization headers, and full student messages.

**Development and testing**

Telegram tests mock the API client and Telegram update objects. CI does not require Telegram credentials or a live FastAPI server.

```bash
pytest tests/telegram -v
```

Optional live Telegram integration tests:

```bash
export TELEGRAM_BOT_TOKEN="..."
export UNIASSIST_RUN_TELEGRAM_INTEGRATION=1
pytest tests/telegram/test_telegram_integration.py -v
```

**Manual test plan**

1. Start the API and bot as shown above.
2. Send `/start`, `/help`, and `/status`.
3. Ask: `How can I apply for academic leave?`
4. Ask an unrelated question.
5. Ask a question with insufficient evidence and confirm grounded refusal.
6. Trigger a long answer and confirm safe splitting.
7. Send rapid repeated questions to trigger rate limiting.

Webhooks, Redis, and student document uploads are intentionally out of scope for Phase 9.

### Phase 10 — Appwrite Cloud persistence

UniAssist can run with local filesystem persistence (default) or Appwrite Cloud for production.

**Backend selection**

```bash
# Local development / tests (default)
UNIASSIST_STORAGE_BACKEND=local

# Production
UNIASSIST_STORAGE_BACKEND=appwrite
# plus APPWRITE_* variables — see docs/appwrite.md
```

**Migration from local data**

```bash
python -m uniassist.migrations.appwrite --dry-run
python -m uniassist.migrations.appwrite
```

**Optional live Appwrite integration tests**

```bash
export UNIASSIST_RUN_APPWRITE_INTEGRATION=1
# configure APPWRITE_* credentials
pytest tests/integration/appwrite -v
```

Full setup guide: [`docs/appwrite.md`](docs/appwrite.md). Filesystem audit: [`docs/persistence-audit.md`](docs/persistence-audit.md).

### Run tests

```bash
pytest -v
ruff check src tests
```

## License

Not yet specified.
