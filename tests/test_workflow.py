import pytest
from datetime import datetime
from src.core.workflow import BaseWorkflow, WorkflowConfig, WorkflowResult
from src.workflows.example_workflow import ExampleWorkflow, ExampleWorkflowConfig

@pytest.fixture
def example_config():
    return ExampleWorkflowConfig(
        name="test_workflow",
        description="Test workflow",
        enabled=True,
        interval=60,
        options={"test": True}
    )

@pytest.fixture
def example_workflow(example_config):
    return ExampleWorkflow(example_config)

@pytest.mark.asyncio
async def test_workflow_execution(example_workflow):
    """Test basic workflow execution."""
    test_data = {
        "test_field": "test_value",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    result = await example_workflow.execute(test_data)
    
    assert result.success
    assert result.data is not None
    assert "message" in result.data
    assert "timestamp" in result.data
    assert "config" in result.data
    assert result.execution_time > 0

@pytest.mark.asyncio
async def test_workflow_validation(example_workflow):
    """Test workflow validation."""
    valid_data = {
        "test_field": "test_value",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    assert await example_workflow.validate(valid_data)

@pytest.mark.asyncio
async def test_workflow_retry(example_workflow):
    """Test workflow retry mechanism."""
    class FailingWorkflow(ExampleWorkflow):
        async def process(self, data):
            if self.retry_count < 2:
                raise ValueError("Simulated failure")
            return await super().process(data)
    
    config = ExampleWorkflowConfig(
        name="failing_workflow",
        max_retries=3
    )
    workflow = FailingWorkflow(config)
    
    result = await workflow.execute({"test": "data"})
    
    assert result.success
    assert workflow.retry_count == 2

@pytest.mark.asyncio
async def test_workflow_cleanup(example_workflow):
    """Test workflow cleanup."""
    await example_workflow.cleanup()
    # Add assertions based on your cleanup implementation

@pytest.mark.asyncio
async def test_example_workflow():
    """Test the example workflow with configuration."""
    # Create workflow configuration
    config = ExampleWorkflowConfig(
        name="test_workflow",
        description="Test workflow",
        enabled=True,
        interval=60,
        options={"test": True}
    )
    
    # Create and execute workflow
    workflow = ExampleWorkflow(config)
    test_data = {"test": "data"}
    result = await workflow.execute(test_data)
    
    # Verify result
    assert result.success
    assert "message" in result.data
    assert "timestamp" in result.data
    assert "config" in result.data
    
    # Verify config data
    config_data = result.data["config"]
    assert config_data["name"] == "test_workflow"
    assert config_data["enabled"] is True
    assert config_data["interval"] == 60
    assert config_data["options"]["test"] is True
    
    # Verify timestamp is valid
    timestamp = datetime.fromisoformat(result.data["timestamp"])
    assert isinstance(timestamp, datetime)  