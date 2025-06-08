#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored messages
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Docker installation and daemon
check_docker() {
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        print_message "Visit https://docs.docker.com/get-docker/ for installation instructions."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker daemon is not running."
        print_message "Please start Docker Desktop or the Docker daemon."
        print_message "On macOS: Open Docker Desktop application"
        print_message "On Linux: Run 'sudo systemctl start docker'"
        exit 1
    fi
    
    print_message "Docker is installed and running."
}

# Function to check Docker Compose installation
check_docker_compose() {
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        print_message "Visit https://docs.docker.com/compose/install/ for installation instructions."
        exit 1
    fi
    print_message "Docker Compose is installed."
}

# Function to setup environment variables
setup_env() {
    local env_file=".env"
    
    if [ -f "$env_file" ]; then
        print_warning "File $env_file already exists. Do you want to overwrite it? (y/n)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_message "Environment setup cancelled."
            return
        fi
    fi
    
    # Prompt for environment variables
    print_message "Setting up environment variables..."
    
    # Redis Configuration
    read -p "Enter Redis Port (default: 6380): " redis_port
    redis_port=${redis_port:-"6380"}
    
    # API Configuration
    read -p "Enter API Host (default: 0.0.0.0): " api_host
    api_host=${api_host:-"0.0.0.0"}
    
    read -p "Enter API Port (default: 8000): " api_port
    api_port=${api_port:-"8000"}
    
    # Logging
    read -p "Enter Log Level (default: info): " log_level
    log_level=${log_level:-"info"}
    
    # Create .env file
    cat > "$env_file" << EOF
# Redis Configuration
REDIS_PORT=$redis_port

# API Configuration
API_HOST=$api_host
API_PORT=$api_port

# Logging
LOG_LEVEL=$log_level
EOF
    
    print_message "Created $env_file with your configuration."
}

# Function to initialize Redis queues
init_redis_queues() {
    print_message "Initializing Redis queues..."
    
    # Check if config.json exists
    if [ ! -f "config.json" ]; then
        print_error "config.json not found. Please create it first."
        exit 1
    fi
    
    # Extract queue names from config.json
    queues=$(jq -r '.workflows | to_entries[] | select(.value.use_redis==true) | .value.redis_queue' config.json)
    
    # Start Redis container if not running
    if ! docker-compose ps redis | grep -q "Up"; then
        print_message "Starting Redis container..."
        docker-compose up -d redis
        sleep 5  # Wait for Redis to start
    fi
    
    # Check Redis connection
    if ! docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        print_error "Redis is not responding. Please check Redis logs."
        docker-compose logs redis
        exit 1
    fi
    
    print_message "Redis is responding. Initializing queues..."
    
    # Initialize each queue
    for queue in $queues; do
        if [ ! -z "$queue" ]; then
            print_message "Initializing queue: $queue"
            # Create the queue key
            queue_key="workflow:$queue:queue"
            # Clear any existing data
            docker-compose exec -T redis redis-cli DEL "$queue_key"
            # Verify queue was created
            if docker-compose exec -T redis redis-cli EXISTS "$queue_key" | grep -q "0"; then
                print_message "Queue $queue initialized successfully"
            else
                print_error "Failed to initialize queue $queue"
            fi
        fi
    done
    
    # List all queues to verify
    print_message "Verifying all queues:"
    docker-compose exec -T redis redis-cli KEYS "workflow:*"
    
    print_message "Redis queues initialized successfully."
}

# Function to start services
start_services() {
    print_message "Starting services..."
    
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Please run setup first."
        exit 1
    fi
    
    # Build and start containers
    docker-compose build
    docker-compose up -d
    
    # Initialize Redis queues
    init_redis_queues
    
    print_message "Services started successfully."
}

# Function to print setup instructions
print_instructions() {
    print_message "\nSetup complete! Here's what you can do next:"
    echo -e "\n1. Test the example workflows:"
    echo "   - News RSS Feed: Monitor financial news"
    echo "   - Weather API: Get weather updates"
    echo "   - Binance WebSocket: Track crypto prices"
    
    echo -e "\n2. Create your own workflow:"
    echo "   - Copy an example from src/workflows/examples/"
    echo "   - Add your workflow to config.json"
    echo "   - Implement your workflow logic"
    
    echo -e "\n3. View logs:"
    echo "   docker-compose logs -f"
    
    echo -e "\n4. Run tests:"
    echo "   docker-compose exec api pytest tests/ -s"
    
    echo -e "\n5. Monitor Redis queues:"
    echo "   docker-compose exec redis redis-cli"
    echo "   KEYS *  # List all queues"
    echo "   LLEN workflow:<queue_name>:queue  # Check queue size"
}

# Main script
print_message "Starting setup..."

# Check dependencies
check_docker
check_docker_compose

# Setup environment
setup_env

# Start services
start_services

# Print instructions
print_instructions 