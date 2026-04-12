from enum import Enum


class WorkflowStatus(str, Enum):
    """
    工作流状态
    
    状态流转:
    - pending → running → [all_success | partial_failed | all_failed | report_failed]
    
    新的详细状态:
    - ALL_SUCCESS: 全部任务成功，报告生成成功
    - PARTIAL_FAILED: 部分任务失败，报告生成成功
    - ALL_FAILED: 全部任务失败，不生成报告
    - REPORT_FAILED: 全部任务成功，但报告生成失败
    """
    
    # 基础状态
    PENDING = "pending"
    RUNNING = "running"
    
    # 新的详细状态
    ALL_SUCCESS = "all_success"           # 全部任务成功，报告生成成功
    PARTIAL_FAILED = "partial_failed"     # 部分任务失败，报告生成成功
    ALL_FAILED = "all_failed"             # 全部任务失败，不生成报告
    REPORT_FAILED = "report_failed"       # 全部任务成功，但报告生成失败
    
    @classmethod
    def is_terminal_status(cls, status: "WorkflowStatus") -> bool:
        """检查是否为终止状态"""
        terminal_statuses = [
            cls.ALL_SUCCESS,
            cls.PARTIAL_FAILED,
            cls.ALL_FAILED,
            cls.REPORT_FAILED
        ]
        return status in terminal_statuses
    
    @classmethod
    def from_string(cls, value: str) -> "WorkflowStatus":
        """从字符串创建状态，支持向后兼容"""
        try:
            return cls(value)
        except ValueError:
            # 向后兼容处理
            if value == "completed":
                return cls.ALL_SUCCESS
            elif value == "failed":
                return cls.ALL_FAILED
            else:
                raise ValueError(f"Invalid workflow status: {value}")
    
    @classmethod
    def to_display_status(cls, status: "WorkflowStatus") -> str:
        """
        转换为前端显示的状态
        
        映射规则:
        - ALL_SUCCESS, PARTIAL_FAILED → completed
        - ALL_FAILED, REPORT_FAILED → failed
        - PENDING, RUNNING → 保持原样
        """
        if status in [cls.ALL_SUCCESS, cls.PARTIAL_FAILED]:
            return "completed"
        if status in [cls.ALL_FAILED, cls.REPORT_FAILED]:
            return "failed"
        return status.value
