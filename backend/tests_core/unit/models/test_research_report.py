"""
ResearchReport 模型测试
"""
import pytest
from datetime import datetime
from core.models import ResearchReport


class TestResearchReportCreation:
    """ResearchReport 创建测试"""

    def test_report_creation_basic(self, sample_workflow_id):
        """验证 ResearchReport 基本创建"""
        report = ResearchReport(
            report_id="report-123",
            workflow_id=sample_workflow_id,
            content="# Test Report",
            url="/reports/report-123"
        )
        
        assert report.report_id == "report-123"
        assert report.workflow_id == sample_workflow_id
        assert report.content == "# Test Report"
        assert report.url == "/reports/report-123"

    def test_report_creation_auto_timestamp(self, sample_workflow_id):
        """验证 ResearchReport 自动时间戳"""
        report = ResearchReport(
            report_id="report-123",
            workflow_id=sample_workflow_id,
            content="# Test Report",
            url="/reports/report-123"
        )
        
        assert report.created_at is not None
        assert report.updated_at is not None

    def test_report_creation_explicit_timestamp(self, sample_workflow_id):
        """验证 ResearchReport 显式时间戳"""
        explicit_time = datetime(2024, 1, 1, 12, 0, 0)
        report = ResearchReport(
            report_id="report-123",
            workflow_id=sample_workflow_id,
            content="# Test Report",
            url="/reports/report-123",
            created_at=explicit_time,
            updated_at=explicit_time
        )
        
        assert report.created_at == explicit_time
        assert report.updated_at == explicit_time


class TestResearchReportUpdates:
    """ResearchReport 更新测试"""

    def test_report_update_content(self, sample_research_report):
        """验证更新内容"""
        initial_updated_at = sample_research_report.updated_at
        sample_research_report.update_content("# Updated Report")
        
        assert sample_research_report.content == "# Updated Report"
        assert sample_research_report.updated_at >= initial_updated_at

    def test_report_update_url(self, sample_research_report):
        """验证更新 URL"""
        initial_updated_at = sample_research_report.updated_at
        sample_research_report.update_url("/reports/new-url")
        
        assert sample_research_report.url == "/reports/new-url"
        assert sample_research_report.updated_at >= initial_updated_at


class TestResearchReportSerialization:
    """ResearchReport 序列化测试"""

    def test_report_model_dump(self, sample_research_report):
        """验证 ResearchReport 模型转字典"""
        data = sample_research_report.model_dump()
        
        assert data["report_id"] == sample_research_report.report_id
        assert data["workflow_id"] == sample_research_report.workflow_id
        assert data["content"] == sample_research_report.content
        assert data["url"] == sample_research_report.url
