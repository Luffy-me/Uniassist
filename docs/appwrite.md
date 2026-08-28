# Appwrite Cloud setup for UniAssist

UniAssist can persist documents, processing metadata, and RAG indexes locally (default) or in Appwrite Cloud.

## 1. Create an Appwrite project

Create a project in [Appwrite Cloud](https://cloud.appwrite.io) and note the project ID.

## 2. Create a database

Create one database (for example `uniassist`).

Collections:

| Collection | Purpose |
|------------|---------|
| `documents` | `DocumentRecord` metadata (`metadata_json`) |
| `processing` | `ProcessingResult` metadata |
| `chunks` | RAG chunk embeddings + manifest document |

## 3. Create storage buckets

| Bucket | Purpose |
|--------|---------|
| `raw` | Uploaded source documents |
| `processed` | Normalized JSON artifacts |

## 4. Permissions

Use a server API key with least privilege:

- Databases: read/write on the three collections
- Storage: read/write on both buckets

Never expose `APPWRITE_API_KEY` to the React frontend or Telegram bot.

## 5. Environment variables

```bash
UNIASSIST_STORAGE_BACKEND=appwrite

APPWRITE_ENDPOINT=https://cloud.appwrite.io/v1
APPWRITE_PROJECT_ID=...
APPWRITE_API_KEY=...

APPWRITE_DATABASE_ID=...
APPWRITE_DOCUMENTS_COLLECTION_ID=...
APPWRITE_PROCESSING_COLLECTION_ID=...
APPWRITE_CHUNKS_COLLECTION_ID=...

APPWRITE_RAW_BUCKET_ID=...
APPWRITE_PROCESSED_BUCKET_ID=...
```

Local development:

```bash
UNIASSIST_STORAGE_BACKEND=local
```

## 6. Migration from local data

Dry run:

```bash
python -m uniassist.migrations.appwrite --dry-run
```

Migrate:

```bash
python -m uniassist.migrations.appwrite
```

The migration is idempotent, preserves SHA-256 deduplication, and does not delete local files.

## 7. Verify

1. Start FastAPI with Appwrite env vars.
2. `GET /status` should report `storage_backend: appwrite`.
3. Upload → activate → process → index through Admin UI.
4. `POST /ask` with a grounded question.
5. Telegram bot should continue calling FastAPI only.

## Optional live integration tests

```bash
UNIASSIST_RUN_APPWRITE_INTEGRATION=1 \
python -m pytest tests/integration/appwrite -v
```

## Frontend production API URL

```bash
VITE_API_URL=https://your-production-api.example.com
```

Do not place Appwrite or Groq secrets in frontend env vars.
