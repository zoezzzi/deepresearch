from typing import Optional
from minio import Minio
from minio.error import S3Error
from io import BytesIO
from .base import ObjectStorage
from infrastructure.config import get_settings
from infrastructure.logger import logger

settings = get_settings()


class MinioObjectStorage(ObjectStorage):
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
            secure=self.secure
        )
        logger.info("MinioObjectStorage initialized")

    async def ensure_bucket_exists(self, bucket_name: str) -> None:
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise

    async def upload_object(self, bucket_name: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        try:
            data_stream = BytesIO(data)
            data_stream.seek(0)
            
            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data_stream,
                length=len(data),
                content_type=content_type
            )
            logger.info(f"Uploaded object: {bucket_name}/{object_name}")
            return await self.get_object_url(bucket_name, object_name)
        except S3Error as e:
            logger.error(f"Error uploading object: {e}")
            raise

    async def download_object(self, bucket_name: str, object_name: str) -> Optional[bytes]:
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
                bucket_name=bucket_name,
                object_name=object_name,
                expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"Error getting object URL: {e}")
            raise
