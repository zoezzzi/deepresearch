from typing import TypedDict, List, Optional, Any, Dict
from datetime import datetime


class WorkflowState(TypedDict, total=False):
    """
    工作流状态类型定义
    
    用于在 LangGraph 工作流节点之间传递状态信息。
    使用 total=False 允许字段可选，便于增量更新。
    
    Fields:
        workflow_id: 工作流唯一标识
        topic: 研究主题
        description: 研究描述
        tasks: 任务列表，每个任务包含 task_id, title, intent, query, order, status
        current_task_index: 当前执行的任务索引
        task_results: 任务执行结果列表
        report_content: 生成的报告内容
        report_url: 报告存储URL
        error: 错误信息（如果有）
        created_at: 创建时间
        updated_at: 更新时间
        workflow_status: 工作流完成状态 (all_success, partial_failed, all_failed, report_failed)
        task_summary: 任务执行摘要 {total, completed, failed}
    """
    
    # 基础信息
    workflow_id: str
    topic: str
    description: Optional[str]
    
    # 任务相关
    tasks: List[Dict[str, Any]]
    current_task_index: int
    task_results: List[Dict[str, Any]]
    
    # 报告相关
    report_content: Optional[str]
    report_url: Optional[str]
    
    # 错误信息
    error: Optional[str]
    
    # 时间戳
    created_at: datetime
    updated_at: datetime
    
    # 新增：工作流完成状态
    workflow_status: Optional[str]  # all_success, partial_failed, all_failed, report_failed
    task_summary: Optional[Dict[str, int]]  # {total: int, completed: int, failed: int}
