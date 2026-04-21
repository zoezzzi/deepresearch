from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from .session import Base
from app.research_assistant.models.enums import WorkflowStatus, TaskStatus, EvaluationStatus
from app.common.utils.time_utils import get_current_utc_time


class WorkflowModel(Base):
    __tablename__ = "workflows"

    workflow_id = Column(String, primary_key=True, index=True)
    topic = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.PENDING, nullable=False)
    report_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_current_utc_time, onupdate=get_current_utc_time, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    tasks = relationship("TaskModel", back_populates="workflow", cascade="all, delete-orphan", order_by="TaskModel.order")
    evaluations = relationship("EvaluationModel", back_populates="workflow", cascade="all, delete-orphan")


class TaskModel(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.workflow_id"), nullable=False)
    title = Column(String, nullable=False)
    intent = Column(Text, nullable=False)
    query = Column(Text, nullable=False)
    order = Column(Integer, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    summary = Column(Text, nullable=True)
    sources_summary = Column(Text, nullable=True)
    notices = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_current_utc_time, onupdate=get_current_utc_time, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    workflow = relationship("WorkflowModel", back_populates="tasks")


class EvaluationModel(Base):
    __tablename__ = "evaluation_results"
    
    evaluation_id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.workflow_id"), nullable=False, index=True)
    scenario_id = Column(String, nullable=True, index=True)
    
    # 动态指标存储：支持任意场景的评估指标
    metrics = Column(JSON, nullable=False, default=dict)
    overall_score = Column(Float, nullable=True)
    
    status = Column(Enum(EvaluationStatus), default=EvaluationStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    evaluation_details = Column(JSON, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_current_utc_time, onupdate=get_current_utc_time, nullable=False, index=True)
    
    workflow = relationship("WorkflowModel", back_populates="evaluations")
