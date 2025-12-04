# Network Stats Collector

A comprehensive Windows-based network monitoring tool that collects latency information from multiple destinations and exports data to Excel files for network analysis and diagnostics.

## 🚀 Features

### Global Destination Management
- **Reusable Destinations**: Define destinations once and use them across multiple jobs
- **Dynamic Management**: Add, edit, and delete destinations through API and web interface
- **Status Tracking**: Monitor destination health and availability
- **Flexible Organization**: Tag destinations for categorization and filtering

### Enhanced Job Configuration
- **Time Window Scheduling**: Define start and end times for job execution
- **Flexible Intervals**: Configure collection intervals per job (minimum 60 seconds)
- **Metric Selection**: Choose specific metrics to collect (ping, traceroute, DNS, bandwidth, etc.)
- **Destination Selection**: Select from global destinations for each job
- **Job Metadata**: Organize jobs with descriptions and tags

### Real-time Monitoring
- **Live Dashboard**: Monitor all job statuses in real-time
- **WebSocket Updates**: Receive live updates without page refresh
- **Job Status Tracking**: Track running, stopped, scheduled, and error states
- **Performance Metrics**: View response times, success rates, and trends

### Data Visualization & Analytics
- **Interactive Charts**: Line charts, bar charts, and statistical visualizations
- **Historical Trends**: Analyze network performance over time
- **Comparative Analysis**: Compare performance across destinations and jobs
- **Real-time Graphs**: Live updating charts for current network status

### Export Capabilities
- **Excel Export**: Comprehensive Excel reports with statistical analysis
- **CSV Export**: Raw data export for external analysis
- **Custom Time Ranges**: Export data for specific time periods
- **Multiple Formats**: Support for different data formats and visualizations

## 📋 Requirements

- **Operating System**: Windows 10 or later
- **Python**: 3.8 or higher
- **Package Manager**: UV (recommended)
- **Memory**: Minimum 512MB RAM
- **Storage**: 100MB free disk space (plus data storage)

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/network-stats.git
cd network-stats
```

### 2. Install Dependencies with UV
```bash
# Install project dependencies
uv sync

# Or install specific additional dependencies
uv add fastapi uvicorn pydantic pyyaml aiosqlite pandas openpyxl
```

### 3. Configure the Application
```bash
# Copy example configuration
cp config/app.yaml.example config/app.yaml

# Edit configuration file
notepad config/app.yaml
```

### 4. Run the Application
```bash
# Start the server
uv run python main.py

# Or with custom configuration
uv run python main.py --config config/production.yaml
```

## 📁 Project Structure

```
network_stats/
├── src/                           # Source code
│   ├── api/                       # API endpoints
│   │   ├── routes/               # API route handlers
│   │   └── websocket.py          # WebSocket handlers
│   ├── core/                     # Core functionality
│   │   ├── config.py             # Configuration management
│   │   └── database.py           # Database layer
│   ├── collectors/               # Network data collectors
│   │   ├── base.py               # Base collector interface
│   │   ├── ping_collector.py     # Ping implementation
│   │   └── traceroute.py         # Traceroute implementation
│   ├── services/                 # Business logic services
│   │   ├── export.py             # Excel/CSV export
│   │   └── statistics.py         # Statistical analysis
│   └── utils/                    # Utility functions
├── web/                          # Web interface
│   ├── static/                   # CSS, JavaScript, images
│   └── templates/                # HTML templates
├── config/                       # Configuration files
│   └── app.yaml                  # Main configuration
├── docs/                         # Documentation
│   ├── api.md                    # API documentation
│   ├── database_schema.md        # Database schema
│   └── configuration.md          # Configuration guide
├── tests/                        # Test files
├── main.py                       # Application entry point
└── pyproject.toml               # UV project configuration
```

## ⚙️ Configuration

### Application Configuration

The main configuration file (`config/app.yaml`) contains all application settings:

```yaml
# Application settings
app:
  database:
    url: "sqlite:///network_stats.db"
    pool_size: 5
  web:
    host: "127.0.0.1"
    port: 8080
    debug: false
  logging:
    level: "INFO"
    file: "logs/network_stats.log"

