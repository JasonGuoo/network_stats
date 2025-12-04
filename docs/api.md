# API Documentation

## Overview

The Network Stats Collector provides a RESTful API for managing destinations, jobs, and accessing network metrics. The API is built with FastAPI and includes automatic OpenAPI/Swagger documentation.

## Base URL

```
http://localhost:18080
```

## Authentication

Currently, the API does not require authentication. This may change in future versions.

## Response Format

All API responses use JSON format:

```json
{
  "data": {},
  "message": "Success",
  "status": "success"
}
```

Error responses include detailed error information:

```json
{
  "detail": "Error description",
  "status": "error"
}
```

## Destinations API

### Get All Destinations

**Endpoint:** `GET /api/destinations`

**Description:** Retrieve all configured destinations

**Query Parameters:**
- `status` (optional): Filter by status (active, inactive, error)
- `tags` (optional): Filter by tags (comma-separated)

**Response:**
```json
[
  {
    "id": 1,
    "name": "google-dns",
    "host": "8.8.8.8",
    "display_name": "Google DNS",
    "description": "Google's public DNS server",
    "tags": ["dns", "public"],
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "last_seen": "2024-01-01T12:00:00Z"
  }
]
```

### Get Single Destination

**Endpoint:** `GET /api/destinations/{destination_id}`

**Description:** Retrieve a specific destination by ID

**Path Parameters:**
- `destination_id`: Destination ID (integer)

**Response:**
```json
{
  "id": 1,
  "name": "google-dns",
  "host": "8.8.8.8",
  "display_name": "Google DNS",
  "description": "Google's public DNS server",
  "tags": ["dns", "public"],
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "last_seen": "2024-01-01T12:00:00Z"
}
```

### Create Destination

**Endpoint:** `POST /api/destinations`

**Description:** Create a new destination

**Request Body:**
```json
{
  "name": "new-server",
  "host": "192.168.1.100",
  "display_name": "New Application Server",
  "description": "Recently added server",
  "tags": ["application", "new"],
  "status": "active"
}
```

**Response:**
```json
{
  "id": 2,
  "name": "new-server",
  "host": "192.168.1.100",
  "display_name": "New Application Server",
  "description": "Recently added server",
  "tags": ["application", "new"],
  "status": "active",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "last_seen": null
}
```

### Update Destination

**Endpoint:** `PUT /api/destinations/{destination_id}`

**Description:** Update an existing destination

**Path Parameters:**
- `destination_id`: Destination ID (integer)

**Request Body:** Same as create destination

**Response:** Updated destination object

### Delete Destination

**Endpoint:** `DELETE /api/destinations/{destination_id}`

**Description:** Delete a destination (only if not used by any jobs)

**Path Parameters:**
- `destination_id`: Destination ID (integer)

**Response:**
```json
{
  "message": "Destination deleted successfully"
}
```

### Get Destination Status

**Endpoint:** `GET /api/destinations/{destination_id}/status`

**Description:** Get current status and health information for a destination

**Path Parameters:**
- `destination_id`: Destination ID (integer)

**Response:**
```json
{
  "id": 1,
  "name": "google-dns",
  "host": "8.8.8.8",
  "status": "active",
  "last_seen": "2024-01-01T12:00:00Z",
  "last_ping": 15.2,
  "last_check": "2024-01-01T12:05:00Z",
  "uptime_percentage": 99.8,
  "recent_failures": 0
}
```

## Jobs API

### Get All Jobs

**Endpoint:** `GET /api/jobs`

**Description:** Retrieve all configured jobs with current status

**Query Parameters:**
- `enabled` (optional): Filter by enabled status (true/false)
- `status` (optional): Filter by job status (running, stopped, scheduled, error)
- `tags` (optional): Filter by tags (comma-separated)

