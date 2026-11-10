import uuid
from pathlib import Path

from harness.config import get_harness_settings
from harness.logger import logger
from harness.storage.base import ObjectStorage


class LocalObjectStorage(ObjectStorage):
    """Local-filesystem implementation mapping object names to paths under the storage root.

    Every read and write validates the resolved path, blocking ``../`` escapes
    outside the storage directory.
    """

    def __init__(self, storage_path: str = None, url_prefix: str = None):
        settings = get_harness_settings()
        self.storage_path = Path(storage_path or settings.REPORT_STORAGE_PATH)
        self.url_prefix = url_prefix or "/research/reports"
        logger.debug(f"LocalObjectStorage initialized, storage path: {self.storage_path}")

    async def ensure_bucket_exists(self, bucket_name: str) -> None:
        """Create the storage directory if needed; ``bucket_name`` is ignored locally."""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured storage directory exists: {self.storage_path}")
        except Exception as e:
            logger.error(f"Error ensuring storage directory exists: {e}")
            raise

    async def upload_object(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Write bytes to disk and return the public URL.

        An empty ``object_name`` is replaced with a random UUID filename.
        """
        try:
            await self.ensure_bucket_exists(bucket_name)

            if not object_name:
                object_name = f"{uuid.uuid4()}.md"

            file_path = self.storage_path / object_name

            safe_file_path = file_path.resolve()
            if not safe_file_path.is_relative_to(self.storage_path.resolve()):
                raise ValueError("Invalid object name, potential path traversal attack")

            safe_file_path.write_bytes(data)
            logger.info(f"Saved report to: {safe_file_path}")

            return await self.get_object_url(bucket_name, object_name)
        except Exception as e:
            logger.error(f"Error uploading object: {e}")
            raise

    async def download_object(self, bucket_name: str, object_name: str) -> bytes | None:
        """Read an object; returns None for missing or unsafe paths."""
        try:
            file_path = self.storage_path / object_name

            safe_file_path = file_path.resolve()
            if not safe_file_path.is_relative_to(self.storage_path.resolve()):
                logger.warning(
                    f"Invalid object name, potential path traversal attack: {object_name}"
                )
                return None

            if not safe_file_path.exists():
                logger.warning(f"Object not found: {object_name}")
                return None

            data = safe_file_path.read_bytes()
            logger.info(f"Downloaded object: {object_name}")
            return data
        except Exception as e:
            logger.error(f"Error downloading object: {e}")
            raise

    async def delete_object(self, bucket_name: str, object_name: str) -> None:
        """Delete an object if it exists; unsafe paths are ignored."""
        try:
            file_path = self.storage_path / object_name

            safe_file_path = file_path.resolve()
            if not safe_file_path.is_relative_to(self.storage_path.resolve()):
                logger.warning(
                    f"Invalid object name, potential path traversal attack: {object_name}"
                )
                return

            if safe_file_path.exists():
                safe_file_path.unlink()
                logger.info(f"Deleted object: {object_name}")
        except Exception as e:
            logger.error(f"Error deleting object: {e}")
            raise

    async def get_object_url(self, bucket_name: str, object_name: str, expires: int = 3600) -> str:
        """Build a static URL; ``expires`` is irrelevant for local storage."""
        try:
            url = f"{self.url_prefix}/{object_name}"
            logger.info(f"Generated object URL: {url}")
            return url
        except Exception as e:
            logger.error(f"Error getting object URL: {e}")
            raise

    async def get_report_url_by_workflow_id(self, workflow_id: str) -> str | None:
        """Find a markdown report whose filename contains the workflow id."""
        try:
            storage_dir = self.storage_path
            if not storage_dir.exists():
                logger.warning(f"[LocalObjectStorage] Storage directory not found: {storage_dir}")
                return None

            for file_path in storage_dir.glob("*.md"):
                if workflow_id in file_path.name:
                    url = f"{self.url_prefix}/{file_path.name}"
                    logger.info(
                        f"[LocalObjectStorage] Found report for workflow {workflow_id}: {url}"
                    )
                    return url

            logger.warning(f"[LocalObjectStorage] No report found for workflow {workflow_id}")
            return None
        except Exception as e:
            logger.error(
                f"[LocalObjectStorage] Error finding report for workflow {workflow_id}: {e}"
            )
            return None

    async def read_file(self, object_name: str) -> str | None:
        """Read a report as UTF-8 text; returns None when absent or undecodable."""
        try:
            content_bytes = await self.download_object("reports", object_name)
            if content_bytes:
                return content_bytes.decode("utf-8")
            return None
        except Exception as e:
            logger.error(f"[LocalObjectStorage] Error reading file: {e}")
            return None
