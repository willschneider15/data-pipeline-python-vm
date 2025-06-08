from typing import Dict, Any, Optional
import os
import json
from pydantic import BaseModel, Field

class WorkflowConfig(BaseModel):
    enabled: bool
    use_redis: bool
    redis_queue: Optional[str] = None
    config: Dict[str, Any]

class RedisConfig(BaseModel):
    enabled: bool
    persistence: bool
    max_memory: str
    max_memory_policy: str
    max_queue_length: int

class APIConfig(BaseModel):
    host: str
    port: int
    workers: int
    log_level: str
    cors_origins: list[str]

class LoggingConfig(BaseModel):
    level: str
    format: str
    output: str
    retention: int

class MonitoringConfig(BaseModel):
    enabled: bool
    metrics: list[str]
    alerts: Dict[str, int]

class DeploymentConfig(BaseModel):
    strategy: str
    health_check: Dict[str, Any]
    rollback: Dict[str, Any]

class Config(BaseModel):
    workflows: Dict[str, WorkflowConfig]
    redis: RedisConfig
    api: APIConfig
    logging: LoggingConfig
    monitoring: MonitoringConfig
    deployment: DeploymentConfig

def load_config(config_path: str = "config.json") -> Config:
    """Load configuration from JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    # Replace environment variables
    def replace_env_vars(data: Any) -> Any:
        if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            env_var = data[2:-1]
            return os.getenv(env_var)
        elif isinstance(data, dict):
            return {k: replace_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [replace_env_vars(item) for item in data]
        return data
    
    config_data = replace_env_vars(config_data)
    
    return Config(**config_data)

def get_workflow_config(workflow_name: str) -> Optional[WorkflowConfig]:
    """Get configuration for a specific workflow."""
    config = load_config()
    return config.workflows.get(workflow_name)

def is_redis_enabled() -> bool:
    """Check if Redis is enabled in the configuration."""
    config = load_config()
    return config.redis.enabled

def get_redis_config() -> Optional[RedisConfig]:
    """Get Redis configuration if enabled."""
    config = load_config()
    return config.redis if config.redis.enabled else None 