**Response:**
```json
[
  {
    "id": 1,
    "name": "critical-servers",
    "description": "Monitor critical infrastructure",
    "enabled": true,
    "interval": 300,
    "metrics": ["ping", "traceroute"],
    "destinations": ["google-dns", "local-server"],
    "start_time": "2024-01-01T09:00:00Z",
    "end_time": "2024-12-31T17:00:00Z",
    "status": "running",
    "last_run": "2024-01-01T12:00:00Z",
    "next_run": "2024-01-01T12:05:00Z",
    "error_message": null,
    "tags": ["critical"],
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Get Single Job

**Endpoint:** `GET /api/jobs/{job_id}`

**Description:** Retrieve a specific job by ID

**Path Parameters:**
- `job_id`: Job ID (integer)

**Response:** Job object with full details

### Create Job

**Endpoint:** `POST /api/jobs`

**Description:** Create a new monitoring job

**Request Body:**
```json
{
  "name": "web-servers",
  "description": "Monitor all web servers",
  "enabled": true,
  "interval": 300,
  "metrics": ["ping", "traceroute"],
  "destinations": ["google-dns", "local-server"],
  "start_time": "2024-01-01T09:00:00Z",
  "end_time": "2024-12-31T17:00:00Z",
  "tags": ["web", "production"]
}
```

**Response:** Created job object

### Update Job

**Endpoint:** `PUT /api/jobs/{job_id}`

**Description:** Update an existing job

**Path Parameters:**
- `job_id`: Job ID (integer)

**Request Body:** Same as create job

**Response:** Updated job object

### Delete Job

**Endpoint:** `DELETE /api/jobs/{job_id}`

**Description:** Delete a job

**Path Parameters:**
- `job_id`: Job ID (integer)

**Response:**
```json
{
  "message": "Job deleted successfully"
}
```

### Start Job

**Endpoint:** `POST /api/jobs/{job_id}/start`

**Description:** Start monitoring for a job

**Path Parameters:**
- `job_id`: Job ID (integer)

**Response:**
```json
{
  "message": "Job started successfully",
  "job_id": 1,
  "status": "running",
  "next_run": "2024-01-01T12:05:00Z"
}
```

### Stop Job

**Endpoint:** `POST /api/jobs/{job_id}/stop`

**Description:** Stop monitoring for a job

**Path Parameters:**
- `job_id`: Job ID (integer)

**Response:**
```json
{
  "message": "Job stopped successfully",
  "job_id": 1,
  "status": "stopped"
}
```

### Get Job Metrics

**Endpoint:** `GET /api/jobs/{job_id}/metrics`

**Description:** Retrieve metrics data for a specific job

**Path Parameters:**
- `job_id`: Job ID (integer)

**Query Parameters:**
- `start_time` (optional): ISO 8601 start time
- `end_time` (optional): ISO 8601 end time
- `metric_type` (optional): Filter by metric type
- `destination_id` (optional): Filter by destination ID
- `limit` (optional): Maximum number of records (default: 1000)

**Response:**
```json
[
  {
    "id": 1001,
    "timestamp": "2024-01-01T12:00:00Z",
    "job_id": 1,
    "destination_id": 1,
    "host": "8.8.8.8",
    "metric_type": "ping",
    "status": "success",
    "response_time_ms": 15.2,
    "additional_data": null,
    "created_at": "2024-01-01T12:00:00Z"
  }
]
```

### Get Job Analytics

**Endpoint:** `GET /api/jobs/{job_id}/analytics`

**Description:** Get statistical analytics for a job

**Path Parameters:**
- `job_id`: Job ID (integer)

**Query Parameters:**
- `hours` (optional): Time range in hours (default: 24)

**Response:**
```json
{
  "job_id": 1,
  "job_name": "critical-servers",
  "time_range_hours": 24,
  "total_metrics": 2880,
  "success_rate": 99.8,
  "avg_response_time": 15.2,
  "min_response_time": 12.1,
  "max_response_time": 45.8,
  "metric_breakdown": {
    "ping": {
      "count": 1440,
      "success_rate": 99.9,
      "avg_response_time": 15.2
    },
    "traceroute": {
      "count": 1440,
      "success_rate": 99.7,
      "avg_response_time": 125.5
    }
  },
  "destination_breakdown": {
    "google-dns": {
      "count": 1440,
      "success_rate": 99.9,
      "avg_response_time": 15.1
    },
    "local-server": {
      "count": 1440,
      "success_rate": 99.7,
      "avg_response_time": 15.3
    }
  }
}
```

### Export Job Data

**Endpoint:** `GET /api/jobs/{job_id}/export`

**Description:** Export job data in Excel or CSV format

**Path Parameters:**
- `job_id`: Job ID (integer)

**Query Parameters:**
- `format`: Export format (xlsx, csv)
- `start_time` (optional): ISO 8601 start time
- `end_time` (optional): ISO 8601 end time
- `metric_type` (optional): Filter by metric type

**Response:** File download with appropriate headers

## Dashboard API

### Get Dashboard Overview

**Endpoint:** `GET /api/dashboard`

**Description:** Get comprehensive dashboard overview

**Response:**
```json
{
  "overview": {
    "total_jobs": 5,
    "active_jobs": 3,
    "total_destinations": 10,
    "total_metrics_today": 14400,
    "system_status": "healthy"
  },
  "jobs": [
    {
      "job_id": 1,
      "job_name": "critical-servers",
      "status": "running",
      "enabled": true,
      "total_hosts": 2,
      "successful_hosts": 2,
      "failed_hosts": 0,
      "last_run": "2024-01-01T12:00:00Z",
      "avg_response_time": 15.2
    }
  ],
  "recent_metrics": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "job_id": 1,
      "job_name": "critical-servers",
      "host": "8.8.8.8",
      "metric_type": "ping",
      "status": "success",
      "response_time_ms": 15.2
    }
  ],
  "alerts": []
}
```

### Get System Health

**Endpoint:** `GET /api/dashboard/health`

**Description:** Get system health and status information

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "uptime": "5 days, 3 hours, 45 minutes",
  "active_jobs": 3,
  "running_collectors": 6,
  "database_status": "connected",
  "last_metric_collection": "2024-01-01T11:59:30Z",
  "system_resources": {
    "cpu_usage": 15.2,
    "memory_usage": 45.8,
    "disk_usage": 23.1
  }
}
```

