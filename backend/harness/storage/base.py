"""Object-storage abstraction hiding the difference between local disk and MinIO/S3."""

from abc import ABC, abstractmethod


class ObjectStorage(ABC):
    """Object storage contract used by report generation.

    Implementations must be safe for concurrent calls. Methods that reference a
    missing object should return ``None`` rather than raising.
    """

    @abstractmethod
    async def upload_object(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        pass

    @abstractmethod
    async def download_object(self, bucket_name: str, object_name: str) -> bytes | None:
        pass

    @abstractmethod
    async def delete_object(self, bucket_name: str, object_name: str) -> None:
        pass

    @abstractmethod
    async def get_object_url(self, bucket_name: str, object_name: str, expires: int = 3600) -> str:
        pass

    @abstractmethod
    async def ensure_bucket_exists(self, bucket_name: str) -> None:
        pass

    @abstractmethod
    async def get_report_url_by_workflow_id(self, workflow_id: str) -> str | None:
        pass
