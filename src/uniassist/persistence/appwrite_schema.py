"""Idempotent Appwrite collection schema setup for UniAssist."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from uniassist.persistence.appwrite_client import AppwriteClients
from uniassist.persistence.config import AppwriteConfig


@dataclass(frozen=True)
class CollectionAttribute:
    key: str
    type: str
    size: int | None = None
    required: bool = False
    array: bool = False


DOCUMENTS_ATTRIBUTES: tuple[CollectionAttribute, ...] = (
    CollectionAttribute("document_id", "string", 64, required=True),
    CollectionAttribute("title", "string", 512),
    CollectionAttribute("filename", "string", 512),
    CollectionAttribute("content_type", "string", 128),
    CollectionAttribute("sha256", "string", 64),
    CollectionAttribute("local_path", "string", 1024),
    CollectionAttribute("storage_ref", "string", 1024),
    CollectionAttribute("uploaded_at", "string", 64),
    CollectionAttribute("source", "string", 512),
    CollectionAttribute("source_type", "string", 64),
    CollectionAttribute("source_url", "string", 2048),
    CollectionAttribute("effective_date", "string", 32),
    CollectionAttribute("version", "string", 64),
    CollectionAttribute("status", "string", 32),
    CollectionAttribute("verification_state", "string", 32),
    CollectionAttribute("notes", "string", 4096),
    CollectionAttribute("metadata_json", "string", 16384, required=True),
)

PROCESSING_ATTRIBUTES: tuple[CollectionAttribute, ...] = (
    CollectionAttribute("document_id", "string", 64, required=True),
    CollectionAttribute("status", "string", 32, required=True),
    CollectionAttribute("processor", "string", 64, required=True),
    CollectionAttribute("input_path", "string", 1024),
    CollectionAttribute("output_path", "string", 1024),
    CollectionAttribute("processed_at", "string", 64),
    CollectionAttribute("source_sha256", "string", 64),
    CollectionAttribute("content_hash", "string", 64),
    CollectionAttribute("processor_version", "string", 64),
    CollectionAttribute("error", "string", 4096),
    CollectionAttribute("metadata_json", "string", 16384, required=True),
)

CHUNKS_ATTRIBUTES: tuple[CollectionAttribute, ...] = (
    CollectionAttribute("chunk_id", "string", 64, required=True),
    CollectionAttribute("document_id", "string", 64, required=True),
    CollectionAttribute("text", "string", 16384, required=True),
    CollectionAttribute("chunk_index", "integer", required=True),
    CollectionAttribute("page_number", "integer"),
    CollectionAttribute("section", "string", 512),
    CollectionAttribute("source_sha256", "string", 64, required=True),
    CollectionAttribute("document_version", "string", 64),
    CollectionAttribute("source", "string", 512),
    CollectionAttribute("source_url", "string", 2048),
    CollectionAttribute("title", "string", 512),
    CollectionAttribute("embedding", "string", 32768, required=True),
    CollectionAttribute("chunk_json", "string", 16384, required=True),
    CollectionAttribute("manifest_json", "string", 16384),
)


@dataclass
class SchemaSetupReport:
    created: list[str]
    existing: list[str]
    failed: list[str]


def ensure_schema(
    clients: AppwriteClients,
    config: AppwriteConfig,
) -> SchemaSetupReport:
    """Ensure required Appwrite collection attributes exist."""
    report = SchemaSetupReport(created=[], existing=[], failed=[])
    mappings = (
        (config.documents_collection_id, DOCUMENTS_ATTRIBUTES),
        (config.processing_collection_id, PROCESSING_ATTRIBUTES),
        (config.chunks_collection_id, CHUNKS_ATTRIBUTES),
    )
    for collection_id, attributes in mappings:
        existing_keys = _list_attribute_keys(
            clients.databases,
            config.database_id,
            collection_id,
        )
        required_keys = {attribute.key for attribute in attributes}
        if required_keys.issubset(existing_keys):
            report.existing.extend(
                f"{collection_id}.{attribute.key}" for attribute in attributes
            )
            continue
        for attribute in attributes:
            key = f"{collection_id}.{attribute.key}"
            if attribute.key in existing_keys:
                report.existing.append(key)
                continue
            try:
                created = _ensure_attribute(
                    clients,
                    config.database_id,
                    collection_id,
                    attribute,
                )
                if created:
                    report.created.append(key)
                else:
                    report.existing.append(key)
            except Exception:
                report.failed.append(key)
    return report


def _ensure_attribute(
    clients: AppwriteClients,
    database_id: str,
    collection_id: str,
    attribute: CollectionAttribute,
) -> bool:
    databases = clients.databases
    existing = _list_attribute_keys(databases, database_id, collection_id)
    if attribute.key in existing:
        return False

    try:
        if attribute.type == "string":
            databases.create_string_attribute(
                database_id=database_id,
                collection_id=collection_id,
                key=attribute.key,
                size=attribute.size or 255,
                required=attribute.required,
                array=attribute.array,
            )
        elif attribute.type == "integer":
            databases.create_integer_attribute(
                database_id=database_id,
                collection_id=collection_id,
                key=attribute.key,
                required=attribute.required,
                array=attribute.array,
            )
        else:
            raise ValueError(f"unsupported attribute type: {attribute.type}")
    except Exception as exc:
        if "already exists" in str(exc).lower():
            return False
        raise

    _wait_for_attribute(databases, database_id, collection_id, attribute.key)
    return True


def _list_attribute_keys(
    databases: Any,
    database_id: str,
    collection_id: str,
) -> set[str]:
    for _attempt in range(3):
        try:
            response = databases.list_attributes(database_id, collection_id)
        except Exception:
            time.sleep(1.0)
            continue
        items = getattr(response, "attributes", None)
        if items is None and isinstance(response, dict):
            items = response.get("attributes", [])
        keys: set[str] = set()
        for item in items or []:
            if isinstance(item, dict):
                key = item.get("key")
            else:
                key = getattr(item, "key", None)
            if key:
                keys.add(str(key))
        return keys
    return set()


def _wait_for_attribute(
    databases: Any,
    database_id: str,
    collection_id: str,
    key: str,
    *,
    timeout_seconds: float = 60.0,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        keys = _list_attribute_keys(databases, database_id, collection_id)
        if key in keys:
            return
        time.sleep(0.5)
    raise TimeoutError(
        f"Timed out waiting for Appwrite attribute {collection_id}.{key}"
    )
