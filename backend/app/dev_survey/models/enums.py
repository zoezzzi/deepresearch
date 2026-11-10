from enum import Enum


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    ALL_SUCCESS = "all_success"
    PARTIAL_FAILED = "partial_failed"
    ALL_FAILED = "all_failed"
    REPORT_FAILED = "report_failed"

    @classmethod
    def is_terminal_status(cls, status: str) -> bool:
        terminal_statuses = [
            cls.ALL_SUCCESS.value,
            cls.PARTIAL_FAILED.value,
            cls.ALL_FAILED.value,
            cls.REPORT_FAILED.value,
        ]
        return status in terminal_statuses

    @classmethod
    def from_string(cls, value: str) -> "WorkflowStatus":
        try:
            return cls(value)
        except ValueError:
            if value == "completed":
                return cls.ALL_SUCCESS
            elif value == "failed":
                return cls.ALL_FAILED
            else:
                raise ValueError(f"Invalid workflow status: {value}")

    @classmethod
    def to_display_status(cls, status: "WorkflowStatus") -> str:
        if status in [cls.ALL_SUCCESS, cls.PARTIAL_FAILED]:
            return "completed"
        if status in [cls.ALL_FAILED, cls.REPORT_FAILED]:
            return "failed"
        return status.value


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EvaluationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
