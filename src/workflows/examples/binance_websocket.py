from typing import Dict, Any, Optional
import structlog
import json
import asyncio
import websockets
from datetime import datetime
from pydantic import BaseModel

from src.core.workflow import BaseWorkflow, WorkflowResult, WorkflowConfig
from src.core.queue import QueueManager
from src.core.config import get_workflow_config, is_redis_enabled

logger = structlog.get_logger()

class BinanceWebSocketConfig(WorkflowConfig):
    """Configuration for the Binance workflow."""
    name: str = "binance"
    description: str = "Fetches and processes cryptocurrency data from Binance Futures WebSocket"
    enabled: bool = True
    interval: int = 0  # WebSocket is real-time
    options: Dict[str, Any] = {
        "symbols": ["btcusdt", "ethusdt"],  # Default symbols to track
        "streams": ["aggTrade", "markPrice"],  # Default streams to subscribe to
        "rate_limit": 10,  # Messages per second
        "rate_limit_window": 1.0,  # Window size in seconds
    }

class BinanceWebSocketWorkflow(BaseWorkflow):
    """Workflow for processing cryptocurrency data from Binance Futures WebSocket."""
    
    def __init__(self, config: BinanceWebSocketConfig):
        super().__init__(config)
        self._logger = logger.bind(workflow="binance")
        
        # Load workflow config from config.json
        workflow_config = get_workflow_config("binance")
        if workflow_config:
            self.config = workflow_config
            self.options = workflow_config.config
        else:
            self.config = config
            self.options = config.options
            
        self.last_pong = datetime.utcnow()
        self.message_count = 0
        self.last_reset = datetime.utcnow()
        self.rate_limit = self.options.get("rate_limit", 10)
        self.rate_limit_window = self.options.get("rate_limit_window", 1.0)
        self._websocket = None
        self._last_data = None
        self._is_running = False
        
        # Initialize queue manager if Redis is enabled
        if is_redis_enabled() and self.config.use_redis:
            self._queue_manager = QueueManager({
                "default": "redis://redis:6379/0",
                self.config.redis_queue: f"redis://redis:6379/1"
            })
        else:
            self._queue_manager = None

    async def _connect_websocket(self):
        """Connect to Binance Futures WebSocket."""
        # Build combined stream URL
        streams = []
        for symbol in self.options["symbols"]:
            for stream_type in self.options["streams"]:
                streams.append(f"{symbol}@{stream_type}")
        
        stream_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
        
        try:
            self._websocket = await websockets.connect(stream_url)
            self._logger.info("Connected to Binance Futures WebSocket")
            return True
        except Exception as e:
            self._logger.error(f"Failed to connect to WebSocket: {str(e)}")
            return False

    async def _fetch_data(self) -> Dict[str, Any]:
        """Fetch data from WebSocket."""
        if not self._websocket:
            if not await self._connect_websocket():
                return {"type": "error", "error": "Failed to connect to WebSocket"}

        try:
            # Set a timeout for receiving data
            message = await asyncio.wait_for(self._websocket.recv(), timeout=5.0)
            data = json.loads(message)
            
            # Handle ping messages
            if isinstance(data, str) and data == "ping":
                await self._websocket.pong()
                self.last_pong = datetime.utcnow()
                return await self._fetch_data()  # Try again after ping
            
            return data
        except asyncio.TimeoutError:
            self._logger.warning("Timeout waiting for WebSocket data")
            return {"type": "error", "error": "Timeout waiting for data"}
        except websockets.exceptions.ConnectionClosed:
            self._logger.warning("WebSocket connection closed, reconnecting...")
            self._websocket = None
            return await self._fetch_data()  # Try again with new connection
        except Exception as e:
            self._logger.error(f"Error fetching data: {str(e)}")
            return {"type": "error", "error": str(e)}

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process cryptocurrency data from Binance Futures WebSocket."""
        try:
            # Handle combined stream format
            if "stream" in data:
                stream_name = data["stream"]
                payload = data["data"]
            else:
                stream_name = "unknown"
                payload = data

            # Process based on stream type
            processed_data = None
            if "@aggTrade" in stream_name:
                processed_data = {
                    "type": "trade",
                    "symbol": payload.get("s"),
                    "price": float(payload.get("p", 0)),
                    "quantity": float(payload.get("q", 0)),
                    "timestamp": payload.get("T"),
                    "is_buyer_maker": payload.get("m", False)
                }
            elif "@markPrice" in stream_name:
                processed_data = {
                    "type": "mark_price",
                    "symbol": payload.get("s"),
                    "price": float(payload.get("p", 0)),
                    "index_price": float(payload.get("i", 0)),
                    "funding_rate": float(payload.get("r", 0)),
                    "next_funding_time": payload.get("T"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                processed_data = {
                    "type": "unknown",
                    "raw_data": payload
                }

            # Queue the processed data if Redis is enabled
            if self._queue_manager and self.config.use_redis:
                await self._queue_manager.enqueue(
                    "binance",  # Use hardcoded workflow name
                    processed_data,
                    self.config.redis_queue
                )

            return processed_data
        except Exception as e:
            self._logger.error(f"Error processing Binance data: {str(e)}")
            return {
                "type": "error",
                "error": str(e),
                "raw_data": data
            }

    async def execute(self, data: Dict[str, Any]) -> WorkflowResult:
        """Execute the workflow with the given data."""
        try:
            # Rate limiting check
            current_time = datetime.utcnow()
            time_diff = (current_time - self.last_reset).total_seconds()
            
            if time_diff >= self.rate_limit_window:
                self.message_count = 0
                self.last_reset = current_time
            
            self.message_count += 1
            if self.message_count > self.rate_limit:
                wait_time = self.rate_limit_window - time_diff
                if wait_time > 0:
                    self._logger.warning(f"Rate limit exceeded, waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                self.message_count = 0
                self.last_reset = datetime.utcnow()

            # Fetch live data
            websocket_data = await self._fetch_data()
            if websocket_data.get("type") == "error":
                return WorkflowResult(success=False, error=websocket_data["error"])

            # Process the data
            processed_data = await self.process(websocket_data)
            self._last_data = processed_data
            return WorkflowResult(success=True, data=processed_data)
        except Exception as e:
            self._logger.error("workflow_error", error=str(e))
            return WorkflowResult(success=False, error=str(e))

    async def cleanup(self):
        """Clean up WebSocket connection."""
        self._is_running = False
        if self._websocket:
            try:
                # Close the WebSocket connection
                await self._websocket.close()
                # Wait for the connection to be fully closed
                await asyncio.sleep(0.1)
            except Exception as e:
                self._logger.error(f"Error closing WebSocket: {str(e)}")
            finally:
                self._websocket = None
                # Cancel any pending tasks
                for task in asyncio.all_tasks():
                    if task != asyncio.current_task():
                        task.cancel()
        
        # Disconnect from Redis if enabled
        if self._queue_manager:
            await self._queue_manager.disconnect_all()

async def run_binance_workflow():
    """Run the Binance workflow with real-time data."""
    config = BinanceWebSocketConfig()
    workflow = BinanceWebSocketWorkflow(config)
    workflow._is_running = True
    
    print("\nConnecting to Binance Futures WebSocket...")
    print("Press Ctrl+C to stop...")
    
    try:
        while workflow._is_running:
            result = await workflow.execute({})
            if result.success:
                print("\nBinance Futures Data:")
                print(json.dumps(result.data, indent=2))
                
                # Print queue size if Redis is enabled
                if workflow._queue_manager and workflow.config.use_redis:
                    queue_size = await workflow._queue_manager.get_queue_size(
                        "binance",  # Use hardcoded workflow name
                        workflow.config.redis_queue
                    )
                    print(f"\nQueue size: {queue_size}")
            else:
                print(f"Error: {result.error}")
            
            # Small delay to prevent overwhelming the output
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping Binance workflow...")
    finally:
        await workflow.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(run_binance_workflow())
    except KeyboardInterrupt:
        print("\nWorkflow stopped by user.") 