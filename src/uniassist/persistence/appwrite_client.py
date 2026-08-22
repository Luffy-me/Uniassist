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


@dataclass(frozen=True)
class AppwriteClients:
    """Injectable Appwrite service clients."""

    databases: AppwriteDatabasesClient
    storage: AppwriteStorageClient
    config: AppwriteConfig


def build_appwrite_clients(config: AppwriteConfig) -> AppwriteClients:
    from appwrite.client import Client
    from appwrite.services.databases import Databases
    from appwrite.services.storage import Storage

    client = Client()
    client.set_endpoint(config.endpoint)
    client.set_project(config.project_id)
    client.set_key(config.api_key)
    return AppwriteClients(
        databases=Databases(client),
        storage=Storage(client),
        config=config,
    )
