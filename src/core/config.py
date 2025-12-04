"""
Configuration management for Network Stats Collector

Handles loading and validation of application and job configurations
from YAML files with Pydantic validation.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class DestinationConfig(BaseModel):
    """Configuration for a single destination to monitor"""
    host: str = Field(..., description="Hostname or IP address")
    display_name: str = Field(..., description="Human-readable name for display")

class JobConfig(BaseModel):
    """Configuration for a network monitoring job"""
    name: str = Field(..., description="Unique job identifier")
    interval: int = Field(..., ge=60, description="Collection interval in seconds (minimum 60)")
    enabled: bool = Field(True, description="Whether this job is active")
    metrics: List[str] = Field(
        default=["ping"],
        description="List of metrics to collect"
    )
    destinations: List[DestinationConfig] = Field(..., min_items=1, description="List of destinations to monitor")

    @validator('metrics')
    def validate_metrics(cls, v):
        allowed_metrics = {"ping", "traceroute", "dns", "bandwidth", "jitter", "packet_loss"}
        for metric in v:
            if metric not in allowed_metrics:
                raise ValueError(f"Invalid metric '{metric}'. Allowed: {allowed_metrics}")
        return v

class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field("sqlite:///network_stats.db", description="Database connection URL")
    pool_size: int = Field(5, ge=1, description="Database connection pool size")
    echo: bool = Field(False, description="Enable SQL query logging")

class WebConfig(BaseModel):
    """Web server configuration"""
    host: str = Field("127.0.0.1", description="Web server host")
    port: int = Field(8080, ge=1, le=65535, description="Web server port")
    debug: bool = Field(False, description="Enable debug mode")
    cors_origins: List[str] = Field(default=["http://127.0.0.1:8080"], description="CORS allowed origins")

class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field("INFO", description="Log level")
    file: Optional[str] = Field(None, description="Log file path")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )

class AppConfig(BaseModel):
    """Main application configuration"""
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

class Config:
    """Configuration manager for the application"""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path or Path("config/app.yaml")
        self.app_config: Optional[AppConfig] = None
        self.jobs: Dict[str, JobConfig] = {}
        self._load_config()

    @property
    def database_url(self) -> str:
        """Get database connection URL"""
        return self.app_config.database.url if self.app_config else "sqlite:///network_stats.db"

    def _load_config(self):
        """Load configuration from file"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Configuration file {self.config_path} not found, using defaults")
                self.app_config = AppConfig()
                return

            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                logger.warning("Empty configuration file, using defaults")
                self.app_config = AppConfig()
                return

            # Load app configuration
            app_data = config_data.get('app', {})
            self.app_config = AppConfig(**app_data)

            # Load job configurations
            jobs_data = config_data.get('jobs', [])
            self.jobs = {}
            for job_data in jobs_data:
                job_config = JobConfig(**job_data)
                self.jobs[job_config.name] = job_config

            logger.info(f"Loaded {len(self.jobs)} job configurations")

        except Exception as e:
            logger.error(f"Error loading configuration from {self.config_path}: {e}")
            logger.info("Using default configuration")
            self.app_config = AppConfig()
            self.jobs = {}

    def get_job(self, name: str) -> Optional[JobConfig]:
        """Get job configuration by name"""
        return self.jobs.get(name)

    def get_all_jobs(self) -> Dict[str, JobConfig]:
        """Get all job configurations"""
        return self.jobs.copy()

    def get_enabled_jobs(self) -> Dict[str, JobConfig]:
        """Get only enabled job configurations"""
        return {name: job for name, job in self.jobs.items() if job.enabled}

    def reload_config(self):
        """Reload configuration from file"""
        logger.info("Reloading configuration...")
        self._load_config()
        logger.info("Configuration reloaded successfully")

    def add_job(self, job_config: JobConfig):
        """
        Add a new job configuration

        Args:
            job_config: Job configuration to add
        """
        if job_config.name in self.jobs:
            raise ValueError(f"Job '{job_config.name}' already exists")

        self.jobs[job_config.name] = job_config
        logger.info(f"Added job '{job_config.name}'")

    def update_job(self, name: str, job_config: JobConfig):
        """
        Update an existing job configuration

        Args:
            name: Name of the job to update
            job_config: New job configuration
        """
        if name not in self.jobs:
            raise ValueError(f"Job '{name}' not found")

        # If name is changing, check for conflicts
        if job_config.name != name:
            if job_config.name in self.jobs:
                raise ValueError(f"Job '{job_config.name}' already exists")
            # Remove old job and add new one
            del self.jobs[name]

        self.jobs[job_config.name] = job_config
        logger.info(f"Updated job '{job_config.name}'")

    def remove_job(self, name: str):
        """
        Remove a job configuration

        Args:
            name: Name of the job to remove
        """
        if name not in self.jobs:
            raise ValueError(f"Job '{name}' not found")

        del self.jobs[name]
        logger.info(f"Removed job '{name}'")

    def save_config(self):
        """Save current configuration to file"""
        try:
            # Prepare configuration data
            config_data = {
                'app': self.app_config.dict() if self.app_config else {},
                'jobs': [job.dict() for job in self.jobs.values()]
            }

            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)

            logger.info(f"Configuration saved to {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to save configuration to {self.config_path}: {e}")
            raise