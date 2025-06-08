from typing import Dict, Any, Optional
import structlog
from datetime import datetime
import aiohttp
from pydantic import BaseModel
import asyncio

from src.core.workflow import BaseWorkflow, WorkflowResult, WorkflowConfig
from src.core.queue import QueueManager
from src.core.config import get_redis_config

logger = structlog.get_logger()

class WeatherAPIConfig(WorkflowConfig):
    """Configuration for the Weather API workflow."""
    name: str = "weather"
    description: str = "Fetches and processes weather data from Open-Meteo API"
    enabled: bool = True
    interval: int = 3600  # 1 hour
    options: Dict[str, Any] = {
        "latitude": 52.52,  # Default to Berlin
        "longitude": 13.41,
    }

class WeatherAPIWorkflow(BaseWorkflow):
    """Workflow for processing weather data from Open-Meteo API."""
    
    def __init__(self, config: WeatherAPIConfig):
        super().__init__(config)
        self._logger = logger.bind(workflow="weather")
        self.config = config
        # Initialize queue manager
        redis_config = get_redis_config()
        if redis_config and redis_config.enabled:
            self.queue_manager = QueueManager({"weather_data": "redis://redis:6379/1"})
        else:
            self.queue_manager = None

    async def fetch_weather_data(self) -> Dict[str, Any]:
        """Fetch weather data from Open-Meteo API."""
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.config.options["latitude"],
            "longitude": self.config.options["longitude"],
            "current": "temperature_2m,wind_speed_10m",
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            "timezone": "auto"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"API request failed with status {response.status}")
                return await response.json()

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process weather data from Open-Meteo API."""
        try:
            current = data.get("current", {})
            hourly = data.get("hourly", {})
            
            # Process current weather
            current_weather = {
                "timestamp": current.get("time"),
                "temperature": current.get("temperature_2m"),
                "wind_speed": current.get("wind_speed_10m"),
            }
            
            # Process hourly forecast (next 24 hours)
            hourly_forecast = []
            for i in range(24):
                if i < len(hourly.get("time", [])):
                    hourly_forecast.append({
                        "timestamp": hourly["time"][i],
                        "temperature": hourly["temperature_2m"][i],
                        "humidity": hourly["relative_humidity_2m"][i],
                        "wind_speed": hourly["wind_speed_10m"][i]
                    })
            
            processed_data = {
                "current": current_weather,
                "forecast": hourly_forecast,
                "location": {
                    "latitude": self.config.options["latitude"],
                    "longitude": self.config.options["longitude"]
                }
            }

            # Queue the processed data if Redis is enabled
            if self.queue_manager:
                await self.queue_manager.enqueue(
                    "weather",
                    processed_data,
                    "weather_data"
                )
                queue_size = await self.queue_manager.get_queue_size("weather", "weather_data")
                self._logger.info(
                    "weather_data_queued",
                    queue_size=queue_size
                )
            
            return processed_data
            
        except Exception as e:
            self._logger.error(f"Error processing weather data: {str(e)}")
            return {
                "error": str(e),
                "raw_data": data
            }

    async def execute(self, data: Dict[str, Any]) -> WorkflowResult:
        """Execute the workflow with the given data."""
        try:
            # Fetch live data from Open-Meteo API
            weather_data = await self.fetch_weather_data()
            processed_data = await self.process(weather_data)
            return WorkflowResult(success=True, data=processed_data)
        except Exception as e:
            self._logger.error("workflow_error", error=str(e))
            return WorkflowResult(success=False, error=str(e))

    async def cleanup(self):
        """Clean up resources."""
        if self.queue_manager:
            await self.queue_manager.disconnect_all()

async def run_weather_workflow():
    """Run the weather workflow with live data."""
    config = WeatherAPIConfig()
    workflow = WeatherAPIWorkflow(config)
    
    print("\nFetching weather data from Open-Meteo API...")
    print("Press Ctrl+C to stop...")
    
    try:
        while True:
            try:
                result = await workflow.execute({})
                if result.success:
                    print("\nWeather Data:")
                    print(f"Current Temperature: {result.data['current']['temperature']}°C")
                    print(f"Current Wind Speed: {result.data['current']['wind_speed']} km/h")
                    print("\n24-Hour Forecast:")
                    for hour in result.data['forecast'][:4]:  # Show next 4 hours
                        print(f"Time: {hour['timestamp']}")
                        print(f"Temperature: {hour['temperature']}°C")
                        print(f"Humidity: {hour['humidity']}%")
                        print(f"Wind Speed: {hour['wind_speed']} km/h")
                        print("---")
                else:
                    print(f"Error: {result.error}")
                
                # Wait for the configured interval
                await asyncio.sleep(config.interval)
                
            except KeyboardInterrupt:
                print("\nStopping weather workflow...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
                await asyncio.sleep(60)  # Wait a minute before retrying
    finally:
        await workflow.cleanup()

if __name__ == "__main__":
    asyncio.run(run_weather_workflow()) 