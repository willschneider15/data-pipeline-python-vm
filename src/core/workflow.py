from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

class WorkflowConfig(BaseModel):
    """Configuration for a workflow instance."""
    name: str
    max_retries: int = 3
    enabled: bool = True

class WorkflowResult(BaseModel):
    """Result of a workflow execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0

class BaseWorkflow(ABC):
    """Base class for all workflows."""
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.retry_count = 0
        self._logger = logger.bind(workflow_name=config.name)
        self.start_time = datetime.now()

    async def execute(self, data: Dict[str, Any]) -> WorkflowResult:
        """Execute the workflow with the given data."""
        self._logger.info("workflow_started", data_size=len(str(data)))

        try:
            result = await self.process(data)
            execution_time = (datetime.now() - self.start_time).total_seconds()
            
            return WorkflowResult(
                success=True,
                data=result,
                execution_time=execution_time
            )

        except Exception as e:
            self._logger.error("workflow_failed", error=str(e))
            execution_time = (datetime.now() - self.start_time).total_seconds()
            
            if self.retry_count < self.config.max_retries:
                self.retry_count += 1
                self._logger.info("retrying_workflow", attempt=self.retry_count)
                return await self.execute(data)

            return WorkflowResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    @abstractmethod
    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the workflow data. Must be implemented by subclasses."""
        pass

    async def validate(self, data: Dict[str, Any]) -> bool:
        """Validate the input data. Can be overridden by subclasses."""
        return True

    async def cleanup(self) -> None:
        """Cleanup resources after workflow execution. Can be overridden by subclasses."""
        pass 