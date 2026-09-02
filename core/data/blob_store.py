"""'Blob Storage (Documents)' box — Azure Blob Storage when configured, the
local filesystem otherwise (under ``./.data/blobs``).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

from core.config import Settings


class BlobStore(ABC):
    @abstractmethod
    async def write(self, path: str, content: bytes) -> str: ...

    @abstractmethod
    async def read(self, path: str) -> bytes | None: ...


class LocalFileBlobStore(BlobStore):
    def __init__(self, root: str = ".data/blobs") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    async def write(self, path: str, content: bytes) -> str:
        target = self._root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)

    async def read(self, path: str) -> bytes | None:
        target = self._root / path
        return target.read_bytes() if target.exists() else None


class AzureBlobStore(BlobStore):
    def __init__(self, settings: Settings) -> None:
        from azure.storage.blob.aio import BlobServiceClient

        self._client = BlobServiceClient.from_connection_string(settings.blob_connection_string)
        self._container = settings.blob_container

    async def write(self, path: str, content: bytes) -> str:
        container_client = self._client.get_container_client(self._container)
        blob_client = container_client.get_blob_client(path)
        await blob_client.upload_blob(content, overwrite=True)
        return blob_client.url

    async def read(self, path: str) -> bytes | None:
        container_client = self._client.get_container_client(self._container)
        blob_client = container_client.get_blob_client(path)
        try:
            stream = await blob_client.download_blob()
            return await stream.readall()
        except Exception:
            return None


def get_blob_store(settings: Settings) -> BlobStore:
    if settings.has_blob:
        return AzureBlobStore(settings)
    return LocalFileBlobStore(os.environ.get("LOCAL_BLOB_ROOT", ".data/blobs"))
