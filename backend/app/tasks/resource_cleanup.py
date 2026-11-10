"""
资源清理和监控任务

定期清理过期资源，监控系统性能
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any

import psutil

from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


class ResourceMonitor:
    """
    资源监控器

    监控系统资源使用情况，生成告警
    """

    def __init__(self):
        self.metrics_history = []
        self.metrics_max_age = settings.MAX_CACHE_AGE

    async def collect_metrics(self) -> dict[str, Any]:
        """
        收集系统资源指标

        Returns:
            资源指标字典
        """
        try:
            process = psutil.Process(os.getpid())

            # 内存使用
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # CPU使用
            cpu_percent = process.cpu_percent(interval=0.1)

            # 磁盘使用
            disk_usage = psutil.disk_usage("/")

            metrics = {
                "timestamp": datetime.now().isoformat(),
                "memory": {
                    "rss_mb": memory_info.rss / (1024 * 1024),
                    "vms_mb": memory_info.vms / (1024 * 1024),
                    "percent": memory_percent,
                },
                "cpu": {"percent": cpu_percent},
                "disk": {
                    "total_gb": disk_usage.total / (1024 * 1024 * 1024),
                    "used_gb": disk_usage.used / (1024 * 1024 * 1024),
                    "free_gb": disk_usage.free / (1024 * 1024 * 1024),
                    "percent": disk_usage.percent,
                },
            }

            # 保存到历史记录
            self.metrics_history.append(metrics)

            # 清理过期历史记录
            self._cleanup_old_metrics()

            logger.debug(
                f"[ResourceMonitor] Collected metrics: memory={memory_percent}%, cpu={cpu_percent}%"
            )

            return metrics

        except Exception as e:
            logger.error(f"[ResourceMonitor] Failed to collect metrics: {str(e)}")
            return {}

    def _cleanup_old_metrics(self):
        """清理过期的历史指标"""
        cutoff_time = datetime.now() - timedelta(seconds=self.metrics_max_age)
        self.metrics_history = [
            metric
            for metric in self.metrics_history
            if datetime.fromisoformat(metric["timestamp"]) > cutoff_time
        ]

    def check_alerts(self, metrics: dict[str, Any]) -> dict[str, bool]:
        """
        检查告警条件

        Args:
            metrics: 资源指标

        Returns:
            告警状态字典
        """
        alerts = {"high_memory": False, "high_cpu": False, "high_disk": False}

        memory_percent = metrics.get("memory", {}).get("percent", 0)
        cpu_percent = metrics.get("cpu", {}).get("percent", 0)
        disk_percent = metrics.get("disk", {}).get("percent", 0)

        if memory_percent > 80:
            alerts["high_memory"] = True
            logger.warning(f"[ResourceMonitor] High memory usage: {memory_percent}%")

        if cpu_percent > 90:
            alerts["high_cpu"] = True
            logger.warning(f"[ResourceMonitor] High CPU usage: {cpu_percent}%")

        if disk_percent > 90:
            alerts["high_disk"] = True
            logger.warning(f"[ResourceMonitor] High disk usage: {disk_percent}%")

        return alerts


class ResourceCleanupTask:
    """
    资源清理任务

    定期清理过期文件和缓存
    """

    def __init__(self, monitor: ResourceMonitor):
        self.monitor = monitor
        self.cleanup_interval = settings.RESOURCE_CLEANUP_INTERVAL
        self.max_cache_age = settings.MAX_CACHE_AGE
        self.is_running = False

    async def run(self):
        """
        运行清理任务循环
        """
        logger.info(f"[ResourceCleanup] Starting with interval={self.cleanup_interval}s")

        self.is_running = True
        while self.is_running:
            try:
                await self._perform_cleanup()
                await self.monitor.collect_metrics()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                logger.info("[ResourceCleanup] Task cancelled")
                break
            except Exception as e:
                logger.error(f"[ResourceCleanup] Error during cleanup: {str(e)}")
                await asyncio.sleep(60)  # 出错后暂停一段时间再继续

    async def _perform_cleanup(self):
        """执行资源清理"""
        logger.info("[ResourceCleanup] Performing cleanup...")

        cleanup_summary = {"temp_files_removed": 0, "cache_files_removed": 0, "disk_space_freed": 0}

        # 清理临时文件
        cleanup_summary["temp_files_removed"] = await self._cleanup_temp_files()

        # 清理过期缓存
        cleanup_summary["cache_files_removed"] = await self._cleanup_old_cache()

        logger.info(f"[ResourceCleanup] Cleanup complete: {cleanup_summary}")

        return cleanup_summary

    async def _cleanup_temp_files(self) -> int:
        """清理临时文件"""
        temp_directories = ["/tmp", "./temp"]

        removed_count = 0

        for temp_dir in temp_directories:
            if not os.path.exists(temp_dir):
                continue

            try:
                cutoff_time = datetime.now() - timedelta(hours=24)

                for root, dirs, files in os.walk(temp_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)

                        try:
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                            if file_mtime < cutoff_time:
                                os.remove(file_path)
                                removed_count += 1
                                logger.debug(f"[ResourceCleanup] Removed temp file: {file_path}")

                        except Exception as e:
                            logger.debug(
                                f"[ResourceCleanup] Failed to remove file {file_path}: {str(e)}"
                            )

            except Exception as e:
                logger.error(f"[ResourceCleanup] Failed to cleanup temp dir {temp_dir}: {str(e)}")

        return removed_count

    async def _cleanup_old_cache(self) -> int:
        """清理过期缓存文件"""
        cache_directories = ["./cache"]

        removed_count = 0

        for cache_dir in cache_directories:
            if not os.path.exists(cache_dir):
                continue

            try:
                cutoff_time = datetime.now() - timedelta(seconds=self.max_cache_age)

                for root, dirs, files in os.walk(cache_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)

                        try:
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                            if file_mtime < cutoff_time:
                                os.remove(file_path)
                                removed_count += 1
                                logger.debug(f"[ResourceCleanup] Removed cache file: {file_path}")

                        except Exception as e:
                            logger.debug(
                                f"[ResourceCleanup] Failed to remove file {file_path}: {str(e)}"
                            )

            except Exception as e:
                logger.error(f"[ResourceCleanup] Failed to cleanup cache dir {cache_dir}: {str(e)}")

        return removed_count

    async def stop(self):
        """停止清理任务"""
        self.is_running = False
        logger.info("[ResourceCleanup] Task stopped")


# 全局单例
_monitor_instance = None
_cleanup_task_instance = None


def get_resource_monitor() -> ResourceMonitor:
    """获取资源监控器单例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ResourceMonitor()
    return _monitor_instance


def get_resource_cleanup_task() -> ResourceCleanupTask:
    """获取资源清理任务单例"""
    global _cleanup_task_instance
    if _cleanup_task_instance is None:
        monitor = get_resource_monitor()
        _cleanup_task_instance = ResourceCleanupTask(monitor)
    return _cleanup_task_instance