# Global destinations
destinations:
  - name: "google-dns"
    host: "8.8.8.8"
    display_name: "Google DNS"
    description: "Google's public DNS server"
    tags: ["dns", "public"]
    status: "active"

# Job definitions
jobs:
  - name: "critical-servers"
    description: "Monitor critical infrastructure"
    enabled: true
    interval: 300  # 5 minutes
    metrics: ["ping", "traceroute"]
    destinations: ["google-dns"]
    start_time: "2024-01-01T09:00:00Z"
    end_time: "2024-12-31T17:00:00Z"
```

### Available Metrics

- **ping**: Basic connectivity and response time
- **traceroute**: Network path analysis
- **dns**: DNS resolution testing
- **bandwidth**: Bandwidth measurement
- **jitter**: Network latency variation
- **packet_loss**: Packet loss measurement

## 🌐 Web Interface

### Dashboard Features
- **Real-time Status**: Live job monitoring and status updates
- **Performance Charts**: Interactive charts showing network trends
- **Job Management**: Start, stop, and configure monitoring jobs
- **Destination Management**: Add, edit, and remove destinations
- **Analytics View**: Detailed statistics and performance analysis

### Accessing the Web Interface

1. Start the application
2. Open your web browser
3. Navigate to `http://localhost:8080`
4. Access the API documentation at `http://localhost:8080/docs`

## 📊 API Documentation

### REST API Endpoints

#### Destinations
- `GET /api/destinations` - List all destinations
- `POST /api/destinations` - Create new destination
- `GET /api/destinations/{id}` - Get destination details
- `PUT /api/destinations/{id}` - Update destination
- `DELETE /api/destinations/{id}` - Remove destination

#### Jobs
- `GET /api/jobs` - List all jobs
- `POST /api/jobs` - Create new job
- `GET /api/jobs/{id}` - Get job details
- `PUT /api/jobs/{id}` - Update job
- `DELETE /api/jobs/{id}` - Remove job
- `POST /api/jobs/{id}/start` - Start job execution
- `POST /api/jobs/{id}/stop` - Stop job execution

#### Analytics
- `GET /api/jobs/{id}/metrics` - Get job metrics
- `GET /api/jobs/{id}/analytics` - Get job statistics
- `GET /api/jobs/{id}/export` - Export job data

### WebSocket API
- `ws://localhost:8080/ws` - Real-time updates for job status and metrics

For complete API documentation, see `docs/api.md`.

## 🚦 Usage Examples

### Basic Monitoring Setup

1. **Add Destinations**:
```python
import requests

destination = {
    "name": "company-web-server",
    "host": "web.company.com",
    "display_name": "Company Web Server",
    "status": "active"
}
response = requests.post("http://localhost:8080/api/destinations", json=destination)
```

2. **Create Monitoring Job**:
```python
job = {
    "name": "web-server-monitoring",
    "description": "Monitor company web server",
    "enabled": true,
    "interval": 300,  # 5 minutes
    "metrics": ["ping", "traceroute"],
    "destinations": ["company-web-server"]
}
response = requests.post("http://localhost:8080/api/jobs", json=job)
```

3. **Start Monitoring**:
```python
requests.post("http://localhost:8080/api/jobs/1/start")
```

### Data Export

```python
# Export last 24 hours of data
response = requests.get(
    "http://localhost:8080/api/jobs/1/export",
    params={
        "format": "xlsx",
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-02T00:00:00Z"
    }
)

# Save the file
with open("network_data.xlsx", "wb") as f:
    f.write(response.content)
```

## 📈 Data Analysis

### Accessing Metrics Data

