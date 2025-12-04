"""
Configuration management for Network Stats Collector

Handles loading and validation of application, destination, and job configurations
from YAML files with Pydantic validation.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class DestinationConfig(BaseModel):
    """Configuration for a global destination"""
    name: str = Field(..., description="Unique destination name")
    host: str = Field(..., description="Hostname or IP address")
    display_name: str = Field(..., description="Human-readable name for display")
    description: Optional[str] = Field(None, description="Optional description")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    status: str = Field("active", description="Destination status")

    @validator('status')
    def validate_status(cls, v):
        allowed_statuses = {"active", "inactive", "error"}
        if v not in allowed_statuses:
            raise ValueError(f"Invalid status '{v}'. Allowed: {allowed_statuses}")
        return v

    @validator('host')
    def validate_host(cls, v):
        """Basic host validation - can be enhanced"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Host cannot be empty")
        return v.strip()

class JobConfig(BaseModel):
    """Configuration for a network monitoring job with destination references"""
    name: str = Field(..., description="Unique job identifier")
    description: Optional[str] = Field(None, description="Job description")
    enabled: bool = Field(True, description="Whether this job is active")
    interval: int = Field(..., ge=60, description="Collection interval in seconds (minimum 60)")
    metrics: List[str] = Field(
        default=["ping"],
        description="List of metrics to collect"
    )
    destinations: List[str] = Field(..., min_items=1, description="List of destination names")

    # Time window scheduling
    start_time: Optional[datetime] = Field(None, description="Job execution start time")
    end_time: Optional[datetime] = Field(None, description="Job execution end time (optional)")

    # Metadata
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")

    @validator('metrics')
    def validate_metrics(cls, v):
        allowed_metrics = {"ping", "traceroute", "dns", "bandwidth", "jitter", "packet_loss"}
        for metric in v:
            if metric not in allowed_metrics:
                raise ValueError(f"Invalid metric '{metric}'. Allowed: {allowed_metrics}")
        return v

    @validator('end_time')
    def validate_time_window(cls, v, values):
        if v and 'start_time' in values and values['start_time']:
            if v <= values['start_time']:
                raise ValueError("End time must be after start time")
        return v

    @validator('destinations')
    def validate_destinations(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one destination must be specified")
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
    cors_origins: List[str] = Field(
        default=["http://127.0.0.1:8080"],
        description="CORS allowed origins"
    )

class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field("INFO", description="Log level")
    file: Optional[str] = Field(None, description="Log file path")
    format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )

    @validator('level')
    def validate_level(cls, v):
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed_levels:
            raise ValueError(f"Invalid log level '{v}'. Allowed: {allowed_levels}")
        return v.upper()

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
        self.destinations: Dict[str, DestinationConfig] = {}
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

            # Load destination configurations
            destinations_data = config_data.get('destinations', [])
            self.destinations = {}
            for dest_data in destinations_data:
                dest_config = DestinationConfig(**dest_data)
                self.destinations[dest_config.name] = dest_config

            # Load job configurations
            jobs_data = config_data.get('jobs', [])
            self.jobs = {}
            for job_data in jobs_data:
                job_config = JobConfig(**job_data)
                self.jobs[job_config.name] = job_config

            # Validate job destinations
            self._validate_job_destinations()

            logger.info(f"Loaded {len(self.destinations)} destinations and {len(self.jobs)} job configurations")

        except Exception as e:
            logger.error(f"Error loading configuration from {self.config_path}: {e}")
            logger.info("Using default configuration")
            self.app_config = AppConfig()
            self.destinations = {}
            self.jobs = {}

    def _validate_job_destinations(self):
        """Validate that all job destinations exist in the destinations list"""
        for job_name, job_config in self.jobs.items():
            for dest_name in job_config.destinations:
                if dest_name not in self.destinations:
                    logger.warning(
                        f"Job '{job_name}' references destination '{dest_name}' which is not defined. "
                        f"Job will be disabled."
                    )
                    job_config.enabled = False

    def get_destination(self, name: str) -> Optional[DestinationConfig]:
        """Get destination configuration by name"""
        return self.destinations.get(name)

    def get_all_destinations(self) -> Dict[str, DestinationConfig]:
        """Get all destination configurations"""
        return self.destinations.copy()

    def get_active_destinations(self) -> Dict[str, DestinationConfig]:
        """Get only active destinations"""
        return {name: dest for name, dest in self.destinations.items() if dest.status == "active"}

    def add_destination(self, destination: DestinationConfig) -> bool:
        """
        Add a new destination to configuration

        Args:
            destination: Destination configuration

        Returns:
            True if added successfully, False if name already exists
        """
        if destination.name in self.destinations:
            logger.warning(f"Destination '{destination.name}' already exists")
            return False

        self.destinations[destination.name] = destination
        logger.info(f"Added destination '{destination.name}'")
        return True

    def update_destination(self, name: str, destination: DestinationConfig) -> bool:
        """
        Update an existing destination

        Args:
            name: Current destination name
            destination: Updated destination configuration

        Returns:
            True if updated successfully, False if not found
        """
        if name not in self.destinations:
            logger.warning(f"Destination '{name}' not found")
            return False

        # Remove old entry and add new one (in case name changed)
        del self.destinations[name]
        self.destinations[destination.name] = destination
        logger.info(f"Updated destination '{name}' -> '{destination.name}'")
        return True

    def remove_destination(self, name: str) -> bool:
        """
        Remove a destination from configuration

        Args:
            name: Destination name to remove

        Returns:
            True if removed successfully, False if not found
        """
        if name not in self.destinations:
            logger.warning(f"Destination '{name}' not found")
            return False

        # Check if destination is used by any jobs
        used_by_jobs = []
        for job_name, job_config in self.jobs.items():
            if name in job_config.destinations:
                used_by_jobs.append(job_name)

        if used_by_jobs:
            logger.warning(
                f"Cannot remove destination '{name}' - it is used by jobs: {', '.join(used_by_jobs)}"
            )
            return False

        del self.destinations[name]
        logger.info(f"Removed destination '{name}'")
        return True

    def get_job(self, name: str) -> Optional[JobConfig]:
        """Get job configuration by name"""
        return self.jobs.get(name)

    def get_all_jobs(self) -> Dict[str, JobConfig]:
        """Get all job configurations"""
        return self.jobs.copy()

    def get_enabled_jobs(self) -> Dict[str, JobConfig]:
        """Get only enabled job configurations"""
        return {name: job for name, job in self.jobs.items() if job.enabled}

    def add_job(self, job: JobConfig) -> bool:
        """
        Add a new job to configuration

        Args:
            job: Job configuration

        Returns:
            True if added successfully, False if name already exists
        """
        if job.name in self.jobs:
            logger.warning(f"Job '{job.name}' already exists")
            return False

        # Validate job destinations
        for dest_name in job.destinations:
            if dest_name not in self.destinations:
                logger.warning(
                    f"Cannot add job '{job.name}' - destination '{dest_name}' not found"
                )
                return False

        self.jobs[job.name] = job
        logger.info(f"Added job '{job.name}'")
        return True

    def update_job(self, name: str, job: JobConfig) -> bool:
        """
        Update an existing job

        Args:
            name: Current job name
            job: Updated job configuration

        Returns:
            True if updated successfully, False if not found
        """
        if name not in self.jobs:
            logger.warning(f"Job '{name}' not found")
            return False

        # Validate job destinations
        for dest_name in job.destinations:
            if dest_name not in self.destinations:
                logger.warning(
                    f"Cannot update job '{name}' - destination '{dest_name}' not found"
                )
                return False

        # Remove old entry and add new one (in case name changed)
        del self.jobs[name]
        self.jobs[job.name] = job
        logger.info(f"Updated job '{name}' -> '{job.name}'")
        return True

    def remove_job(self, name: str) -> bool:
        """
        Remove a job from configuration

        Args:
            name: Job name to remove

        Returns:
            True if removed successfully, False if not found
        """
        if name not in self.jobs:
            logger.warning(f"Job '{name}' not found")
            return False

        del self.jobs[name]
        logger.info(f"Removed job '{name}'")
        return True

    def save_config(self) -> bool:
        """
        Save current configuration to file

        Returns:
            True if saved successfully
        """
        try:
            # Ensure config directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare configuration data
            config_data = {
                'app': self.app_config.dict(),
                'destinations': [dest.dict() for dest in self.destinations.values()],
                'jobs': [job.dict() for job in self.jobs.values()]
            }

            # Convert datetime objects to strings for YAML serialization
            config_data = self._prepare_for_yaml(config_data)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)

            logger.info(f"Configuration saved to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def _prepare_for_yaml(self, obj: Any) -> Any:
        """Prepare object for YAML serialization (convert datetime to string)"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._prepare_for_yaml(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._prepare_for_yaml(item) for item in obj]
        else:
            return obj

    def reload_config(self):
        """Reload configuration from file"""
        logger.info("Reloading configuration...")
        self._load_config()
        logger.info("Configuration reloaded successfully")

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration"""
        return {
            'app_config': {
                'database_url': self.app_config.database.url if self.app_config else None,
                'web_host': self.app_config.web.host if self.app_config else None,
                'web_port': self.app_config.web.port if self.app_config else None,
                'debug_mode': self.app_config.web.debug if self.app_config else False,
            },
            'destinations': {
                'total': len(self.destinations),
                'active': len([d for d in self.destinations.values() if d.status == "active"]),
                'inactive': len([d for d in self.destinations.values() if d.status == "inactive"]),
                'error': len([d for d in self.destinations.values() if d.status == "error"]),
            },
            'jobs': {
                'total': len(self.jobs),
                'enabled': len([j for j in self.jobs.values() if j.enabled]),
                'disabled': len([j for j in self.jobs.values() if not j.enabled]),
            }
        }