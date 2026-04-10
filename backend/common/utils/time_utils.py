from datetime import datetime, timezone
from typing import Optional


def get_current_utc_time() -> datetime:
    """获取当前UTC时间（带时区信息）"""
    return datetime.now(timezone.utc)


def get_current_local_time() -> datetime:
    """获取当前本地时间（带时区信息）"""
    return datetime.now().astimezone()


def utc_to_local(dt: datetime) -> datetime:
    """将UTC时间转换为本地时间"""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def local_to_utc(dt: datetime) -> datetime:
    """将本地时间转换为UTC时间"""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


def format_utc(dt: Optional[datetime]) -> Optional[str]:
    """格式化为UTC时间字符串"""
    if dt is None:
        return None
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def format_local(dt: Optional[datetime]) -> Optional[str]:
    """格式化为本地时间字符串"""
    if dt is None:
        return None
    local_dt = utc_to_local(dt)
    return local_dt.isoformat()
