# Example Workflows

This directory contains example implementations of workflows that demonstrate different data processing patterns.

## Available Examples

### 1. News RSS Feed (`news_rss.py`)
- Monitors financial news from multiple RSS feeds
- Filters content based on relevant keywords
- Processes and cleans HTML content
- Maintains a history of processed entries
- Useful for market sentiment analysis

### 2. Weather API (`weather_api.py`)
- Fetches weather data from OpenWeatherMap API
- Processes temperature, humidity, pressure, and wind data
- Demonstrates API integration and data transformation
- Useful for weather-dependent business logic

### 3. Binance WebSocket (`binance_websocket.py`)
- Connects to Binance WebSocket API for real-time price data
- Calculates price statistics (average, min, max)
- Maintains a rolling price history
- Demonstrates real-time data processing

## Running Workflows in Isolation

Each workflow can be run independently for testing or development purposes. Here are the commands for each workflow:

### Binance Futures WebSocket
```bash
# Run the Binance workflow (real-time cryptocurrency data)
docker-compose exec api python src/workflows/examples/binance_websocket.py

# Stop with Ctrl+C
```

The Binance workflow provides:
- Real-time trade data
- Mark prices
- Funding rates
- Rate-limited processing (10 messages/second)
- Automatic reconnection

### Weather API
```bash
# Run the weather workflow (current weather and forecast)
docker-compose exec api python src/workflows/examples/weather_api.py
```

The Weather workflow provides:
- Current temperature and wind speed
- 24-hour forecast
- Humidity data
- Location-based weather

### News RSS
```bash
# Run the news workflow (financial news feeds)
docker-compose exec api python src/workflows/examples/news_rss.py
```

The News workflow provides:
- Real-time news updates
- Article processing
- Keyword extraction
- Source tracking

## Usage

Each example workflow can be used as a template for your own implementations. They demonstrate:
- Proper error handling
- Logging best practices
- Data validation
- Async/await patterns
- External API integration

## Creating Your Own Workflow

1. Copy one of the example files
2. Modify the class name and docstring
3. Implement your data processing logic in the `execute()` method
4. Add any necessary helper methods
5. Update the imports if needed

## Testing

Each workflow includes corresponding tests in `tests/test_workflows.py`. Use these as examples for testing your own workflows. 