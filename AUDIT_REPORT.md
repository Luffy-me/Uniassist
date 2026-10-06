# UniAssist: Research-Readiness Audit

Scope: read-only audit of this repository to judge whether it can support a research evaluation report. The only file written is this one. I did not call Groq, Telegram or Appwrite, and I did not touch `.env` or secrets.

State audited: the working tree as it is now, which includes the fixes I made earlier in this session (Unicode-aware verification, auth on read routes, Appwrite error handling, the DOCX reader, optional LLM verification and so on). Line numbers refer to that tree. The directory is not a git repository, so history, tags and past commits could not be inspected.

---

## One-page summary

**What it is.** A Python 3.11+ monorepo (about 9,000 lines of source, about 310 test functions) with these parts:

- a FastAPI backend (`/ask`, `/documents/*`, `/status`)
- a React/Vite admin UI
- a python-telegram-bot long-polling bot that calls the API over HTTP
- a ScrapeAI crawler for university documents (SUSU, a Russian university)
- optional Appwrite Cloud persistence

**The RAG pipeline as it really is:**

- Documents are chunked at 800 characters with 100 overlap.
- Embeddings are a **hash-based 128-dimension vector** (SHA-256 of words, bigrams and character trigrams). This is not a learned model.
- The vector store is an in-memory Python scan with cosine similarity.
- Retrieval is **hybrid**: 0.35 × hash-vector score + 0.65 × a keyword-overlap score. There is no BM25 and no cross-encoder reranker.
- Generation is `openai/gpt-oss-20b` on Groq, with strict JSON output of an answer plus claims plus evidence IDs.
- A local verifier then checks claims by keyword overlap, numbers and negation. An optional second LLM check exists but is off by default.

**Verdict.** The system is well structured, offline-testable and strict about citing sources. It is **not yet ready for a research evaluation**. The blockers are:

1. **There is no evaluation harness.** The only "eval" is 4 queries over 4 synthetic documents of about 400–600 characters each (`tests/fixtures/eval/`), measured as a recall regression test.
2. **Nothing about real usage is recorded.** The bot logs only a hash of each question. Questions, retrieved chunks, answers and user feedback are not stored, so you cannot analyze real traffic or run human evaluation from logs.
3. **The retriever is a baseline, not a research component.** The embedding is hard-wired, with `force_deterministic` ignored (`rag/embedding_factory.py:17`). All pipeline parameters are code constants. Swapping the embedder, retriever or reranker means editing source files in several places.
4. **It is probably weak for the target users.** Documents are Russian (`configs/susu/official_regulations.yaml`), while international students will often ask in English. Both retrieval signals are surface-form matching (exact tokens plus hashed n-grams), so **cross-lingual retrieval essentially does not work**. This is the biggest threat to answer quality and needs a decision before any experiment.
5. **Reproducibility is partial.** The Python dependencies are `>=` ranges with no lockfile, only the frontend has one, and the LLM is not seeded.

**Strengths worth keeping.** Every answer carries structured citations. The refusal paths are explicit and enumerated (`RefusalReason`). Retrieval is deterministic and runs offline. There is a document lifecycle with SHA-256 hashing, and CI runs the test suite.

**Top five fixes before experiments:**

1. Add an evaluation log: a persistent, pseudonymized store of query, retrieved chunk IDs and scores, answer, refusal reason and latency (M).
2. Make the pipeline config-driven through one config object (S–M).
3. Introduce an `Embedder` and `Retriever` selection point so a real multilingual model can be swapped in (M).
4. Decide the cross-lingual strategy and build a real multilingual test set (L, mostly annotation).
5. Pin the dependencies and record the exact corpus snapshot by hash (S).

---

## 1. Repository map

