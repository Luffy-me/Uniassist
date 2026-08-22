# Phase 10 — Filesystem Persistence Audit

## Summary

UniAssist currently persists all production data on the local filesystem under `data/`. Phase 10 adds Appwrite-backed implementations behind the same interfaces while preserving local mode for development and tests.

## Persistence touchpoints

| Area | Local path / file | Module | Notes |
|------|-------------------|--------|-------|
| Raw document blobs | `data/raw/{sha256}__{filename}` | `documents/store.py` | Immutable SHA-256 deduplication |
| Document metadata | `data/metadata/documents.json` | `documents/store.py` | `DocumentRecord` index |
| Processing metadata | `data/metadata/processing.json` | `processing/store.py` | `ProcessingResult` index |
| Normalized JSON | `data/processed/{id}/{sha256}/normalized.json` | `processing/store.py` | Large artifacts |
| Vector index | `data/metadata/rag/index.json` | `rag/vector_store.py` | Chunk embeddings |
| RAG document index | `data/metadata/rag/documents.json` | `rag/indexing.py` | Indexed document metadata |
| Index manifest | `data/metadata/rag/index_manifest.json` | `rag/index_metadata.py` | Embedding compatibility |

## Service factories assuming local paths

- `DocumentIngestionService.default()` → `JsonDocumentStore`
- `DocumentProcessingService.default()` → `JsonDocumentStore` + `ProcessingStore`
- `IndexingService.default()` → `JsonVectorStore` + JSON metadata
- `AnswerPipeline.default()` / `from_indexing()` → shared `IndexingService`
- `build_services()` in `api/dependencies.py` → all `.default()` factories

## Processing reads local files directly

- `DocumentProcessingService.process_document()` checks `record.local_path.exists()`
- Processors write to `output_dir` on disk (`ProcessorContext`)
- MinerU requires local input files (cloud mode downloads to temp workspace)

## Configuration

- `UNIASSIST_PROJECT_ROOT` — project root for local paths
- `UNIASSIST_DATA_DIR` — optional data directory override (new)
- No Appwrite variables existed before Phase 10

## Out of scope for migration

- ScrapeAI acquisition storage (`scrapeai/storage.py`) — frozen optional path
- NVIDIA / Telegram — no persistence changes
- AnswerPipeline business logic — storage-provider independent

## Phase 10 approach

1. Add `uniassist.persistence` with `local` and `appwrite` backends
2. Select backend via `UNIASSIST_STORAGE_BACKEND=local|appwrite`
3. Extend `DocumentStore` with blob read/exists for cloud paths
4. Add optional `storage_ref` on `DocumentRecord` for cloud object IDs
5. Processing uses temp directories when Appwrite backend is active
6. `AppwriteVectorStore` mirrors `JsonVectorStore` cosine behavior with DB persistence
