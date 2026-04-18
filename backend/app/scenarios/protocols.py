from typing import Protocol, Any
from uuid import UUID
from pydantic import BaseModel


class ScenarioUIConfig(BaseModel):
    navbar_title: str | None = None
    form_title: str | None = None
    topic_label: str | None = None
    topic_placeholder: str | None = None


class ScenarioMetadata(BaseModel):
    scenario_id: str
    name: str
    description: str
    version: str
    author: str | None = None
    ui_config: ScenarioUIConfig | None = None


class ScenarioExecutor(Protocol):
    def get_metadata(self) -> ScenarioMetadata:
        ...
    
    async def create_workflow(self, request: Any) -> Any:
        ...
    
    async def execute_workflow(self, workflow_id: UUID) -> None:
        ...
    
    async def get_workflow_status(self, workflow_id: UUID) -> Any:
        ...
    
    async def get_report_content(self, workflow_id: UUID) -> str | None:
        ...
    
    def get_report_file_path(self, report_id: str) -> str | None:
        ...