| Area | Path | Notes |
|---|---|---|
| Package | `src/uniassist/` | hatchling build (`pyproject.toml`), console entry points not defined |
| API | `api/` (`app.py`, `routes/ask.py`, `routes/documents.py`, `routes/health.py`, `dependencies.py`, `errors.py`, `schemas.py`) | `create_app` factory, served as `uvicorn uniassist.api.app:create_app --factory` |
| RAG | `rag/` (`chunking.py`, `embeddings.py`, `embedding_factory.py`, `vector_store.py`, `indexing.py`, `retrieval.py`, `index_metadata.py`) | |
| LLM | `ai/` (`prompting.py`, `generation.py`, `pipeline.py`, `verification.py`, `claim_verification.py`, `parsing.py`, `providers/{groq,mock,base}.py`) | |
| Ingestion | `documents/`, `processing/` (processors for txt, pdf text via pypdf, MinerU, built-in DOCX) | |
| Scraping | `scrapeai/`, `configs/susu/official_regulations.yaml`, `scripts/` | |
| Persistence | `persistence/` (local files or Appwrite) | selected by `UNIASSIST_STORAGE_BACKEND` |
| Bot | `telegram/` (`bot.py`, `handlers.py`, `api_client.py`, `rate_limit.py`, `session.py`, `formatting.py`) | |
| Admin UI | `frontend/` | React 19, Vite 6, TanStack Query, Tailwind |
| Tests | `tests/` (api, ai, rag, processing, persistence, telegram, scrapeai, e2e, integration) | |
| CI | `.github/workflows/ci.yml` | pytest, `ruff check src tests scripts`, frontend test and build |
| Docs | `README.md`, `docs/appwrite*.md`, `docs/persistence-audit.md` | |

**How it runs.**

- API: `uvicorn uniassist.api.app:create_app --factory --port 8001`.
- Bot: `python -m uniassist.telegram.bot` (`telegram/bot.py`, `run_polling`).
- `scripts/start_uniassist.command` starts both on macOS only (zsh).
- Nothing in the repo deploys it: there is no Dockerfile, compose file, systemd unit or Procfile. **Deployment is undefined. Unverified: how the live instance is actually hosted.**

**Dependencies** (`pyproject.toml`):

- Core: `pyyaml>=6.0, fastapi>=0.115, uvicorn[standard]>=0.32, python-multipart>=0.0.9, httpx>=0.27, pypdf>=5.0`.
- Optional extras: `appwrite>=6.0.0`, `scrapy>=2.11`, `python-telegram-bot>=21.0,<23`.
- **None are pinned, and there is no Python lockfile.** `frontend/package-lock.json` exists. On a fresh install I got fastapi/starlette versions that print a `httpx` deprecation warning, so behaviour can drift between installs.

---

## 2. The RAG pipeline as implemented

**Ingestion.**

- Upload goes through `api/routes/documents.py` (`/documents/upload`) and `documents/ingestion.py`.
- `validate_upload` (`documents/validation.py`) allows only `.pdf`, `.docx` and `.txt`, with a 50 MB cap.
- The SHA-256 of the content is the dedupe key. A record is created as `draft`/`pending`.
- Activation, processing and indexing are separate steps. `/publish` chains them and rolls back on failure.
- Only `admin_upload` is accepted by `DocumentIngestionService.ingest_bytes` (`documents/ingestion.py`). **The crawler and the `scripts/import_susu_*` scripts therefore do not reach the corpus through this path. Unverified: how those scripts load documents.**
- Processing:
  - `.txt` → `TextProcessor`, split on blank lines into paragraphs.
  - PDF → MinerU if installed, otherwise `PdfTextProcessor` (pypdf).
  - DOCX → `DocxTextProcessor` (`processing/processors/docx_text.py`) when MinerU can't.
  - The output is a `NormalizedDocument` of blocks with page number and section.

**Chunking** (`rag/chunking.py`, `rag/models.py:12-13`):

- Character-based, `max_chars=800`, `overlap=100` (`ChunkConfig`).
- Each normalized block is kept whole if it is at most 800 characters (`chunking.py:74-76`).
- Longer blocks are split by paragraph, then sentence, then word (`_semantic_units`, `chunking.py:88-98`), then packed (`_pack_units`, `chunking.py:101-128`).
- The overlap copies the last 100 characters of the previous chunk (`_apply_overlap`, `chunking.py:148-160`), which can start mid-word.
- The sentence splitter `(?<=[.!?])\s+` works for Russian and English.
- `chunk_id` is a SHA-256 of `document_id:source_sha256:index:text`, so it is deterministic.
- Chunk size is measured in characters, not tokens, and is not tied to any embedder's input limit.

**Embedding** (`rag/embeddings.py`, `rag/embedding_factory.py`):

