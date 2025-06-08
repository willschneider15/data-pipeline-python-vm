import pytest
from src.core.workflow import BaseWorkflow, WorkflowConfig, WorkflowResult
from datetime import datetime

@pytest.fixture
def test_config():
    """Fixture to create test configuration."""
    class TestConfig(WorkflowConfig):
        name: str = "test"
        description: str = "Test workflow configuration"
        enabled: bool = True
        interval: int = 60
        options: dict = {"test": True}
    return TestConfig()

@pytest.fixture
def test_workflow(test_config):
    """Fixture to create test workflow."""
    class TestWorkflow(BaseWorkflow):
        def __init__(self, config):
            super().__init__(config)
            self.max_retries = 3

        async def process(self, data):
            if data.get("should_fail"):
                raise Exception("Test error")
            return {
                "timestamp": datetime.now().isoformat(),
                "test_value": "success",
                "config": self.config.model_dump()
            }

        async def execute(self, data):
            try:
                result = await self.process(data)
                return WorkflowResult(success=True, data=result, execution_time=0.1)
            except Exception as e:
                return WorkflowResult(success=False, error=str(e))

    return TestWorkflow(test_config)

@pytest.mark.asyncio
async def test_workflow_config(test_config):
    """Test workflow configuration."""
    assert test_config.name == "test"
    assert test_config.enabled is True
    assert test_config.interval == 60
    assert test_config.options == {"test": True}

@pytest.mark.asyncio
async def test_workflow_execution(test_workflow):
    """Test workflow execution with success case."""
    result = await test_workflow.execute({})
    assert result.success
    assert "timestamp" in result.data
    assert result.data["test_value"] == "success"
    assert "config" in result.data
    assert result.execution_time == 0.1

@pytest.mark.asyncio
async def test_workflow_failure(test_workflow):
    """Test workflow execution with failure case."""
    result = await test_workflow.execute({"should_fail": True})
    assert not result.success
    assert "Test error" in result.error

@pytest.mark.asyncio
async def test_workflow_retry(test_workflow):
    """Test workflow retry mechanism."""
    attempts = 0
    while attempts < test_workflow.max_retries:
        result = await test_workflow.execute({"should_fail": True})
        attempts += 1
        if result.success:
            break
    assert attempts == test_workflow.max_retries

@pytest.mark.asyncio
async def test_workflow_error_handling(test_config):
    """Test workflow error handling."""
    class FailingWorkflow(BaseWorkflow):
        async def process(self, data: dict) -> dict:
            raise Exception("Test error")
    
    workflow = FailingWorkflow(test_config)
    result = await workflow.execute({})
    
    assert not result.success
    assert result.error == "Test error"
    assert result.data is None 