"""
Dashboard API routes for Network Stats Collector

API endpoints for dashboard data, including system overview,
real-time statistics, and summary information.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Pydantic models for dashboard responses
class JobSummary(BaseModel):
    job_id: str
    job_name: str
    status: str  # running, stopped, error
    enabled: bool
    total_hosts: int
    successful_hosts: int
    failed_hosts: int
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    avg_response_time: Optional[float]

class SystemOverview(BaseModel):
    total_jobs: int
    active_jobs: int
    total_hosts: int
    total_metrics_today: int
    system_status: str
    uptime: Optional[str]

class RecentMetric(BaseModel):
    timestamp: datetime
    job_id: str
    host: str
    metric_type: str
    status: str
    response_time_ms: Optional[float]

class AlertSummary(BaseModel):
    level: str  # info, warning, error, critical
    message: str
    timestamp: datetime
    job_id: Optional[str]

class DashboardResponse(BaseModel):
    overview: SystemOverview
    jobs: List[JobSummary]
    recent_metrics: List[RecentMetric]
    alerts: List[AlertSummary]

@router.get("/", response_model=DashboardResponse)
async def get_dashboard(request):
    """
    Get comprehensive dashboard data

    Returns system overview, job summaries, recent metrics, and alerts.
    """
    try:
        config = request.app.state.config
        db = request.app.state.db

        # Get all jobs
        jobs = config.get_all_jobs()
        enabled_jobs = config.get_enabled_jobs()

        # Calculate overview statistics
        total_jobs = len(jobs)
        active_jobs = len(enabled_jobs)

        # Count total hosts across all jobs
        total_hosts = sum(len(job.machines) for job in jobs.values())

        # Get metrics count for today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_metrics = await db.get_metrics(start_time=today_start)
        total_metrics_today = len(today_metrics)

        # Create overview
        overview = SystemOverview(
            total_jobs=total_jobs,
            active_jobs=active_jobs,
            total_hosts=total_hosts,
            total_metrics_today=total_metrics_today,
            system_status="healthy",  # TODO: Implement health check
            uptime=None  # TODO: Calculate from application start time
        )

        # Create job summaries
        job_summaries = []
        for job_id, job_config in jobs.items():
            # TODO: Get real runtime data from job manager
            # For now, create basic summary
            job_summary = JobSummary(
                job_id=job_id,
                job_name=job_config.name,
                status="stopped",  # TODO: Get real status
                enabled=job_config.enabled,
                total_hosts=len(job_config.machines),
                successful_hosts=0,  # TODO: Get from last run
                failed_hosts=0,     # TODO: Get from last run
                last_run=None,      # TODO: Get from job manager
                next_run=None,      # TODO: Get from job manager
                avg_response_time=None  # TODO: Calculate from recent metrics
            )
            job_summaries.append(job_summary)

        # Get recent metrics (last 24 hours)
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_metrics_db = await db.get_metrics(
            start_time=yesterday,
            limit=100
        )

        recent_metrics = [
            RecentMetric(
                timestamp=m.timestamp,
                job_id=m.job_id,
                host=m.host,
                metric_type=m.metric_type,
                status=m.status,
                response_time_ms=m.response_time_ms
            )
            for m in recent_metrics_db
        ]

        # TODO: Get real alerts from alert system
        alerts = []

        return DashboardResponse(
            overview=overview,
            jobs=job_summaries,
            recent_metrics=recent_metrics,
            alerts=alerts
        )

    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")

@router.get("/overview", response_model=SystemOverview)
async def get_system_overview(request):
    """
    Get system overview statistics

    Returns high-level system status and statistics.
    """
    try:
        config = request.app.state.config
        db = request.app.state.db

        # Get all jobs
        jobs = config.get_all_jobs()
        enabled_jobs = config.get_enabled_jobs()

        # Calculate overview statistics
        total_jobs = len(jobs)
        active_jobs = len(enabled_jobs)
        total_hosts = sum(len(job.machines) for job in jobs.values())

        # Get metrics count for today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_metrics = await db.get_metrics(start_time=today_start)
        total_metrics_today = len(today_metrics)

        return SystemOverview(
            total_jobs=total_jobs,
            active_jobs=active_jobs,
            total_hosts=total_hosts,
            total_metrics_today=total_metrics_today,
            system_status="healthy",  # TODO: Implement health check
            uptime=None  # TODO: Calculate from application start time
        )

    except Exception as e:
        logger.error(f"Failed to get system overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system overview")

@router.get("/jobs/summary", response_model=List[JobSummary])
async def get_jobs_summary(request):
    """
    Get summary of all jobs

    Returns status and performance summary for each job.
    """
    try:
        config = request.app.state.config

        # Get all jobs
        jobs = config.get_all_jobs()

        # Create job summaries
        job_summaries = []
        for job_id, job_config in jobs.items():
            # TODO: Get real runtime data from job manager
            job_summary = JobSummary(
                job_id=job_id,
                job_name=job_config.name,
                status="stopped",  # TODO: Get real status
                enabled=job_config.enabled,
                total_hosts=len(job_config.machines),
                successful_hosts=0,  # TODO: Get from last run
                failed_hosts=0,     # TODO: Get from last run
                last_run=None,      # TODO: Get from job manager
                next_run=None,      # TODO: Get from job manager
                avg_response_time=None  # TODO: Calculate from recent metrics
            )
            job_summaries.append(job_summary)

        return job_summaries

    except Exception as e:
        logger.error(f"Failed to get jobs summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs summary")

@router.get("/metrics/recent", response_model=List[RecentMetric])
async def get_recent_metrics(
    limit: int = Query(100, le=1000),
    job_id: Optional[str] = Query(None),
    host: Optional[str] = Query(None),
    request: Request = None
):
    """
    Get recent metrics

    Returns the most recent metric data with optional filtering.
    """
    try:
        db = request.app.state.db

        # Get recent metrics
        recent_metrics_db = await db.get_metrics(
            job_id=job_id,
            host=host,
            limit=limit
        )

        # Convert to response format
        recent_metrics = [
            RecentMetric(
                timestamp=m.timestamp,
                job_id=m.job_id,
                host=m.host,
                metric_type=m.metric_type,
                status=m.status,
                response_time_ms=m.response_time_ms
            )
            for m in recent_metrics_db
        ]

        return recent_metrics

    except Exception as e:
        logger.error(f"Failed to get recent metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recent metrics")

@router.get("/metrics/statistics")
async def get_metrics_statistics(
    job_id: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),  # Last 1-168 hours (1 week)
    request: Request = None
):
    """
    Get metrics statistics

    Returns statistical analysis of metrics data including averages,
    min/max values, and success rates.
    """
    try:
        db = request.app.state.db

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get metrics for analysis
        metrics = await db.get_metrics(
            job_id=job_id,
            start_time=start_time,
            end_time=end_time
        )

        if not metrics:
            return {
                "total_metrics": 0,
                "success_rate": 0.0,
                "avg_response_time": None,
                "min_response_time": None,
                "max_response_time": None,
                "metric_types": [],
                "hosts": []
            }

        # Calculate statistics
        total_metrics = len(metrics)
        successful_metrics = [m for m in metrics if m.status == "success"]
        success_rate = len(successful_metrics) / total_metrics * 100

        # Response time statistics
        response_times = [m.response_time_ms for m in successful_metrics if m.response_time_ms is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else None
        min_response_time = min(response_times) if response_times else None
        max_response_time = max(response_times) if response_times else None

        # Unique metric types and hosts
        metric_types = list(set(m.metric_type for m in metrics))
        hosts = list(set(m.host for m in metrics))

        return {
            "total_metrics": total_metrics,
            "success_rate": round(success_rate, 2),
            "avg_response_time": round(avg_response_time, 2) if avg_response_time else None,
            "min_response_time": round(min_response_time, 2) if min_response_time else None,
            "max_response_time": round(max_response_time, 2) if max_response_time else None,
            "metric_types": metric_types,
            "hosts": hosts,
            "time_range_hours": hours
        }

    except Exception as e:
        logger.error(f"Failed to get metrics statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics statistics")

@router.get("/alerts")
async def get_alerts(
    level: Optional[str] = Query(None, regex="^(info|warning|error|critical)$"),
    limit: int = Query(50, le=500),
    request: Request = None
):
    """
    Get system alerts

    Returns system alerts and notifications with optional filtering.
    """
    try:
        # TODO: Implement alert system
        # For now, return empty list
        return {
            "alerts": [],
            "total_alerts": 0,
            "unread_alerts": 0
        }

    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")