# Appwrite schema for UniAssist

This document describes the Appwrite Database attributes required by Phase 10 persistence code. Create these attributes on the existing `uniassist` database tables. Do not delete or recreate the tables.

Setup command (idempotent):

```bash
python -m uniassist.persistence.appwrite_setup
```

## `documents` table

| Column | Appwrite type | Required | Size | Array | Why UniAssist needs it |
|--------|---------------|----------|------|-------|------------------------|
| `document_id` | string | yes | 64 | no | Primary business identifier for corpus records |
| `title` | string | no | 512 | no | Admin-visible document title |
| `filename` | string | no | 512 | no | Original uploaded filename |
| `content_type` | string | no | 128 | no | MIME type for processing routing |
| `sha256` | string | no | 64 | no | Immutable blob deduplication |
| `local_path` | string | no | 1024 | no | Legacy/local reference retained in metadata |
| `storage_ref` | string | no | 1024 | no | Appwrite Storage blob reference |
| `uploaded_at` | string | no | 64 | no | Provenance timestamp |
| `source` | string | no | 512 | no | Human-readable source label |
| `source_type` | string | no | 64 | no | Acquisition channel |
| `source_url` | string | no | 2048 | no | Optional source URL |
| `effective_date` | string | no | 32 | no | Policy effective date |
| `version` | string | no | 64 | no | Document version label |
| `status` | string | no | 32 | no | Lifecycle status |
| `verification_state` | string | no | 32 | no | Verification gate for indexing |
| `notes` | string | no | 4096 | no | Admin notes |
| `metadata_json` | string | yes | 16384 | no | Canonical serialized `DocumentRecord` |

## `processing` table

| Column | Appwrite type | Required | Size | Array | Why UniAssist needs it |
|--------|---------------|----------|------|-------|------------------------|
| `document_id` | string | yes | 64 | no | Foreign key to document |
| `status` | string | yes | 32 | no | Processing lifecycle state |
| `processor` | string | yes | 64 | no | Processor name (`text`, `mineru`, etc.) |
| `input_path` | string | no | 1024 | no | Source path/reference used for processing |
| `output_path` | string | no | 1024 | no | Normalized artifact storage reference |
| `processed_at` | string | no | 64 | no | Processing timestamp |
| `source_sha256` | string | no | 64 | no | Links processing to immutable source blob |
| `content_hash` | string | no | 64 | no | Hash of normalized output |
| `processor_version` | string | no | 64 | no | Processor version for auditability |
| `error` | string | no | 4096 | no | Failure reason when processing fails |
| `metadata_json` | string | yes | 16384 | no | Canonical serialized `ProcessingResult` |

Normalized JSON artifacts themselves are stored in the `processed` Storage bucket, not as database rows.

## `chunks` table

| Column | Appwrite type | Required | Size | Array | Why UniAssist needs it |
|--------|---------------|----------|------|-------|------------------------|
| `chunk_id` | string | yes | 64 | no | Unique chunk identifier |
| `document_id` | string | yes | 64 | no | Source document for retrieval filtering |
| `text` | string | yes | 16384 | no | Evidence text used by retrieval and verification |
| `chunk_index` | integer | yes | — | no | Stable chunk ordering within a document |
| `page_number` | integer | no | — | no | Provenance page number |
| `section` | string | no | 512 | no | Provenance section label |
| `source_sha256` | string | yes | 64 | no | Links chunk to immutable source blob |
| `document_version` | string | no | 64 | no | Version-aware retrieval preference |
| `source` | string | no | 512 | no | Citation source label |
| `source_url` | string | no | 2048 | no | Citation URL |
| `title` | string | no | 512 | no | Citation title |
| `embedding` | string | yes | 32768 | no | JSON-serialized embedding vector |
| `chunk_json` | string | yes | 16384 | no | Canonical serialized `Chunk` model |
| `manifest_json` | string | no | 16384 | no | Index manifest document (`index_manifest`) |

Embedding model name, embedding dimension, and index version are stored in the index manifest row (`index_manifest`) rather than duplicated on every chunk row.

## Storage buckets

| Bucket | Purpose |
|--------|---------|
| `raw` | Immutable uploaded source documents |
| `processed` | Normalized JSON artifacts |

Blob references use the internal format:

```text
appwrite://<prefix>/<bucket_id>/<file_id>
```

## Permissions

Use a server-side API key only. FastAPI holds Appwrite credentials; React Admin and Telegram must never receive `APPWRITE_API_KEY`.