### Get Chart Data

**Endpoint:** `GET /api/charts/{job_id}/{chart_type}`

**Description:** Get formatted data for charts

**Path Parameters:**
- `job_id`: Job ID (integer)
- `chart_type`: Chart type (line, bar, pie, heatmap)

**Query Parameters:**
- `hours` (optional): Time range in hours (default: 24)
- `metric_type` (optional): Filter by metric type

**Response:**
```json
{
  "chart_type": "line",
  "data": {
    "labels": ["12:00", "12:05", "12:10", "12:15"],
    "datasets": [
      {
        "label": "Google DNS",
        "data": [15.2, 14.8, 15.5, 15.1],
        "borderColor": "#3b82f6",
        "backgroundColor": "rgba(59, 130, 246, 0.1)"
      },
      {
        "label": "Local Server",
        "data": [25.3, 24.9, 26.1, 25.7],
        "borderColor": "#ef4444",
        "backgroundColor": "rgba(239, 68, 68, 0.1)"
      }
    ]
  },
  "options": {
    "responsive": true,
    "scales": {
      "y": {
        "title": {
          "display": true,
          "text": "Response Time (ms)"
        }
      }
    }
  }
}
```

## WebSocket API

### Real-time Updates

**Endpoint:** `ws://localhost:8080/ws`

**Description:** WebSocket connection for real-time updates

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

**Message Types:**

1. **Job Status Update**
```json
{
  "type": "job_status_update",
  "data": {
    "job_id": 1,
    "job_name": "critical-servers",
    "status": "running",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

2. **Metrics Collected**
```json
{
  "type": "metrics_collected",
  "data": {
    "job_id": 1,
    "job_name": "critical-servers",
    "metrics": [
      {
        "host": "8.8.8.8",
        "metric_type": "ping",
        "status": "success",
        "response_time_ms": 15.2
      }
    ],
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

3. **System Alerts**
```json
{
  "type": "system_alert",
  "data": {
    "level": "warning",
    "message": "Destination 'google-dns' is experiencing high latency",
    "job_id": 1,
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource already exists
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "detail": "Detailed error message",
  "status_code": 400,
  "error_type": "ValidationError"
}
```

### Common Errors

1. **Validation Error**
```json
{
  "detail": [
    {
      "loc": ["body", "interval"],
      "msg": "ensure this value is greater than or equal to 60",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

2. **Resource Not Found**
```json
{
  "detail": "Destination with ID 999 not found"
}
```

3. **Conflict**
```json
{
  "detail": "Destination 'google-dns' already exists"
}
```

## Rate Limiting

Currently, no rate limiting is implemented. This may be added in future versions.

## API Versioning

The current API version is v1. Future versions will include versioning in the URL path:

```
/api/v1/destinations
/api/v2/destinations
```

## OpenAPI Documentation

Interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`
- **OpenAPI JSON**: `http://localhost:8080/openapi.json`

## Usage Examples

### Python Client

```python
import requests
import json

# Base URL
BASE_URL = "http://localhost:8080"

# Get all destinations
response = requests.get(f"{BASE_URL}/api/destinations")
destinations = response.json()

# Create a new destination
new_dest = {
    "name": "test-server",
    "host": "192.168.1.50",
    "display_name": "Test Server",
    "status": "active"
}
response = requests.post(f"{BASE_URL}/api/destinations", json=new_dest)
created_dest = response.json()

# Get job metrics
response = requests.get(f"{BASE_URL}/api/jobs/1/metrics")
metrics = response.json()
```

### JavaScript Client

```javascript
// Get all destinations
fetch('/api/destinations')
  .then(response => response.json())
  .then(destinations => {
    console.log('Destinations:', destinations);
  });

// Create a new destination
const newDest = {
  name: 'test-server',
  host: '192.168.1.50',
  display_name: 'Test Server',
  status: 'active'
};

fetch('/api/destinations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(newDest)
})
.then(response => response.json())
.then(destination => {
  console.log('Created destination:', destination);
});
```

### WebSocket Client

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = function(event) {
  console.log('Connected to WebSocket');
};

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);

  switch(message.type) {
    case 'job_status_update':
      updateJobStatus(message.data);
      break;
    case 'metrics_collected':
      updateMetricsDisplay(message.data);
      break;
    case 'system_alert':
      showAlert(message.data);
      break;
  }
};

ws.onerror = function(error) {
  console.error('WebSocket error:', error);
};

ws.onclose = function() {
  console.log('WebSocket connection closed');
  // Attempt to reconnect after 5 seconds
  setTimeout(connectWebSocket, 5000);
};
```
