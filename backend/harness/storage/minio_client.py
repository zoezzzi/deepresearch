from io import BytesIO

from minio import Minio
from minio.error import S3Error

from harness.config import get_harness_settings
from harness.logger import logger
from harness.storage.base import ObjectStorage

settings = get_harness_settings()


class MinioObjectStorage(ObjectStorage):
    """MinIO / S3-compatible implementation.

    The MinIO SDK is synchronous and is called directly on the event loop. That
    is acceptable for low-volume report writes; high-concurrency workloads
    should offload these calls to a thread pool.
    """

    def __init__(self):
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.secure = settings.MINIO_SECURE
        self.default_bucket = settings.MINIO_BUCKET

        self.client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )
        logger.info("MinioObjectStorage initialized")

    async def ensure_bucket_exists(self, bucket_name: str) -> None:
        """Create the bucket when it does not exist yet."""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise

    async def upload_object(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes and return a presigned GET URL."""
        try:
            data_stream = BytesIO(data)
            data_stream.seek(0)

            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data_stream,
                length=len(data),
                content_type=content_type,
            )
            logger.info(f"Uploaded object: {bucket_name}/{object_name}")
            return await self.get_object_url(bucket_name, object_name)
        except S3Error as e:
            logger.error(f"Error uploading object: {e}")
            raise

    async def download_object(self, bucket_name: str, object_name: str) -> bytes | None:
        """Download an object; returns None when the key does not exist."""
        try:
            response = self.client.get_object(bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Downloaded object: {bucket_name}/{object_name}")
            return data
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.warning(f"Object not found: {bucket_name}/{object_name}")
                return None
            logger.error(f"Error downloading object: {e}")
            raise

    async def delete_object(self, bucket_name: str, object_name: str) -> None:
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted object: {bucket_name}/{object_name}")
        except S3Error as e:
            logger.error(f"Error deleting object: {e}")
            raise

    async def get_object_url(self, bucket_name: str, object_name: str, expires: int = 3600) -> str:
        try:
            url = self.client.presigned_get_object(
                bucket_name=bucket_name, object_name=object_name, expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"Error getting object URL: {e}")
            raise

    async def get_report_url_by_workflow_id(self, workflow_id: str) -> str | None:
        return None
