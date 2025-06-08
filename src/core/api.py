from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
import asyncio
import json

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import structlog
from pydantic import BaseModel
import aiohttp

from .queue import QueueManager

logger = structlog.get_logger()

class WebhookPayload(BaseModel):
    """Model for webhook payload validation."""
    workflow_name: str
    data: Dict[str, Any]

class APIServer:
    """FastAPI server for data ingestion with support for multiple triggers."""

    def __init__(
        self,
        queue_manager: QueueManager,
        scheduled_tasks: Optional[Dict[str, Callable[[], Awaitable[None]]]] = None
    ):
        self.app = FastAPI(title="Data VM Processing API")
        self.queue_manager = queue_manager
        self.scheduled_tasks = scheduled_tasks or {}
        self._logger = logger.bind(component="api_server")
        self._setup_middleware()
        self._setup_routes()

    def _setup_middleware(self) -> None:
        """Setup middleware for the FastAPI application."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self) -> None:
        """Setup API routes."""
        
        @self.app.post("/webhook/{workflow_name}")
        async def webhook_endpoint(
            workflow_name: str,
            payload: WebhookPayload,
            background_tasks: BackgroundTasks
        ):
            """Webhook endpoint for workflow ingestion."""
            background_tasks.add_task(
                self.queue_manager.enqueue,
                workflow_name,
                payload.data
            )
            return {"status": "success", "message": "Data enqueued successfully"}

        @self.app.websocket("/ws/{workflow_name}")
        async def websocket_endpoint(websocket: WebSocket, workflow_name: str):
            """WebSocket endpoint for real-time data ingestion."""
            await websocket.accept()
            self._logger.info("websocket_connected", workflow=workflow_name)

            try:
                while True:
                    data = await websocket.receive_json()
                    await self.queue_manager.enqueue(workflow_name, data)
                    await websocket.send_json({
                        "status": "success",
                        "message": "Data enqueued successfully"
                    })

            except Exception as e:
                self._logger.error("websocket_error", error=str(e))
                await websocket.close()

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat()
            }

    async def start_scheduled_tasks(self) -> None:
        """Start all scheduled tasks."""
        for task_name, task_func in self.scheduled_tasks.items():
            asyncio.create_task(self._run_scheduled_task(task_name, task_func))

    async def _run_scheduled_task(
        self,
        task_name: str,
        task_func: Callable[[], Awaitable[None]]
    ) -> None:
        """Run a scheduled task continuously."""
        while True:
            try:
                await task_func()
            except Exception as e:
                self._logger.error(
                    "scheduled_task_error",
                    task=task_name,
                    error=str(e)
                )
            await asyncio.sleep(60)  # Run every minute

    async def start(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Start the API server."""
        import uvicorn
        
        # Start scheduled tasks
        await self.start_scheduled_tasks()
        
        # Start API server
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

async def fetch_external_api(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Helper function to make HTTP requests to external APIs."""
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method,
            url,
            headers=headers,
            json=data
        ) as response:
            return await response.json() 