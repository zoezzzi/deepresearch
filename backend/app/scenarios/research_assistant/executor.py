from uuid import UUID
from sqlalchemy.orm import Session

from app.scenarios.protocols import ScenarioExecutor, ScenarioMetadata, ScenarioUIConfig
from app.scenarios.research_assistant.config import (
    SCENARIO_ID,
    SCENARIO_NAME,
    SCENARIO_DESCRIPTION,
    SCENARIO_VERSION,
    SCENARIO_AUTHOR,
    SCENARIO_UI_CONFIG
)
from app.infrastructure.db.session import SessionLocal
from app.service_factory import create_research_service
from app.research_assistant.models.dtos import CreateResearchRequest
from harness.logger import logger


class ResearchAssistantExecutor(ScenarioExecutor):
    def __init__(self):
        self._metadata = ScenarioMetadata(
            scenario_id=SCENARIO_ID,
            name=SCENARIO_NAME,
            description=SCENARIO_DESCRIPTION,
            version=SCENARIO_VERSION,
            author=SCENARIO_AUTHOR,
            ui_config=ScenarioUIConfig(**SCENARIO_UI_CONFIG)
        )
    
    def get_metadata(self) -> ScenarioMetadata:
        return self._metadata
    
    def _get_db(self) -> Session:
        return SessionLocal()
    
    async def create_workflow(self, request: CreateResearchRequest) -> any:
        db = self._get_db()
        try:
            service = create_research_service(db)
            return await service.create_research_workflow(request)
        finally:
            db.close()
    
    async def execute_workflow(self, workflow_id: UUID) -> None:
        db = self._get_db()
        try:
            service = create_research_service(db)
            await service.execute_research_workflow(workflow_id)
        finally:
            db.close()
    
    async def get_workflow_status(self, workflow_id: UUID) -> any:
        db = self._get_db()
        try:
            service = create_research_service(db)
            return await service.get_workflow_status(workflow_id)
        finally:
            db.close()
    
    async def get_report_content(self, workflow_id: UUID) -> str | None:
        db = self._get_db()
        try:
            service = create_research_service(db)
            return await service.get_report_content(workflow_id)
        finally:
            db.close()
    
    def get_report_file_path(self, report_id: str) -> str | None:
        db = self._get_db()
        try:
            service = create_research_service(db)
            return service.get_report_file_path(report_id)
        finally:
            db.close()
