"""Thin Appwrite SDK wrapper with injectable clients for tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from uniassist.persistence.config import AppwriteConfig


class AppwriteDatabasesClient(Protocol):
    def list_documents(
        self,
        database_id: str,
        collection_id: str,
        queries: list[str] | None = None,
    ) -> dict[str, Any]: ...

    def get_document(
        self,
        database_id: str,
        collection_id: str,
        document_id: str,
    ) -> dict[str, Any]: ...

    def create_document(
        self,
        database_id: str,
        collection_id: str,
        document_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]: ...

    def update_document(
        self,
        database_id: str,
        collection_id: str,
        document_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]: ...

    def delete_document(
        self,
        database_id: str,
        collection_id: str,
        document_id: str,
    ) -> dict[str, Any]: ...


class AppwriteStorageClient(Protocol):
    def create_file(
        self,
        bucket_id: str,
        file_id: str,
        file: Any,
    ) -> dict[str, Any]: ...

    def get_file(self, bucket_id: str, file_id: str) -> dict[str, Any]: ...

    def get_file_download(self, bucket_id: str, file_id: str) -> bytes: ...

    def delete_file(self, bucket_id: str, file_id: str) -> dict[str, Any]: ...


class TablesDBAdapter:
    """Expose the legacy store contract through Appwrite's TablesDB API."""

    def __init__(self, tables_db: Any) -> None:
        self._tables_db = tables_db

    def list_documents(self, database_id: str, collection_id: str, queries=None):
        response = self._tables_db.list_rows(
            database_id=database_id, table_id=collection_id, queries=queries
        )
        data = _sdk_response_map(response)
        return {"documents": data.get("rows", [])}

    def get_document(self, database_id: str, collection_id: str, document_id: str):
        response = self._tables_db.get_row(
            database_id=database_id, table_id=collection_id, row_id=document_id
        )
        return _sdk_response_map(response)

    def create_document(
        self, database_id: str, collection_id: str, document_id: str, data
    ):
        response = self._tables_db.create_row(
            database_id=database_id,
            table_id=collection_id,
            row_id=document_id,
            data=data,
        )
        return _sdk_response_map(response)

    def update_document(
        self, database_id: str, collection_id: str, document_id: str, data
    ):
        response = self._tables_db.update_row(
            database_id=database_id,
            table_id=collection_id,
            row_id=document_id,
            data=data,
        )
        return _sdk_response_map(response)

    def delete_document(self, database_id: str, collection_id: str, document_id: str):
        return self._tables_db.delete_row(
            database_id=database_id, table_id=collection_id, row_id=document_id
        )


def _sdk_response_map(response: Any) -> dict[str, Any]:
    """Convert Appwrite SDK model responses across supported SDK versions."""
    if isinstance(response, dict):
        return response
    if hasattr(response, "to_map"):
        return dict(response.to_map())
    if hasattr(response, "model_dump"):
        return dict(response.model_dump(by_alias=True))
    return {}


@dataclass(frozen=True)
class AppwriteClients:
    """Injectable Appwrite service clients."""

    databases: AppwriteDatabasesClient
    storage: AppwriteStorageClient
    config: AppwriteConfig


def build_appwrite_clients(config: AppwriteConfig) -> AppwriteClients:
    from appwrite.client import Client
    from appwrite.services.storage import Storage
    from appwrite.services.tables_db import TablesDB

    client = Client()
    client.set_endpoint(config.endpoint)
    client.set_project(config.project_id)
    client.set_key(config.api_key)
    return AppwriteClients(
        databases=TablesDBAdapter(TablesDB(client)),
        storage=Storage(client),
        config=config,
    )
