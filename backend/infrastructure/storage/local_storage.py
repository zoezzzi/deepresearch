from typing import Optional
from pathlib import Path
import uuid
from .base import ObjectStorage
from infrastructure.logger import logger


class LocalObjectStorage(ObjectStorage):
    def __init__(self, storage_path: str = None, url_prefix: str = None):
        from infrastructure.config import get_settings
        settings = get_settings()
        self.storage_path = Path(storage_path or settings.REPORT_STORAGE_PATH)
        self.url_prefix = url_prefix or settings.REPORT_URL_PREFIX
        logger.info(f"LocalObjectStorage initialized, storage path: {self.storage_path}")

    async def ensure_bucket_exists(self, bucket_name: str) -> None:
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured storage directory exists: {self.storage_path}")
        except Exception as e:
            logger.error(f"Error ensuring storage directory exists: {e}")
            raise

    async def upload_object(self, bucket_name: str, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
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

    async def download_object(self, bucket_name: str, object_name: str) -> Optional[bytes]:
        try:
            file_path = self.storage_path / object_name
            
            safe_file_path = file_path.resolve()
            if not safe_file_path.is_relative_to(self.storage_path.resolve()):
                logger.warning(f"Invalid object name, potential path traversal attack: {object_name}")
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
        try:
            file_path = self.storage_path / object_name
            
            safe_file_path = file_path.resolve()
            if not safe_file_path.is_relative_to(self.storage_path.resolve()):
                logger.warning(f"Invalid object name, potential path traversal attack: {object_name}")
                return
            
            if safe_file_path.exists():
                safe_file_path.unlink()
                logger.info(f"Deleted object: {object_name}")
        except Exception as e:
            logger.error(f"Error deleting object: {e}")
            raise

    async def get_object_url(self, bucket_name: str, object_name: str, expires: int = 3600) -> str:
        try:
            url = f"{self.url_prefix}/{object_name}"
            logger.info(f"Generated object URL: {url}")
            return url
        except Exception as e:
            logger.error(f"Error getting object URL: {e}")
            raise

    async def get_report_url_by_workflow_id(self, workflow_id: str) -> Optional[str]:
        """
        根据 workflow_id 查找已生成的报告 URL

        Args:
            workflow_id: 工作流 ID

        Returns:
            报告 URL，如果未找到则返回 None
        """
        try:
            # 扫描存储目录，查找匹配的报告文件
            # 报告文件名格式: {workflow_id}.md 或包含 workflow_id 的文件
            storage_dir = self.storage_path
            if not storage_dir.exists():
                logger.warning(f"[LocalObjectStorage] Storage directory not found: {storage_dir}")
                return None

            # 查找匹配的报告文件
            for file_path in storage_dir.glob("*.md"):
                # 检查文件名是否包含 workflow_id
                if workflow_id in file_path.name:
                    # 生成 URL
                    url = f"{self.url_prefix}/{file_path.name}"
                    logger.info(f"[LocalObjectStorage] Found report for workflow {workflow_id}: {url}")
                    return url

            logger.warning(f"[LocalObjectStorage] No report found for workflow {workflow_id}")
            return None
        except Exception as e:
            logger.error(f"[LocalObjectStorage] Error finding report for workflow {workflow_id}: {e}")
            return None
