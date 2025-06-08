import pytest
from datetime import datetime
import asyncio

from src.workflows.examples.binance_websocket import BinanceWebSocketWorkflow, BinanceWebSocketConfig
from src.workflows.examples.weather_api import WeatherAPIWorkflow, WeatherAPIConfig
from src.workflows.examples.news_rss import NewsRSSWorkflow, NewsRSSConfig

def print_result(workflow_name: str, result):
    """Print workflow result in a readable format."""
    print(f"\n==================== {workflow_name} Result ====================")
    print(f"Success: {result.success}")
    print("Data:")
    print(result.data)
    print("=" * 60)

@pytest.mark.asyncio
async def test_binance_websocket_workflow():
    """Test Binance websocket workflow with live data."""
    config = BinanceWebSocketConfig()
    workflow = BinanceWebSocketWorkflow(config)
    
    try:
        # Execute workflow with live data
        result = await workflow.execute({})
        
        print_result("Binance WebSocket", result)
        
        assert result.success
        assert "type" in result.data
        assert "symbol" in result.data
        assert "price" in result.data
        
        # Check fields based on message type
        if result.data["type"] == "trade":
            assert "quantity" in result.data
            assert "is_buyer_maker" in result.data
        elif result.data["type"] == "mark_price":
            assert "index_price" in result.data
            assert "funding_rate" in result.data
            assert "next_funding_time" in result.data
        else:
            pytest.fail(f"Unexpected message type: {result.data['type']}")
    finally:
        # Ensure proper cleanup
        await workflow.cleanup()
        # Give time for cleanup to complete
        await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_weather_api_workflow():
    """Test weather API workflow with live data."""
    config = WeatherAPIConfig()
    workflow = WeatherAPIWorkflow(config)
    
    # Execute workflow with live data
    result = await workflow.execute({})
    
    print_result("Weather API", result)
    
    assert result.success
    assert "current" in result.data
    assert "forecast" in result.data
    assert "temperature" in result.data["current"]
    assert "wind_speed" in result.data["current"]
    assert isinstance(result.data["current"]["temperature"], (int, float))
    assert isinstance(result.data["current"]["wind_speed"], (int, float))
    assert len(result.data["forecast"]) > 0

@pytest.mark.asyncio
async def test_news_rss_workflow():
    """Test news RSS workflow with live data."""
    config = NewsRSSConfig()
    workflow = NewsRSSWorkflow(config)
    
    # Execute workflow with live data
    result = await workflow.execute({})
    
    print_result("News RSS", result)
    
    assert result.success
    assert "articles" in result.data
    assert len(result.data["articles"]) > 0
    assert all(isinstance(article, dict) for article in result.data["articles"])
    assert all("title" in article for article in result.data["articles"])
    assert all("description" in article for article in result.data["articles"]) 