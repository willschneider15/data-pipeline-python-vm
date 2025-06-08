from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
import structlog

from src.core.workflow import BaseWorkflow, WorkflowResult, WorkflowConfig

logger = structlog.get_logger()

class ExampleWorkflowConfig(WorkflowConfig):
    """Configuration for the example workflow."""
    name: str
    description: Optional[str] = None
    enabled: bool = True
    interval: int = 300  # seconds
    options: Dict[str, Any] = {}

class ExampleWorkflow(BaseWorkflow):
    """Example workflow that demonstrates basic workflow functionality."""
    
    def __init__(self, config: ExampleWorkflowConfig):
        super().__init__(config)
        self._logger = logger.bind(workflow="example_workflow")

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the input data.
        
        Args:
            data: Input data to process
            
        Returns:
            Processed data
        """
        self._logger.info("processing_data", data=self.config.model_dump())
        
        # Simulate some work
        await self._simulate_work()
        
        return {
            "message": "Example workflow completed successfully",
            "timestamp": datetime.now().isoformat(),
            "config": self.config.model_dump()
        }
            
    async def _simulate_work(self):
        """Simulate some asynchronous work."""
        import asyncio
        await asyncio.sleep(1)  # Simulate work 