- `DeterministicEmbeddingProvider`: 128 dimensions (`DEFAULT_DIMENSION`).
- It hashes lower-cased words, word bigrams and character trigrams with SHA-256 into signed buckets and L2-normalizes.
- `create_embedding_provider` always returns it; the `force_deterministic` parameter is deleted unused (`embedding_factory.py:17`).
- `default_min_score_for` always returns `0.0` (`embedding_factory.py:21-24`).

**Vector store** (`rag/vector_store.py`):

- In-memory dict. `JsonVectorStore` persists to a JSON file. `AppwriteVectorStore` stores each chunk and its embedding as a JSON string and searches in memory (`persistence/appwrite_vector_store.py`).
- Search is a full scan. Norms are cached after my earlier change.
- An index manifest records provider, model and dimension and refuses to mix them (`rag/index_metadata.py`, `IndexingService._ensure_compatible_index`).

**Retrieval** (`rag/retrieval.py`):

- Defaults (`RetrievalConfig`, lines 30-32): `top_k=8`, `min_score=None` (→ 0.0), `max_chunks_per_document=3`.
- The vector search pulls *every* chunk (`pool_size = len(store)`, lines 126-133), because reranking needs the full pool.
- `_hybrid_rerank` (lines 232-266) scores `0.35 * vector + 0.65 * lexical` (constants at lines 190-191) and caps 3 chunks per document.
- `_lexical_score` (line 268 on) is the fraction of query terms found as substrings in title and text, with hand-written query expansions for "email", "contact" and "help", and bonuses for titles containing "student support" and "international office".
- `_apply_version_preference` re-sorts by relevance bucket (`_TIE_BAND=0.05`, line 189), then effective date, then score.
- **There is no BM25, no learned reranker, and no query rewriting.**

**Prompt construction** (`ai/prompting.py`):

- `SYSTEM_INSTRUCTIONS` (lines 9-58) says to use only the evidence, answer in the student's language, treat documents as data, and return JSON `{answer, insufficient_evidence, claims[{text, evidence_ids}]}`.
- The user message is the question plus the evidence as a JSON array (`build_generation_messages`, line 89 on).
- There is no chat history; every question is independent.

**LLM** (`ai/providers/groq.py`):

- Model `openai/gpt-oss-20b` (line 34), overridable by `GROQ_CHAT_MODEL`.
- Generation uses `temperature=0.0` (line 135), strict JSON-schema response format (lines 189-257), and `max_tokens=2000` (line 90).
- Calls retry on 429/5xx with backoff, 3 attempts. The timeout is 60 s by default.
- No seed is passed.

**Post-processing and verification** (`ai/pipeline.py`, `ai/verification.py`, `ai/claim_verification.py`):

- Structural checks cover duplicate and unknown evidence IDs and empty claims.
- The answer text must be covered by the claims (`verification.py:259-275`, threshold `_MIN_ANSWER_COVERAGE=0.5`).
- Each claim is judged by keyword overlap against the cited chunks: at least 0.5 is "supported", at least 0.25 is "partial", which counts as unsupported (`claim_verification.py:79-93`).
- Every number in a claim must appear in the cited evidence.
- Negation mismatch against the best-matching sentence is rejected.
- Conflicting durations across documents trigger a refusal.
- If some claims fail but at least as many are supported as unsupported, the answer is rebuilt from the supported claims (`repair_candidate`, `verification.py:145`).
- Optional second opinion by the LLM when `UNIASSIST_LLM_VERIFY=1` (`pipeline.py:92`, flag read at `pipeline.py:183`).
- The Telegram bot formats the answer plus a "Sources / Источники" list (`telegram/formatting.py:31-40`).

---

## 3. Capability checklist

