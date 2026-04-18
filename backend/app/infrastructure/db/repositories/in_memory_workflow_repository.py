from typing import Optional, Dict
from domain.repositories.workflow_repository import WorkflowRepository
from domain.entities.workflow import Workflow
from harness.logger import logger


class InMemoryWorkflowRepository(WorkflowRepository):
    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}

    async def save(self, workflow: Workflow) -> None:
        logger.info(f"[InMemory] Saving workflow: {workflow.workflow_id.value}")
        self._workflows[workflow.workflow_id.value] = workflow

    async def find_by_id(self, workflow_id: str) -> Optional[Workflow]:
        logger.info(f"[InMemory] Finding workflow by id: {workflow_id}")
        return self._workflows.get(workflow_id)

    async def update(self, workflow: Workflow) -> None:
        logger.info(f"[InMemory] Updating workflow: {workflow.workflow_id.value}")
        self._workflows[workflow.workflow_id.value] = workflow
