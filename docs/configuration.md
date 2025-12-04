# Configuration Documentation

## Overview

The Network Stats Collector uses YAML-based configuration files with Pydantic validation for type safety and comprehensive validation. The configuration system supports global destination management, enhanced job scheduling, and flexible application settings.

## Configuration File Structure

The main configuration file is typically located at `config/app.yaml` and consists of three main sections:

```yaml
# Application settings
app:
  database:
    # Database configuration
  web:
    # Web server configuration
  logging:
    # Logging configuration

# Global destinations
destinations:
  # Destination definitions

# Job definitions
jobs:
  # Job configurations
```

## Application Configuration (`app` section)

### Database Configuration

```yaml
app:
  database:
    url: "sqlite:///network_stats.db"  # Database connection URL
    pool_size: 5                       # Connection pool size
    echo: false                        # SQL query logging (development)
```

**Database URL Options:**
- SQLite: `sqlite:///network_stats.db` (default, file-based)
- PostgreSQL: `postgresql://user:pass@localhost/network_stats`
- MySQL: `mysql://user:pass@localhost/network_stats`

### Web Server Configuration

```yaml
app:
  web:
    host: "127.0.0.1"        # Server bind address
    port: 8080               # Server port
    debug: false            # Debug mode (development only)
    cors_origins:           # CORS allowed origins
      - "http://127.0.0.1:8080"
      - "http://localhost:8080"
```

### Logging Configuration

```yaml
app:
  logging:
    level: "INFO"             # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    file: "logs/app.log"      # Log file path (optional)
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## Destination Configuration (`destinations` section)

Global destinations can be defined once and reused across multiple jobs.

### Destination Fields

```yaml
destinations:
  - name: "google-dns"
    host: "8.8.8.8"
    display_name: "Google DNS"
    description: "Google's public DNS server"
    tags: ["dns", "public", "google"]
    status: "active"

  - name: "local-server"
    host: "192.168.1.100"
    display_name: "Local Web Server"
    description: "Internal web server"
    tags: ["internal", "web"]
    status: "active"
```

**Field Descriptions:**
- `name` (required): Unique identifier for the destination
- `host` (required): IP address or hostname
- `display_name` (required): Human-readable name
- `description` (optional): Detailed description
- `tags` (optional): Array of tags for categorization
- `status` (optional): Destination status (active, inactive, error)

**Status Values:**
- `active`: Destination is monitored and included in jobs
- `inactive`: Destination exists but is excluded from monitoring
- `error`: Destination encountered errors and needs attention

## Job Configuration (`jobs` section)

Jobs define what to monitor, when to monitor, and which metrics to collect.

### Basic Job Configuration

```yaml
jobs:
  - name: "critical-servers"
    description: "Monitor critical infrastructure servers"
    enabled: true
    interval: 300                    # Collection interval in seconds (5 minutes)
    metrics: ["ping", "traceroute"] # Metrics to collect
    destinations: ["google-dns", "local-server"]

    # Time window scheduling
    start_time: "2024-01-01T09:00:00Z"
    end_time: "2024-12-31T17:00:00Z"

    # Metadata
    tags: ["critical", "infrastructure"]
```

### Job Fields

**Required Fields:**
- `name`: Unique job identifier
- `interval`: Collection interval in seconds (minimum 60)
- `destinations`: Array of destination names

**Optional Fields:**
- `description`: Job description
- `enabled`: Whether job is active (default: true)
- `metrics`: Array of metrics to collect (default: ["ping"])
- `start_time`: Job execution start time (ISO 8601 format)
- `end_time`: Job execution end time (ISO 8601 format)
- `tags`: Array of tags for categorization

### Available Metrics

- `ping`: Basic connectivity and response time
- `traceroute`: Network path analysis
- `dns`: DNS resolution testing
- `bandwidth`: Bandwidth measurement
- `jitter`: Network latency variation
- `packet_loss`: Packet loss measurement

### Time Window Scheduling

Jobs can be configured with execution time windows:

```yaml
jobs:
  - name: "business-hours-monitoring"
    interval: 300
    start_time: "2024-01-01T09:00:00Z"  # Start monitoring at 9 AM
    end_time: "2024-01-01T17:00:00Z"    # Stop monitoring at 5 PM
    destinations: ["critical-server"]
```

**Time Format:**
- ISO 8601 format is required
- UTC timezone is recommended
- Example: `2024-01-15T14:30:00Z`

### Job Examples

#### 1. Simple Ping Monitoring
```yaml
jobs:
  - name: "basic-ping-check"
    interval: 60
    metrics: ["ping"]
    destinations: ["google-dns"]
    enabled: true