| Item | Status | Evidence |
|---|---|---|
| Source citations in answers | **PRESENT** | `Citation` model (`ai/models.py`), built in `VerificationEngine.build_citations`; `AskResponse.citations` (`api/schemas.py:78`); Telegram prints title, page or section and `source_url` (`telegram/formatting.py:14-40`). Citations are per chunk, not per sentence. |
| Abstention when retrieval is weak | **PARTIAL** | Refuses when retrieval returns nothing (`ai/generation.py:80-83`), when the model sets `insufficient_evidence`, or when verification fails. But `min_score` is 0.0 (`embedding_factory.py:21-24`), and with 128-dimension hash vectors some chunk almost always passes, so the "weak retrieval" gate is effectively the LLM plus the verifier. There is no calibrated score threshold. |
| Query / retrieval / answer logging | **PARTIAL** | Only `question_hash` (16 hex chars of SHA-256), chunk count, model, top score and latencies are logged (`ai/observability.py:14-66`). API access log has method, path, status and duration (`api/app.py:90-99`). **The question text, retrieved chunk IDs and the answer are not stored anywhere.** The hash is of the plain question, so it is guessable for common questions and is not a salted pseudonym. The Telegram user ID is used for rate limiting and an in-memory session only (`telegram/handlers.py:133,169`), and is not logged. |
| User feedback capture | **MISSING** | No feedback buttons, handler, endpoint or table. A search for feedback, rating or thumbs in `src/` and `frontend/src/` found nothing. |
| Config-driven pipeline | **PARTIAL** | Env-driven: Groq model, base URL and timeout, CORS, max question length, storage backend, Telegram limits, `UNIASSIST_LLM_VERIFY`. **Hardcoded:** chunk size and overlap (`rag/models.py:12-13`), embedding provider and dimension, `top_k=8` (generation service constructor), `max_chunks_per_document=3`, `min_score`, the 0.35/0.65 weights, `_TIE_BAND`, verifier thresholds 0.5/0.25, query expansions, the full prompts, `max_tokens`, `temperature`. No YAML or TOML pipeline config exists. |
| Evaluation harness / test set | **PARTIAL (minimal)** | `tests/rag/test_eval_retrieval.py` plus `tests/fixtures/eval/queries.json`: 4 queries, 4 synthetic English documents of about 400–600 characters (1,923 characters total), metric recall@k by title. Its own docstring says it is a regression check and not real quality. No answer-quality metrics, no gold passages, no refusal/abstention set, no Russian or cross-lingual queries, no script that outputs a results file. The live E2E tests (`tests/e2e/`) are skipped without `UNIASSIST_RUN_GROQ_INTEGRATION=1`. |
| Document versioning (fetch date, hash) | **PARTIAL** | `DocumentRecord` stores `sha256`, `uploaded_at`, `effective_date`, `version`, `source_url`, `status`. Chunks carry `source_sha256` and `document_version` (`rag/models.py`). The crawler's own metadata has `sha256` and `retrieved_at` (`scrapeai/models.py:48-49`) but **`DocumentRecord` has no fetch date and no link to the crawl record**, so the retrieval date of an official source is lost. No corpus-snapshot manifest exists. |
| Reproducibility | **PARTIAL** | Good: deterministic embeddings and chunk IDs, offline tests, `pythonpath` set in pytest config, CI on Python 3.12. Missing: no Python lockfile, unpinned ranges, no seed to Groq, Groq model can change server-side, no data/corpus snapshot, no deployment files. README: the install steps work (I installed `.[dev,telegram,scrapeai]` plus `appwrite` and ran the suite), and it is mostly accurate. It still describes the project in "phases", and `.env.example` and README say retrieval uses local hash embeddings, which is accurate. The README has no section on how to run an evaluation. |
| Language handling | **PARTIAL** | The prompt says to answer in the question's language (`prompting.py:16`), the bot greets and refuses in English plus Russian (`telegram/handlers.py` START/HELP text, `telegram/errors.py:45-49`), and tokenization is now Unicode-aware (`core/text.py`). **There is no language detection, no translation of queries or documents, and retrieval is monolingual by construction.** An English question will not match Russian text lexically, and the hash embedding cannot bridge languages. |
| Prompt injection and off-topic | **PARTIAL** | Prompt rules treat documents as data and forbid following embedded instructions (`prompting.py:31-33`), and the question is length-limited (`api/routes/ask.py:38-41`). Answers must be tied to cited evidence by the verifier, which blocks many injected claims. But the user question is placed straight in the prompt with no filtering, there is no injection or jailbreak classifier, no explicit off-topic detector (off-topic falls out as "no evidence"), and no tests with adversarial documents or questions. Unverified: behaviour against a live model. |
| Error handling, timeouts, retries, rate limits | **PARTIAL** | Good: consistent error envelope with request IDs (`api/errors.py`), Groq retries and timeout, Telegram timeouts (`telegram/config.py`), user-facing error mapping (`telegram/errors.py`), per-user Telegram rate limit (`telegram/rate_limit.py`). Gaps: **`/ask` itself has no rate limit or auth**, so anyone who can reach the API bypasses the bot's limit and spends Groq quota; the rate limiter is per process and in memory; no retry for the bot-to-API call; no circuit breaker. |
| Tests and CI | **PRESENT** | 300 tests pass, 13 skipped (live Groq, Appwrite, Telegram, MinerU). CI runs pytest, ruff on `src tests scripts`, frontend tests and build. No coverage reporting, no type checking (mypy/pyright), no scheduled live smoke test. |

