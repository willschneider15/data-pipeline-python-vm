from typing import Any, Dict, Optional, List
from datetime import datetime
import json
import os

import aioredis
import structlog

from src.core.config import get_redis_config

logger = structlog.get_logger()

class QueueManager:
    """Manages workflow queues with support for multiple Redis instances."""

    def __init__(self, redis_configs: Dict[str, str]):
        """
        Initialize queue manager with multiple Redis configurations.
        
        Args:
            redis_configs: Dict mapping queue names to Redis URLs
                Example: {
                    "default": "redis://localhost:6379/0",
                    "high_priority": "redis://localhost:6379/1"
                }
        """
        self.redis_configs = redis_configs
        self.redis_connections: Dict[str, Optional[aioredis.Redis]] = {
            name: None for name in redis_configs
        }
        self._logger = logger.bind(component="queue_manager")
        
        # Load max_queue_length from config.json
        redis_config = get_redis_config()
        if redis_config and hasattr(redis_config, "max_queue_length"):
            self.max_queue_length = redis_config.max_queue_length
            self._logger.info(
                "queue_length_configured",
                max_queue_length=self.max_queue_length
            )
        else:
            self.max_queue_length = 1000
            self._logger.warning(
                "using_default_queue_length",
                max_queue_length=self.max_queue_length
            )

    async def connect(self, queue_name: str = "default") -> None:
        """Connect to a specific Redis instance."""
        if queue_name not in self.redis_configs:
            raise ValueError(f"Queue {queue_name} not configured")
            
        if not self.redis_connections[queue_name]:
            self.redis_connections[queue_name] = await aioredis.from_url(
                self.redis_configs[queue_name]
            )
            self._logger.info("redis_connected", queue=queue_name)

    async def disconnect(self, queue_name: str = "default") -> None:
        """Disconnect from a specific Redis instance."""
        if self.redis_connections[queue_name]:
            await self.redis_connections[queue_name].close()
            self.redis_connections[queue_name] = None
            self._logger.info("redis_disconnected", queue=queue_name)

    async def disconnect_all(self) -> None:
        """Disconnect from all Redis instances."""
        for queue_name in self.redis_connections:
            await self.disconnect(queue_name)

    async def enqueue(
        self,
        workflow_name: str,
        data: Dict[str, Any],
        queue_name: str = "default"
    ) -> bool:
        """Add a workflow to the specified queue."""
        if queue_name not in self.redis_configs:
            raise ValueError(f"Queue {queue_name} not configured")

        await self.connect(queue_name)
        
        queue_key = f"workflow:{workflow_name}:queue"
        item = {
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "queue": queue_name
        }

        await self.redis_connections[queue_name].rpush(
            queue_key,
            json.dumps(item)
        )
        # Enforce max queue length (FIFO) using LTRIM
        await self.redis_connections[queue_name].ltrim(queue_key, -self.max_queue_length, -1)
        queue_len = await self.redis_connections[queue_name].llen(queue_key)
        self._logger.info(
            "item_enqueued",
            workflow=workflow_name,
            queue=queue_name,
            queue_length=queue_len
        )
        return True

    async def dequeue(
        self,
        workflow_name: str,
        queue_name: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """Get the next workflow from the specified queue."""
        if queue_name not in self.redis_configs:
            raise ValueError(f"Queue {queue_name} not configured")

        await self.connect(queue_name)
        
        queue_key = f"workflow:{workflow_name}:queue"
        item = await self.redis_connections[queue_name].lpop(queue_key)

        if item:
            self._logger.info(
                "item_dequeued",
                workflow=workflow_name,
                queue=queue_name
            )
            return json.loads(item)
        return None

    async def get_queue_size(
        self,
        workflow_name: str,
        queue_name: str = "default"
    ) -> int:
        """Get the current size of a workflow queue."""
        if queue_name not in self.redis_configs:
            raise ValueError(f"Queue {queue_name} not configured")

        await self.connect(queue_name)
        
        queue_key = f"workflow:{workflow_name}:queue"
        return await self.redis_connections[queue_name].llen(queue_key)

    async def get_all_queue_sizes(self, workflow_name: str) -> Dict[str, int]:
        """Get sizes of a workflow's queues across all Redis instances."""
        sizes = {}
        for queue_name in self.redis_configs:
            sizes[queue_name] = await self.get_queue_size(workflow_name, queue_name)
        return sizes 