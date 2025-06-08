import asyncio
import importlib
import os
from typing import Dict, Type

import structlog
from prometheus_client import Counter, Gauge

from .workflow import BaseWorkflow, WorkflowResult

logger = structlog.get_logger()

class WorkflowProcessor:
    """Processes workflows from the queue."""

    def __init__(self, queue_manager):
        self.queue_manager = queue_manager
        self.workflows: Dict[str, Type[BaseWorkflow]] = {}
        self._logger = logger.bind(component="workflow_processor")
        self._running = False

        # Metrics
        self.workflow_executions = Counter(
            'workflow_executions_total',
            'Total number of workflow executions',
            ['workflow_name', 'status']
        )
        self.queue_size = Gauge(
            'workflow_queue_size',
            'Current size of workflow queue',
            ['workflow_name']
        )

    def register_workflow(self, workflow_class: Type[BaseWorkflow]) -> None:
        """Register a workflow class."""
        workflow_name = workflow_class.__name__
        self.workflows[workflow_name] = workflow_class
        self._logger.info("workflow_registered", workflow=workflow_name)

    async def start(self) -> None:
        """Start processing workflows."""
        self._running = True
        self._logger.info("processor_started")

        while self._running:
            for workflow_name, workflow_class in self.workflows.items():
                try:
                    # Get data from queue
                    data = await self.queue_manager.dequeue(workflow_name)
                    if not data:
                        continue

                    # Update queue size metric
                    self.queue_size.labels(workflow_name=workflow_name).set(
                        await self.queue_manager.get_queue_size(workflow_name)
                    )

                    # Execute workflow
                    workflow = workflow_class(data)
                    result = await workflow.execute()

                    # Update metrics
                    self.workflow_executions.labels(
                        workflow_name=workflow_name,
                        status='success' if result.success else 'failure'
                    ).inc()

                    if not result.success:
                        self._logger.error(
                            "workflow_failed",
                            workflow=workflow_name,
                            error=result.error
                        )

                except Exception as e:
                    self._logger.error(
                        "processor_error",
                        workflow=workflow_name,
                        error=str(e)
                    )

            await asyncio.sleep(1)  # Prevent tight loop

    def stop(self) -> None:
        """Stop processing workflows."""
        self._running = False
        self._logger.info("processor_stopped")

    def load_workflows(self, workflows_dir: str) -> None:
        """Load workflow classes from a directory."""
        for filename in os.listdir(workflows_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                module_name = filename[:-3]
                module = importlib.import_module(f'workflows.{module_name}')
                
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseWorkflow) and 
                        attr != BaseWorkflow):
                        self.register_workflow(attr)

async def main():
    """Main entry point for the workflow processor."""
    # Initialize queue manager
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    queue_manager = QueueManager(redis_url)
    await queue_manager.connect()

    # Load and start processor
    processor = WorkflowProcessor(queue_manager)
    
    try:
        await processor.start()
    except KeyboardInterrupt:
        await processor.stop()
    finally:
        await queue_manager.disconnect()

if __name__ == '__main__':
    asyncio.run(main()) 