# Data Processing Workflow Template

A lightweight template for deploying data processing workflows on any cloud VM.

## Quick Start

### Local Development
```bash
# Run setup script (configures environment and starts services)
chmod +x setup.sh
./setup.sh

# Run all tests
docker-compose exec api pytest tests/

# Run specific test file
docker-compose exec api pytest tests/test_example_workflows.py

# Run with print output
docker-compose exec api pytest tests/ -s

# View logs
docker-compose logs -f
```

### VM Deployment
1. SSH into your VM and navigate to your desired directory:
```bash
ssh username@your-vm-ip
cd /opt  # or your preferred directory
```

2. Clone the repository onto the VM:
```bash
git clone https://github.com/willschneider15/data-pipeline-python-vm.git
cd data-pipeline-python-vm
```
Note: You will need to get perms on the VM to do this

3. Install docker configure the VM
```bash
# Install Docker and Docker Compose
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# Add your user to docker group
sudo usermod -aG docker $USER
```

4. Run setup script:
```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Check for Docker/Docker Compose
- Configure environment variables
- Build and start the Docker containers
- Set up example workflows

## CI/CD Pipeline

The GitHub Actions workflow (`ci.yml`) handles:
- Running tests
- Deploying to VM via SSH
- Restarting services

### Setting up GitHub Secrets
1. Go to your GitHub repository
2. Click on "Settings" > "Secrets and variables" > "Actions"
3. Add the following secrets:
   - `HOST`: Your VM's IP address or hostname
   - `USERNAME`: SSH username for your VM
   - `SSH_PRIVATE_KEY`: Your SSH private key (the entire key content, including BEGIN and END lines)

To generate a new SSH key pair:
```bash
ssh-keygen -t ed25519 -C "your-email@example.com"
# Add the public key to your VM's ~/.ssh/authorized_keys
# Add the private key content to GitHub Secrets
```

## Creating Workflows

### Example Workflows
The template includes three example workflows in `src/workflows/examples/`:

1. **News RSS Feed** (`news_rss.py`):
   - Monitors financial news from RSS feeds
   - Extracts headlines, summaries, and publication dates
   - Can be configured to track specific topics or sources
   - Uses Redis for caching and rate limiting

2. **Weather API** (`weather_api.py`):
   - Fetches weather data from OpenWeatherMap API
   - Tracks temperature, humidity, and conditions
   - Supports multiple locations
   - Implements error handling and retries

3. **Binance WebSocket** (`binance_websocket.py`):
   - Real-time cryptocurrency price monitoring
   - Tracks multiple trading pairs
   - Calculates price statistics
   - Handles WebSocket reconnection

### Building Your Own Workflow

1. **Configuration**
   Add your workflow to `config.json`:
   ```json
   {
     "workflows": {
       "my_workflow": {
         "enabled": true,
         "use_redis": true,
         "redis_queue": "my_queue",
         "update_interval": 300,  // in seconds
         "config": {
           "api_key": "${API_KEY}",
           "endpoint": "https://api.example.com",
           "options": {
             "timeout": 30,
             "retries": 3
           }
         }
       }
     }
   }
   ```

2. **Implementation**
   Create your workflow class in `src/workflows/`:
   ```python
   from core.workflow import BaseWorkflow, WorkflowResult
   from core.config import get_workflow_config

   class MyWorkflow(BaseWorkflow):
       def __init__(self):
           super().__init__()
           self.config = get_workflow_config("my_workflow")
           
       async def execute(self):
           try:
               # 1. Fetch data
               data = await self.fetch_data()
               
               # 2. Process data
               processed = await self.process_data(data)
               
               # 3. Store results
               await self.store_results(processed)
               
               return WorkflowResult(
                   success=True,
                   data=processed,
                   metadata={
                       "timestamp": datetime.now().isoformat(),
                       "source": "my_workflow"
                   }
               )
           except Exception as e:
               return WorkflowResult(
                   success=False,
                   error=str(e)
               )
   ```

3. **Best Practices**
   - Use async/await for I/O operations
   - Implement proper error handling
   - Use Redis for caching and rate limiting
   - Add logging for debugging
   - Include unit tests
   - Document your workflow's purpose and configuration

4. **Testing**
   Create tests in `tests/test_workflows.py`:
   ```python
   import pytest
   from unittest.mock import patch, MagicMock
   from workflows.my_workflow import MyWorkflow

   @pytest.mark.asyncio
   async def test_my_workflow():
       workflow = MyWorkflow()
       result = await workflow.execute()
       
       assert result.success
       assert "data" in result.data
       assert "metadata" in result.data
   ```

### Workflow Lifecycle
1. **Initialization**: Workflow is created and configured
2. **Execution**: Main processing logic runs
3. **Error Handling**: Any errors are caught and reported
4. **Result Processing**: Results are stored and/or returned
5. **Cleanup**: Resources are released

### Redis Queue Management
1. **Configure in `config.json`:**
```json
{
    "redis": {
        "enabled": true,
        "max_queue_length": 20,
        "max_memory": "512mb"
    },
    "workflows": {
        "your_workflow": {
            "use_redis": true,
            "redis_queue": "your_queue_name"
        }
    }
}
```

2. **Inspect Queues:**
```bash
# List all queues
docker-compose exec redis redis-cli -n 1 KEYS "workflow:*"

# Check queue size
docker-compose exec redis redis-cli -n 1 LLEN workflow:your_workflow:queue

# View queue contents
docker-compose exec redis redis-cli -n 1 LRANGE workflow:your_workflow:queue 0 -1

# Clear queue
docker-compose exec redis redis-cli -n 1 DEL workflow:your_workflow:queue
```

3. **Monitor in Real-time:**
```bash
docker-compose exec redis redis-cli -n 1 MONITOR
```

### Common Patterns
- **Data Fetching**: Use aiohttp for HTTP requests
- **Caching**: Use Redis for temporary storage
- **Rate Limiting**: Implement delays between requests
- **Error Recovery**: Implement retry logic
- **Monitoring**: Add metrics for workflow performance

### Project Structure
```
backend/
├── src/
│   ├── api/          # FastAPI application
│   ├── core/         # Core functionality
│   ├── workflows/    # Workflow implementations
│   │   └── examples/ # Example workflows
│   └── utils/        # Utility functions
├── tests/            # Test files
├── docker-compose.yml
└── setup.sh
```



## License

MIT License