---

## 4. Security and privacy

**Secrets.**

- A pattern search over `src`, `scripts`, `tests`, `configs` and `docs` found no hardcoded keys; only test placeholders (`test-token`, `test-key`, `api_key="k"`).
- `.env` is gitignored; `.env.example` and `frontend/.env.example` hold empty placeholders.
- The Appwrite API key and the Telegram token are read from the environment only.
- Unverified: git history (no git repository here) and whether a real `.env` exists on disk. I did not look for one.

**Frontend secret handling.** The staff secret is entered at runtime and held in `sessionStorage` (`frontend/src/lib/adminSecret.ts`). It is no longer readable from the build environment.

**User data stored.**

- Telegram user IDs live only in process memory (rate limiter and session store, capped and evicted) and vanish on restart.
- Question text is never persisted. Hashes of questions and request IDs appear in logs.
- Logs go to `logs/fastapi.log` and `logs/telegram.log` when the macOS launcher is used (`scripts/start_uniassist.command`); that directory is gitignored. **No retention policy exists.**
- If you add the evaluation log recommended below, it will become personal-data storage and needs a retention rule and a consent notice.

**Things that would block publishing the repo as it is.**

1. `docs/` and README mention Appwrite project setup but I found no real identifiers. Re-check `docs/appwrite*.md` for project or database IDs before publishing (I only skimmed them).
2. The SUSU crawl profile names a real university and sets a Crawl-delay-aware 10 s delay. Check the terms of reuse for the documents before redistributing the corpus; `data/` is gitignored, which helps.
3. Build artifacts left by my own setup runs are present and should be excluded or deleted before sharing: `frontend/node_modules/`, `frontend/dist/`, `src/uniassist.egg-info/`, and `__pycache__/` folders. They are gitignored but the folder is not a git repository, so a plain zip would include them.
4. `/ask` is unauthenticated by design for the bot. If you publish a running instance, add auth or a rate limit.

---

## 5. Code quality

- **Dead or unused code.**
  - `GroqProvider.verify_answer` and the verification prompt are only used when `UNIASSIST_LLM_VERIFY=1`.
  - `create_embedding_provider(force_deterministic=...)` ignores its argument.
  - `default_min_score_for` ignores its argument.
  - `telegram/formatting.escape_markdown` is only used by its test.
  - `DocumentStatus`/`VerificationState` comments mention "future" and "Phase 3".
- **Duplicated logic.**
  - Stopword lists and tokenizers now live in `core/text.py`, but `rag/retrieval.py` still has its own `_RETRIEVAL_STOPWORDS` and `_retrieval_terms`.
  - The refusal message map (`ai/pipeline.py`) and the Telegram refusal text (`telegram/errors.py`) are separate.
  - The document-lifecycle checks are split between `ingestion`, `processing/service.py` and `indexing.py`.
  - `AnswerPipeline.default` builds its own `JsonDocumentStore` apart from the retriever's.
- **Files that deserve splitting.**
  - `processing/service.py` (about 430 lines): orchestration, DOCX, PDF fallback and output reading are mixed.
  - `ai/verification.py` (about 370 lines): structural, citation, contradiction and repair logic.
  - `rag/indexing.py` (about 340 lines): indexing, manifest, metadata JSON and eligibility.
  - `api/routes/documents.py`: route handlers plus publish orchestration.