```python
import pandas as pd
import requests

# Get metrics for analysis
response = requests.get("http://localhost:8080/api/jobs/1/metrics")
metrics = response.json()

# Convert to DataFrame
df = pd.DataFrame(metrics)

# Analyze response times
print(f"Average response time: {df['response_time_ms'].mean():.2f} ms")
print(f"Success rate: {(df['status'] == 'success').mean() * 100:.1f}%")

# Export to CSV
df.to_csv("network_metrics.csv", index=False)
```

### Excel Export with Analysis

The application automatically generates comprehensive Excel reports including:
- Raw metrics data
- Statistical summaries
- Performance charts
- Success rate analysis
- Response time distributions

## 🔧 Advanced Configuration

### Custom Time Windows

```yaml
jobs:
  - name: "business-hours-monitoring"
    interval: 300
    destinations: ["critical-server"]
    start_time: "2024-01-01T09:00:00Z"    # 9 AM
    end_time: "2024-01-01T17:00:00Z"      # 5 PM
```

### Multiple Destination Jobs

```yaml
jobs:
  - name: "full-network-scan"
    interval: 900  # 15 minutes
    metrics: ["ping", "traceroute", "dns"]
    destinations:
      - "gateway"
      - "dns-server"
      - "web-server"
      - "database-server"
```

### Tag-based Organization

```yaml
destinations:
  - name: "prod-db-01"
    tags: ["production", "database", "critical"]
  - name: "dev-web-01"
    tags: ["development", "web", "testing"]

jobs:
  - name: "production-monitoring"
    destinations: ["prod-db-01", "prod-web-01"]
```

## 🐛 Troubleshooting

### Common Issues

1. **Destination Not Reachable**
   ```
   Solution: Check network connectivity and firewall settings
   Verify destination host and port accessibility
   ```

2. **Job Not Starting**
   ```
   Solution: Ensure all referenced destinations exist
   Check job configuration for validation errors
   Verify system time and scheduling conflicts
   ```

3. **Database Connection Issues**
   ```
   Solution: Check database file permissions
   Verify database URL in configuration
   Ensure sufficient disk space
   ```

### Debug Mode

Enable debug mode for detailed logging:

```yaml
app:
  web:
    debug: true
  logging:
    level: "DEBUG"
    file: "logs/debug.log"
```

### Log Analysis

Check the application log file for errors:

```bash
# View recent logs
tail -f logs/network_stats.log

# Search for errors
grep "ERROR" logs/network_stats.log
```

## 📚 Documentation

- **[API Documentation](docs/api.md)**: Complete REST API reference
- **[Database Schema](docs/database_schema.md)**: Database structure and relationships
- **[Configuration Guide](docs/configuration.md)**: Detailed configuration options
- **[OpenAPI/Swagger](http://localhost:8080/docs)**: Interactive API documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone and install dependencies
git clone <your-fork>
cd network-stats
uv sync

# Run in development mode
uv run python main.py --debug

# Run tests
uv run pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:

- **Issues**: [GitHub Issues](https://github.com/yourusername/network-stats/issues)
- **Documentation**: Check the `docs/` folder
- **API Documentation**: Accessible at `/docs` endpoint when running

## 🗺️ Roadmap

### Version 0.2 (Planned)
- [ ] Advanced notification system
- [ ] Multi-user support with authentication
- [ ] Custom dashboard widgets
- [ ] Integration with external monitoring systems

### Version 0.3 (Future)
- [ ] Distributed monitoring agents
- [ ] Machine learning-based anomaly detection
- [ ] Mobile application
- [ ] Cloud deployment support

## 📊 Version History

- **v0.1.0** - Initial release with basic monitoring
- **v0.1.1** - Added global destination management
- **v0.1.2** - Enhanced job scheduling with time windows
- **v0.1.3** - Real-time dashboard and WebSocket support
- **v0.1.4** - Advanced analytics and export features

---

**Network Stats Collector** - Your comprehensive network monitoring solution for Windows environments.