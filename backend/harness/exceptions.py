"""
harness 层异常定义

包含 harness 层使用的异常类，避免依赖 app 层
"""


class CheckpointConnectionError(Exception):
    """Checkpoint 连接错误"""
    def __init__(self, message: str, thread_id: str = None, retry_count: int = 0):
        self.message = message
        self.thread_id = thread_id
        self.retry_count = retry_count
        super().__init__(message)