- **What makes swapping components hard.**
  - **Embedder:** `Retriever` and `IndexingService` each call `create_embedding_provider()` as a fallback (`retrieval.py:59`, `indexing.py:84`), and the factory has no selection logic. The `EmbeddingProvider` protocol exists, which helps, but the dimension is baked into the manifest, so switching models needs a full reindex (the compatibility check supports this).
  - **Retriever:** hybrid reranking is module-level functions and constants inside `retrieval.py`. There is no `Retriever` protocol, so a BM25 or dense-only variant means editing or subclassing a concrete class used directly by `AnswerGenerationService`.
  - **Reranker:** none exists, and there is no hook between `_hybrid_rerank` and `_apply_version_preference`.
  - **Chunker:** `chunk_document` is a function with a fixed config object, with no pluggable strategy.
  - **LLM:** well isolated behind the `LLMProvider` protocol (`ai/providers/base.py`), and a `MockLLMProvider` exists. This is the cleanest seam in the repo.
- **Typing.** Annotations are widespread but `mypy` is not run, and several functions return untyped values (for example `_mark_contradictory`, `normalized` parameters in `processing/service.py`).

---

## 6. Prioritized plan

Effort: S ≈ under half a day, M ≈ 1–3 days, L ≈ more than 3 days.

### (a) Must fix before running experiments

| # | Item | Files | Effort | Smallest change |
|---|---|---|---|---|
| A1 | Decide and handle **cross-lingual retrieval** (English questions, Russian documents) | `rag/embeddings.py`, `rag/embedding_factory.py`, `rag/retrieval.py`, `ai/prompting.py` | L | Pick a multilingual embedder (for example a multilingual E5 or BGE-M3 model) behind the `EmbeddingProvider` protocol and reindex. Cheaper alternative to compare against: translate the query to the document language before retrieval. Keep the hash embedder as the baseline arm. |
| A2 | **Experiment log** (see B1), because without it nothing in an experiment is reproducible | `ai/observability.py`, `api/routes/ask.py` | M | Append one JSON line per `/ask` to a file: run ID, config hash, pseudonymized user, question, retrieved chunk IDs and scores, answer, refusal reason, latencies. |
| A3 | **Single pipeline config** with a config hash | new `config/pipeline.yaml` or dataclass; `rag/models.py`, `rag/retrieval.py`, `ai/generation.py`, `ai/providers/groq.py` | M | One `PipelineConfig` dataclass (chunk size and overlap, top_k, min_score, weights, thresholds, model, temperature, prompt version) loaded from YAML/env and passed in; log its hash with every request. |
| A4 | **Pin dependencies** and record environment | `pyproject.toml`, new `requirements.lock` (or `uv.lock`) | S | Generate a lockfile with `pip-compile` or `uv lock`; document Python version; add to CI. |
| A5 | **Calibrated abstention threshold** | `rag/embedding_factory.py:21-24`, `rag/retrieval.py:109-111` | S–M | Make `min_score` configurable and choose it from the score distribution on the evaluation set; today it is 0.0 and cannot gate anything. |
| A6 | **Protect `/ask`** if the API is reachable beyond localhost | `api/routes/ask.py`, `api/dependencies.py` | S | Add an API key header for the bot and a per-IP rate limit, otherwise experiments can be polluted and quota drained. |
| A7 | **Corpus snapshot** | `documents/models.py`, `documents/ingestion.py`, `scrapeai/` | S–M | Add `fetched_at` and `crawl_sha256` fields to `DocumentRecord`, and write a `corpus_manifest.json` (document IDs, hashes, versions) next to every evaluation run. |

### (b) Needed for the evaluation harness

