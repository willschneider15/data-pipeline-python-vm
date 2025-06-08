import pytest
from src.core.workflow import BaseWorkflow, WorkflowConfig, WorkflowResult
from datetime import datetime

class TestConfig(WorkflowConfig):
    """Test configuration."""
    name: str = "test"
    description: str = "Test workflow for GitHub Actions"
    enabled: bool = True
    interval: int = 60

class TestWorkflow(BaseWorkflow):
    """Test workflow implementation."""
    
    def __init__(self, config: TestConfig):
        super().__init__(config)
        self.config = config

    async def process(self, data: dict) -> dict:
        """Process the data."""
        return {
            "timestamp": datetime.now().isoformat(),
            "test_value": "success",
            "config": self.config.model_dump()
        }

    async def execute(self, data: dict) -> WorkflowResult:
        """Execute the test workflow."""
        try:
            processed_data = await self.process(data)
            
            return WorkflowResult(
                success=True,
                data=processed_data,
                execution_time=0.1
            )
        except Exception as e:
            return WorkflowResult(
                success=False,
                error=str(e)
            )

@pytest.mark.asyncio
async def test_workflow_config():
    """Test workflow configuration."""
    config = TestConfig()
    assert config.name == "test"
    assert config.enabled is True
    assert config.interval == 60

@pytest.mark.asyncio
async def test_workflow_execution():
    """Test workflow execution."""
    config = TestConfig()
    workflow = TestWorkflow(config)
    
    result = await workflow.execute({})
    
    assert result.success
    assert "timestamp" in result.data
    assert result.data["test_value"] == "success"
    assert "config" in result.data
    assert result.execution_time == 0.1

@pytest.mark.asyncio
async def test_workflow_error_handling():
    """Test workflow error handling."""
    class FailingWorkflow(BaseWorkflow):
        async def process(self, data: dict) -> dict:
            raise Exception("Test error")
    
    config = TestConfig()
    workflow = FailingWorkflow(config)
    
    result = await workflow.execute({})
    
    assert not result.success
    assert result.error == "Test error"
    assert result.data is None 