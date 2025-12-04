# Database Schema Documentation

## Overview

The Network Stats Collector uses SQLite as its primary database with SQLAlchemy ORM. The schema has been designed to support global destination management, enhanced job scheduling, and efficient time-series metric storage.

## Tables

### 1. `destinations`

Stores global destination configurations that can be reused across multiple jobs.

**Columns:**
- `id` (INTEGER, PRIMARY KEY) - Unique identifier
- `name` (STRING, UNIQUE, NOT NULL) - Unique destination name
- `host` (STRING, NOT NULL) - IP address or hostname
- `display_name` (STRING, NOT NULL) - Human-readable display name
- `description` (TEXT, NULLABLE) - Optional description
- `tags` (TEXT, NULLABLE) - JSON array of tags for categorization
- `status` (STRING, NOT NULL, DEFAULT "active") - Destination status (active, inactive, error)
- `created_at` (DATETIME, NOT NULL) - Creation timestamp
- `updated_at` (DATETIME, NOT NULL) - Last update timestamp
- `last_seen` (DATETIME, NULLABLE) - Last time destination was reachable

**Indexes:**
- `idx_host_status` - For querying by host and status
- `idx_name_active` - For querying active destinations by name

### 2. `jobs`

Stores job configurations with destination references and scheduling information.

**Columns:**
- `id` (INTEGER, PRIMARY KEY) - Unique identifier
- `name` (STRING, UNIQUE, NOT NULL) - Unique job name
- `description` (TEXT, NULLABLE) - Job description
- `enabled` (BOOLEAN, NOT NULL, DEFAULT TRUE) - Whether job is active
- `interval` (INTEGER, NOT NULL) - Collection interval in seconds
- `metrics` (TEXT, NOT NULL) - JSON array of metric types to collect
- `destination_ids` (TEXT, NOT NULL) - JSON array of destination IDs
- `start_time` (DATETIME, NULLABLE) - Job execution start time
- `end_time` (DATETIME, NULLABLE) - Job execution end time (optional)
- `status` (STRING, NOT NULL, DEFAULT "stopped") - Job status (running, stopped, scheduled, error)
- `last_run` (DATETIME, NULLABLE) - Timestamp of last execution
- `next_run` (DATETIME, NULLABLE) - Timestamp of next scheduled execution
- `error_message` (TEXT, NULLABLE) - Error details if job failed
- `tags` (TEXT, NULLABLE) - JSON array of tags for categorization
- `created_at` (DATETIME, NOT NULL) - Creation timestamp
- `updated_at` (DATETIME, NOT NULL) - Last update timestamp

**Indexes:**
- `idx_name_enabled` - For querying enabled jobs by name
- `idx_status_scheduled` - For querying scheduled jobs
- `idx_active_jobs` - For querying active jobs

### 3. `metrics`

Stores time-series metric data collected from destinations.

**Columns:**
- `id` (INTEGER, PRIMARY KEY) - Unique identifier
- `timestamp` (DATETIME, NOT NULL) - Metric collection timestamp
- `job_id` (INTEGER, NOT NULL) - Foreign key to jobs.id
- `destination_id` (INTEGER, NOT NULL) - Foreign key to destinations.id
- `host` (STRING, NOT NULL) - Denormalized hostname for query performance
- `metric_type` (STRING, NOT NULL) - Type of metric (ping, traceroute, etc.)
- `status` (STRING, NOT NULL) - Collection status (success, failure, timeout)
- `response_time_ms` (FLOAT, NULLABLE) - Response time in milliseconds
- `additional_data` (TEXT, NULLABLE) - JSON string for metric-specific data
- `created_at` (DATETIME, NOT NULL) - Record creation timestamp

**Indexes:**
- `idx_job_destination_timestamp` - For querying job-specific metrics
- `idx_job_host_timestamp` - For querying job-host metrics
- `idx_metric_type_timestamp` - For querying by metric type
- `idx_status_timestamp` - For querying by status
- `idx_destination_metrics` - For querying destination-specific metrics

### 4. `job_runs`

Tracks execution runs for jobs.

**Columns:**
- `id` (INTEGER, PRIMARY KEY) - Unique identifier
- `job_id` (INTEGER, NOT NULL) - Foreign key to jobs.id
- `start_time` (DATETIME, NOT NULL) - Run start timestamp
- `end_time` (DATETIME, NULLABLE) - Run end timestamp
- `status` (STRING, NOT NULL, DEFAULT "running") - Run status (running, completed, failed)
- `total_destinations` (INTEGER, NOT NULL) - Total destinations in this run
- `successful_destinations` (INTEGER, DEFAULT 0) - Successfully monitored destinations
- `failed_destinations` (INTEGER, DEFAULT 0) - Failed destination attempts
- `error_message` (TEXT, NULLABLE) - Error details if run failed
- `created_at` (DATETIME, NOT NULL) - Record creation timestamp

**Indexes:**
- `idx_job_status_time` - For querying job runs by status and time

## Relationships

- `jobs.destination_ids` → `destinations.id` (Many-to-Many relationship via JSON array)
- `metrics.job_id` → `jobs.id` (Many-to-One)
- `metrics.destination_id` → `destinations.id` (Many-to-One)
- `job_runs.job_id` → `jobs.id` (Many-to-One)

## Key Design Decisions

### JSON Storage for Relationships
- **Destination IDs in Jobs**: Stored as JSON array to support flexible Many-to-Many relationships
- **Metrics Data**: JSON storage for metric-specific data (packet loss, jitter, etc.)
- **Tags**: JSON arrays for flexible categorization

### Denormalization for Performance
- **host field in metrics**: Duplicated from destinations table for query performance
- Enables fast filtering without additional joins

### Time-Series Optimization
- **Timestamp Indexes**: Comprehensive indexing for time-based queries
- **Composite Indexes**: Optimized for common query patterns
- **Partitioning Ready**: Schema designed for easy partitioning if needed

### Scheduling Support
- **Time Windows**: Jobs support start_time and end_time for execution windows
- **Status Tracking**: Multiple status fields for comprehensive job monitoring
- **Run History**: Detailed tracking of job execution runs

## Migration Considerations

When upgrading from previous versions:

1. **New Tables**: Add `destinations` table
2. **Job Migration**: Convert inline machine definitions to destination references
3. **Metric Migration**: Update metric records to include destination_id
4. **Index Creation**: Add new indexes for performance

## Performance Notes

### Query Optimization
- Use destination_id filtering when possible (faster than hostname)
- Time-range queries benefit from timestamp indexes
- Job-specific queries use job_id indexes

### Storage Efficiency
- JSON fields enable flexible schemas without schema changes
- Consider JSON size limits for large arrays
- Monitor metric table growth for archival policies

### Scaling Considerations
- Partitioning by timestamp for large metric tables
- Consider read replicas for heavy query workloads
- Implement data retention policies for historical data