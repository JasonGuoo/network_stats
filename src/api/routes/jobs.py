"""
Jobs API routes for Network Stats Collector

REST API endpoints for managing network monitoring jobs,
including creation, modification, status monitoring, and data export.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.core.config import JobConfig, DestinationConfig
from src.core.database import Database

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Pydantic models for API requests/responses
class DestinationConfigRequest(BaseModel):
    host: str
    display_name: str

class JobConfigRequest(BaseModel):
    name: str
    interval: int
    enabled: bool = True
    metrics: List[str] = ["ping"]
    destinations: List[DestinationConfigRequest]

class JobConfigResponse(BaseModel):
    name: str
    interval: int
    enabled: bool
    metrics: List[str]
    destinations: List[DestinationConfigRequest]
    status: Optional[str] = None  # Current job status
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None

class MetricDataResponse(BaseModel):
    timestamp: datetime
    job_id: str
    host: str
    metric_type: str
    status: str
    response_time_ms: Optional[float]
    additional_data: Optional[str]

class JobRunResponse(BaseModel):
    id: int
    job_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    total_destinations: int
    successful_destinations: int
    failed_destinations: int
    error_message: Optional[str]

def get_database() -> Database:
    """Dependency to get database instance"""
    # This would typically be injected via FastAPI's dependency system
    # For now, we'll access it through the app state
    from fastapi import Request
    def _get_db(request: Request):
        return request.app.state.db
    return _get_db

@router.get("/", response_model=List[JobConfigResponse])
async def get_jobs(request):
    """
    Get all configured jobs with their current status

    Returns a list of all jobs, including their configuration and runtime status.
    """
    try:
        config = request.app.state.config
        jobs = config.get_all_jobs()

        job_responses = []
        for job_name, job_config in jobs.items():
            # Convert to response model
            destinations = [
                DestinationConfigRequest(host=d.host, display_name=d.display_name)
                for d in job_config.destinations
            ]

            job_response = JobConfigResponse(
                name=job_config.name,
                interval=job_config.interval,
                enabled=job_config.enabled,
                metrics=job_config.metrics,
                destinations=destinations
            )

            # Add runtime status information from job manager
            job_manager = request.app.state.job_manager
            db = request.app.state.db

            # Get job from database to get proper ID and status
            job_record = await db.get_job_by_name(job_name)
            if job_record:
                job_response.status = await job_manager.get_job_status(job_record.id)
                job_response.last_run = job_record.last_run
                job_response.next_run = job_record.next_run

            job_responses.append(job_response)

        return job_responses

    except Exception as e:
        logger.error(f"Failed to get jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs")

@router.get("/{job_id}", response_model=JobConfigResponse)
async def get_job(job_id: str, request):
    """
    Get a specific job configuration

    Args:
        job_id: Unique identifier for the job
    """
    try:
        config = request.app.state.config
        job_config = config.get_job(job_id)

        if not job_config:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        destinations = [
            DestinationConfigRequest(host=d.host, display_name=d.display_name)
            for d in job_config.destinations
        ]

        # Get job from database to get proper ID and status
        db = request.app.state.db
        job_manager = request.app.state.job_manager

        job_record = await db.get_job_by_name(job_id)
        if job_record:
            return JobConfigResponse(
                name=job_config.name,
                interval=job_config.interval,
                enabled=job_config.enabled,
                metrics=job_config.metrics,
                destinations=destinations,
                status=await job_manager.get_job_status(job_record.id),
                last_run=job_record.last_run,
                next_run=job_record.next_run
            )
        else:
            return JobConfigResponse(
                name=job_config.name,
                interval=job_config.interval,
                enabled=job_config.enabled,
                metrics=job_config.metrics,
                destinations=destinations
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job")

@router.post("/", response_model=JobConfigResponse)
async def create_job(job_data: JobConfigRequest, request):
    """
    Create a new monitoring job

    Args:
        job_data: Job configuration data
    """
    try:
        config = request.app.state.config

        # Check if job already exists
        if config.get_job(job_data.name):
            raise HTTPException(status_code=409, detail=f"Job '{job_data.name}' already exists")

        # Convert request to JobConfig
        destinations = [
            DestinationConfig(host=d.host, display_name=d.display_name)
            for d in job_data.destinations
        ]

        job_config = JobConfig(
            name=job_data.name,
            interval=job_data.interval,
            enabled=job_data.enabled,
            metrics=job_data.metrics,
            destinations=destinations
        )

        # Save to configuration file and reload
        config.add_job(job_config)
        config.save_config()

        # Convert to response format
        destinations_response = [
            DestinationConfigRequest(host=d.host, display_name=d.display_name)
            for d in job_config.destinations
        ]

        return JobConfigResponse(
            name=job_config.name,
            interval=job_config.interval,
            enabled=job_config.enabled,
            metrics=job_config.metrics,
            destinations=destinations_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create job '{job_data.name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to create job")

@router.put("/{job_id}", response_model=JobConfigResponse)
async def update_job(job_id: str, job_data: JobConfigRequest, request):
    """
    Update an existing monitoring job

    Args:
        job_id: Unique identifier for the job
        job_data: Updated job configuration data
    """
    try:
        config = request.app.state.config

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Check if name is being changed and conflicts with existing job
        if job_data.name != job_id and config.get_job(job_data.name):
            raise HTTPException(status_code=409, detail=f"Job '{job_data.name}' already exists")

        # Convert request to JobConfig
        destinations = [
            DestinationConfig(host=d.host, display_name=d.display_name)
            for d in job_data.destinations
        ]

        job_config = JobConfig(
            name=job_data.name,
            interval=job_data.interval,
            enabled=job_data.enabled,
            metrics=job_data.metrics,
            destinations=destinations
        )

        # Update configuration file and reload
        config.update_job(job_id, job_config)
        config.save_config()

        # Convert to response format
        destinations_response = [
            DestinationConfigRequest(host=d.host, display_name=d.display_name)
            for d in job_config.destinations
        ]

        return JobConfigResponse(
            name=job_config.name,
            interval=job_config.interval,
            enabled=job_config.enabled,
            metrics=job_config.metrics,
            destinations=destinations_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to update job")

@router.delete("/{job_id}")
async def delete_job(job_id: str, request):
    """
    Delete a monitoring job

    Args:
        job_id: Unique identifier for the job
    """
    try:
        config = request.app.state.config

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Remove job from configuration
        config.remove_job(job_id)
        config.save_config()

        # Stop job if it's running
        job_manager = request.app.state.job_manager
        await job_manager.stop_job(int(job_id))  # Convert to int for job manager

        return {"message": f"Job '{job_id}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to delete job")

@router.get("/{job_id}/status")
async def get_job_status(job_id: str, request):
    """
    Get current status of a specific job

    Args:
        job_id: Unique identifier for the job
    """
    try:
        config = request.app.state.config

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Get real-time status from job manager
        db = request.app.state.db
        job_manager = request.app.state.job_manager

        job_record = await db.get_job_by_name(job_id)
        if job_record:
            status = await job_manager.get_job_status(job_record.id)
            return {
                "job_id": job_id,
                "status": status,
                "last_run": job_record.last_run,
                "next_run": job_record.next_run,
                "enabled": job_record.enabled
            }
        else:
            return {
                "job_id": job_id,
                "status": "not_found",
                "last_run": None,
                "next_run": None,
                "enabled": False
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to get job status")

@router.get("/{job_id}/metrics", response_model=List[MetricDataResponse])
async def get_job_metrics(
    job_id: str,
    request: Request,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(1000, le=10000)
):
    """
    Get metrics data for a specific job

    Args:
        job_id: Unique identifier for the job
        start_time: Filter by start time
        end_time: Filter by end time
        limit: Maximum number of records to return
    """
    try:
        config = request.app.state.config
        db = request.app.state.db

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Get metrics from database
        metrics = await db.get_metrics(
            job_id=job_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        # Convert to response format
        return [
            MetricDataResponse(
                timestamp=m.timestamp,
                job_id=m.job_id,
                host=m.host,
                metric_type=m.metric_type,
                status=m.status,
                response_time_ms=m.response_time_ms,
                additional_data=m.additional_data
            )
            for m in metrics
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metrics for job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")

@router.get("/{job_id}/runs", response_model=List[JobRunResponse])
async def get_job_runs(
    job_id: str,
    request,
    limit: int = Query(100, le=1000)
):
    """
    Get job execution history

    Args:
        job_id: Unique identifier for the job
        limit: Maximum number of runs to return
    """
    try:
        config = request.app.state.config
        db = request.app.state.db

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Get job runs from database
        runs = await db.get_job_runs(job_id=job_id, limit=limit)

        # Convert to response format
        return [
            JobRunResponse(
                id=r.id,
                job_id=r.job_id,
                start_time=r.start_time,
                end_time=r.end_time,
                status=r.status,
                total_destinations=r.total_destinations,
                successful_destinations=r.successful_destinations,
                failed_destinations=r.failed_destinations,
                error_message=r.error_message
            )
            for r in runs
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get runs for job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job runs")

@router.post("/{job_id}/start")
async def start_job(job_id: str, request):
    """
    Start a job execution

    Args:
        job_id: Unique identifier for the job
    """
    try:
        config = request.app.state.config
        db = request.app.state.db
        job_manager = request.app.state.job_manager

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Get job record from database
        job_record = await db.get_job_by_name(job_id)
        if not job_record:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found in database")

        # Get job configuration
        job_config = config.get_job(job_id)

        # Start the job
        success = await job_manager.start_job(job_record.id, job_config)
        if success:
            return {"message": f"Job '{job_id}' started successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to start job")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to start job")

@router.post("/{job_id}/stop")
async def stop_job(job_id: str, request):
    """
    Stop a running job

    Args:
        job_id: Unique identifier for the job
    """
    try:
        config = request.app.state.config
        db = request.app.state.db
        job_manager = request.app.state.job_manager

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # Get job record from database
        job_record = await db.get_job_by_name(job_id)
        if not job_record:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found in database")

        # Stop the job
        success = await job_manager.stop_job(job_record.id)
        if success:
            return {"message": f"Job '{job_id}' stopped successfully"}
        else:
            return {"message": f"Job '{job_id}' was not running"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to stop job")

@router.get("/{job_id}/export")
async def export_job_data(
    job_id: str,
    request,
    format: str = Query("xlsx", regex="^(xlsx|csv)$"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None)
):
    """
    Export job data to Excel or CSV format

    Args:
        job_id: Unique identifier for the job
        format: Export format (xlsx or csv)
        start_time: Filter by start time
        end_time: Filter by end time
    """
    try:
        config = request.app.state.config
        db = request.app.state.db

        # Check if job exists
        if not config.get_job(job_id):
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        # TODO: Implement export functionality
        # export_service = ExportService(db)
        # file_data, filename = await export_service.export_job_metrics(
        #     job_id, format, start_time, end_time
        # )

        # For now, return placeholder
        raise HTTPException(status_code=501, detail="Export functionality not yet implemented")

        # return StreamingResponse(
        #     io.BytesIO(file_data),
        #     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        #     headers={"Content-Disposition": f"attachment; filename={filename}"}
        # )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export data for job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail="Failed to export job data")