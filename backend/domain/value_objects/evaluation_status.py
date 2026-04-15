from enum import Enum


class EvaluationStatus(str, Enum):
    """
    评估状态
    """
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    
    @classmethod
    def is_terminal_status(cls, status: "EvaluationStatus") -> bool:
        """检查是否为终止状态"""
        terminal_statuses = [
            cls.COMPLETED,
            cls.FAILED
        ]
        return status in terminal_statuses