```

#### 2. Comprehensive Monitoring
```yaml
jobs:
  - name: "full-diagnostics"
    description: "Complete network diagnostics for all servers"
    interval: 900  # 15 minutes
    metrics: ["ping", "traceroute", "dns", "packet_loss"]
    destinations:
      - "google-dns"
      - "cloudflare-dns"
      - "local-server"
    start_time: "2024-01-01T00:00:00Z"
    enabled: true
```

#### 3. Scheduled Maintenance Window
```yaml
jobs:
  - name: "off-hours-backup-monitoring"
    description: "Monitor backup servers during off-peak hours"
    interval: 600  # 10 minutes
    metrics: ["ping"]
    destinations: ["backup-server"]
    start_time: "2024-01-01T22:00:00Z"  # 10 PM
    end_time: "2024-01-02T06:00:00Z"    # 6 AM next day
    enabled: true
```

## Configuration Validation

The configuration system includes comprehensive validation:

### Destination Validation
- Unique destination names required
- Host field cannot be empty
- Status values must be valid (active, inactive, error)

### Job Validation
- Unique job names required
- Minimum interval of 60 seconds
- All referenced destinations must exist
- End time must be after start time
- Metric types must be valid

### Application Validation
- Database URL must be valid
- Port numbers must be in valid range (1-65535)
- Log levels must be valid

## Configuration Management

### Adding Destinations via API
```python
from src.core.config import DestinationConfig

destination = DestinationConfig(
    name="new-server",
    host="192.168.1.50",
    display_name="New Application Server",
    description="Recently added application server",
    tags=["application", "new"],
    status="active"
)

config.add_destination(destination)
```

### Adding Jobs via API
```python
from src.core.config import JobConfig

job = JobConfig(
    name="new-server-monitoring",
    description="Monitor the new application server",
    interval: 300,
    metrics=["ping", "traceroute"],
    destinations=["new-server"],
    enabled=True
)

config.add_job(job)
```

### Saving Configuration
```python
# Save current configuration to file
config.save_config()

# Reload configuration from file
config.reload_config()
```

## Environment-Specific Configuration

Different environments can use different configuration files:

```bash
# Development
python main.py --config config/dev.yaml

# Production
python main.py --config config/prod.yaml

# Testing
python main.py --config config/test.yaml
```

## Configuration Best Practices

### 1. Use Descriptive Names
```yaml
destinations:
  - name: "prod-web-server-01"  # Clear, descriptive
    host: "10.0.1.101"
    display_name: "Production Web Server 01"

# Avoid:
  - name: "server1"  # Too generic
```

### 2. Organize with Tags
```yaml
destinations:
  - name: "db-master"
    tags: ["database", "production", "critical"]
  - name: "db-replica"
    tags: ["database", "production", "replica"]
```

### 3. Use Consistent Intervals
```yaml
jobs:
  - name: "critical-monitoring"    # More frequent for critical systems
    interval: 60
  - name: "general-monitoring"    # Less frequent for general systems
    interval: 300
```

### 4. Document Complex Jobs
```yaml
jobs:
  - name: "complex-scheduled-job"
    description: |
      This job monitors critical infrastructure during business hours
      and performs comprehensive diagnostics every 15 minutes.
      It includes traceroute to identify network path issues.
```

## Troubleshooting

### Common Configuration Issues

1. **Destination Not Found**
   ```
   Job 'my-job' references destination 'missing-server' which is not defined
   ```
   **Solution:** Ensure all destinations referenced in jobs are defined in the destinations section.

2. **Invalid Time Format**
   ```
   Invalid time format for start_time
   ```
   **Solution:** Use ISO 8601 format with timezone: `2024-01-15T14:30:00Z`

3. **Duplicate Names**
   ```
   Destination 'duplicate-name' already exists
   ```
   **Solution:** Ensure all destinations and jobs have unique names.

### Debugging Configuration

Enable debug mode for detailed configuration loading:

```yaml
app:
  web:
    debug: true
  logging:
    level: "DEBUG"
    file: "logs/debug.log"
```

### Configuration Validation

Use the built-in validation methods:

```python
from src.core.config import Config

config = Config("config/app.yaml")
summary = config.get_config_summary()
print(f"Loaded {summary['destinations']['total']} destinations")
print(f"Loaded {summary['jobs']['enabled']} enabled jobs")
```