| # | Item | Files | Effort | Smallest change |
|---|---|---|---|---|
| B1 | **Retrieval and answer evaluation script** | new `eval/run_eval.py`, `eval/datasets/*.jsonl`, reuse `ai/pipeline.py` | M | A CLI that reads a JSONL test set (question, language, gold document or passage IDs, answerable yes/no, reference answer), runs the pipeline with a named config, and writes per-question results plus recall@k, MRR, abstention precision and recall, citation correctness. |
| B2 | **Real test set**: Russian, English and mixed questions, unanswerable and off-topic questions, adversarial ones | `eval/datasets/` | L | Annotate 100–200 questions over the actual SUSU corpus, with gold passages. The existing 4 synthetic queries are a smoke test only. |
| B3 | **Retriever, embedder and reranker interfaces** | `rag/retrieval.py`, `rag/embedding_factory.py`, `ai/generation.py` | M | Define a `Retriever` protocol (`retrieve_with_metadata`) and a `Reranker` protocol; make the factory choose by config name. Move BM25 and dense-only variants into separate classes so arms can be compared. |
| B4 | **Add BM25 and a cross-encoder reranker as comparison arms** | `rag/` | M | Implement BM25 over the existing chunks; add an optional reranker step after retrieval. |
| B5 | **User feedback capture** (Telegram inline buttons, a `/feedback` route, a store) | `telegram/handlers.py`, `telegram/bot.py`, `api/routes/`, `api/schemas.py` | M | Add 👍/👎 and a "wrong or outdated" button to each answer, post to a new endpoint keyed by `request_id`, and append to the experiment log. |
| B6 | **Human-evaluation export** | `eval/` | S | Script that turns the experiment log into a CSV or sheet with question, answer, citations, and blank rating columns. |
| B7 | **Deterministic LLM runs** | `ai/providers/groq.py` | S | Pass a `seed` if Groq supports it for the model; otherwise store the full raw model output per request and report the variance by repeated runs. |
| B8 | **Latency and cost fields** | `ai/pipeline.py`, `api/schemas.py` | S | Record retrieval, generation, verification and total latencies, and token counts from the Groq response. The pipeline's own timing code was removed as dead earlier, so this needs to be re-added properly. |
| B9 | **Ablation switches** for the verifier, hybrid weights, LLM second opinion | config from A3 | S | Expose each as a config flag so a run can toggle them. |

### (c) Nice to have

| # | Item | Files | Effort | Smallest change |
|---|---|---|---|---|
| C1 | Dockerfile and compose for API plus bot | repo root | S–M | Single image, two commands, env file. Also documents the real deployment. |
| C2 | Per-sentence citations | `ai/prompting.py`, `telegram/formatting.py` | M | Attach claim-to-citation mapping in the Telegram message. |
| C3 | Coverage reporting and type checking in CI | `.github/workflows/ci.yml` | S | Add `pytest --cov` and `mypy src`. |
| C4 | Split the large modules | `processing/service.py`, `ai/verification.py`, `rag/indexing.py` | M | Extract by responsibility; no behaviour change. |
| C5 | Remove dead code | see section 5 | S | Delete or implement the unused parameters and helpers. |
| C6 | Conversation context (follow-up questions) | `telegram/session.py`, `ai/prompting.py` | M | Pass the previous turn to query rewriting. Out of scope unless the research needs it. |
| C7 | Retention policy and a consent notice | `telegram/handlers.py`, README | S | Add text to `/start` and a log-purge command or schedule once the experiment log exists. |
| C8 | Prompt-injection test suite | `tests/ai/` | M | Add documents containing instructions and questions that attempt to override rules; assert refusal or unaffected answers. |

---

## 7. Questions for you

1. **What is the target corpus and language mix?** Is the evaluation on Russian SUSU documents only, with students asking in English, Russian or both? This determines whether A1 is a blocker or just a risk.
2. **Is a paid or hosted embedding model allowed, or must everything run locally?** The README says "no model downloads"; that conflicts with using a multilingual embedder.
3. **Which Groq model and version must the report cite**, and is Groq an acceptable fixed dependency for the study?
4. **Will real students use the bot during the study?** If yes, you need consent, retention and anonymization decisions before storing any question text (see section 4).
5. **How is the live instance deployed and where do logs go?** Nothing in the repo tells me.
6. **Which comparison arms do you want** (hash baseline, BM25, multilingual dense, reranked, with or without verification)? That shapes B3–B4.
7. **Who annotates the test set**, and are there existing real student questions I should know about?

## 8. What I could not verify

- Behaviour against live Groq, Telegram or Appwrite (no calls were made; those tests are skipped).
- The actual quality of retrieval on the real SUSU corpus. The `data/` directories are empty here.
- How `scripts/import_susu_international_pages.py` and `scripts/ingest_susu_international_public_pages.py` load documents. I did not read them in this audit, and `DocumentIngestionService` only accepts `admin_upload`.
- MinerU behaviour (not installed here).
- Git history, existing deployments, whether a real `.env` or logs exist, and the full text of `docs/appwrite*.md`.
- Frontend behaviour beyond its unit tests.
- Exact line numbers for `top_k=8` in the generation service constructor and for `DEFAULT_DIMENSION`; I cited the file and symbol instead.
