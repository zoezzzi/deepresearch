from sqlalchemy import JSON, BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.common.utils.time_utils import get_current_utc_time
from harness.db.session import Base


class WorkflowModel(Base):
    __tablename__ = "workflows"

    workflow_id = Column(String, primary_key=True, index=True)
    topic = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    report_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_current_utc_time,
        onupdate=get_current_utc_time,
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    tasks = relationship(
        "TaskModel",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="TaskModel.order",
    )
    evaluations = relationship(
        "EvaluationModel", back_populates="workflow", cascade="all, delete-orphan"
    )


class TaskModel(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, ForeignKey("workflows.workflow_id"), nullable=False)
    title = Column(String, nullable=False)
    intent = Column(Text, nullable=False)
    query = Column(Text, nullable=False)
    order = Column(Integer, nullable=False, default=0)
    depends_on = Column(JSON, nullable=True, default=list)
    status = Column(String(50), nullable=False, default="pending")
    summary = Column(Text, nullable=True)
    sources_summary = Column(Text, nullable=True)
    notices = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_current_utc_time,
        onupdate=get_current_utc_time,
        nullable=False,
    )
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

    status = Column(String(50), default="pending", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    evaluation_details = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_current_utc_time,
        onupdate=get_current_utc_time,
        nullable=False,
        index=True,
    )

    workflow = relationship("WorkflowModel", back_populates="evaluations")


class WorkflowTraceModel(Base):
    __tablename__ = "workflow_trace"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), unique=True, nullable=False, index=True)
    workflow_id = Column(String(64), unique=True, nullable=False, index=True)
    request_id = Column(String(64), nullable=True)
    scenario_id = Column(String(64), nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    status = Column(String(32), nullable=False, default="running", index=True)

    langsmith_run_id = Column(String(64), nullable=True)
    langsmith_url = Column(String(512), nullable=True)

    execute_duration_ms = Column(Integer, nullable=True)

    input_topic = Column(Text, nullable=True)
    input_description = Column(Text, nullable=True)
    output_report_url = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_current_utc_time,
        onupdate=get_current_utc_time,
        nullable=False,
    )


class WorkflowTaskTraceModel(Base):
    __tablename__ = "workflow_task_trace"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trace_id = Column(String(64), nullable=False, index=True)
    workflow_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=False, index=True)
    span_id = Column(String(64), unique=True, nullable=False, index=True)

    task_title = Column(String(256), nullable=False)
    task_order = Column(Integer, nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    status = Column(String(32), nullable=False, default="pending", index=True)

    input_query = Column(Text, nullable=True)
    input_intent = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    output_sources = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    langsmith_run_id = Column(String(64), nullable=True)

    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=get_current_utc_time, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_current_utc_time,
        onupdate=get_current_utc_time,
        nullable=False,
    )
