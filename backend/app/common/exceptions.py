"""
自定义异常类模块

定义项目中使用的自定义异常，便于错误处理和问题定位。
"""


class CheckpointConnectionError(Exception):
    """
    Checkpoint 存储连接失败异常

    当 AsyncPostgresSaver 无法连接到数据库且重试耗尽时抛出。
    此异常表示持久化存储不可用，需要上层业务逻辑处理。

    Attributes:
        message: 错误描述信息
        thread_id: 关联的工作流线程ID（如果有）
        retry_count: 已尝试的重试次数
    """

    def __init__(self, message: str, thread_id: str = None, retry_count: int = 0):
        self.message = message
        self.thread_id = thread_id
        self.retry_count = retry_count
        super().__init__(self.message)

    def __str__(self):
        if self.thread_id:
            return f"[CheckpointConnectionError] {self.message} | thread_id={self.thread_id} | retries={self.retry_count}"
        return f"[CheckpointConnectionError] {self.message} | retries={self.retry_count}"


class WorkflowExecutionError(Exception):
    """
    工作流执行异常

    当工作流执行过程中发生不可恢复的错误时抛出。
    """

    def __init__(self, message: str, thread_id: str = None, original_error: Exception = None):
        self.message = message
        self.thread_id = thread_id
        self.original_error = original_error
        super().__init__(self.message)

    def __str__(self):
        if self.thread_id:
            return f"[WorkflowExecutionError] {self.message} | thread_id={self.thread_id}"
        return f"[WorkflowExecutionError] {self.message}"


class ResearchServiceError(Exception):
    """
    研究服务异常

    当研究服务（如报告生成、数据分析）发生错误时抛出。
    """

    def __init__(self, message: str, service_name: str = None):
        self.message = message
        self.service_name = service_name
        super().__init__(self.message)

    def __str__(self):
        if self.service_name:
            return f"[ResearchServiceError:{self.service_name}] {self.message}"
        return f"[ResearchServiceError] {self.message}"
