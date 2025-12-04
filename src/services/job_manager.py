"""
Job Manager Service for Network Stats Collector

Handles job execution, scheduling, and lifecycle management.
Coordinates with collectors and manages metric collection workflows.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from src.core.database import Database, Job, JobRun, MetricRecord, Destination
from src.core.config import JobConfig, DestinationConfig
from src.collectors.ping_collector import PingCollector
from src.services.destination_manager import DestinationManager

logger = logging.getLogger(__name__)


class JobExecutionResult:
    """Result of a job execution"""

    def __init__(self, job_id: int, success: bool, metrics_collected: int = 0,
                 destinations_successful: int = 0, destinations_failed: int = 0,
                 error_message: Optional[str] = None):
        self.job_id = job_id
        self.success = success
        self.metrics_collected = metrics_collected
        self.destinations_successful = destinations_successful
        self.destinations_failed = destinations_failed
        self.error_message = error_message
        self.end_time = datetime.now(timezone.utc)


class JobManager:
    """
    Job execution manager

    Handles the execution of network monitoring jobs, including:
    - Job lifecycle management
    - Metric collection coordination
    - Error handling and recovery
    - Status tracking and reporting
    """

    def __init__(self, db: Database, destination_manager: DestinationManager):
        """
        Initialize job manager

        Args:
            db: Database instance
            destination_manager: Destination manager instance
        """
        self.db = db
        self.destination_manager = destination_manager
        self.ping_collector = PingCollector()
        self._running_jobs: Dict[int, asyncio.Task] = {}
        self._shutdown = False

    async def start_job(self, job_id: int, job_config: JobConfig) -> bool:
        """
        Start a job execution

        Args:
            job_id: Database ID of the job
            job_config: Job configuration

        Returns:
            True if job started successfully, False otherwise
        """
        try:
            if job_id in self._running_jobs:
                logger.warning(f"Job {job_id} is already running")
                return False

            # Create job run record
            run_id = await self._create_job_run(job_id, len(job_config.destinations))
            if not run_id:
                return False

            # Start job execution task
            task = asyncio.create_task(
                self._execute_job(job_id, job_config, run_id)
            )
            self._running_jobs[job_id] = task

            logger.info(f"Started job {job_id} (run {run_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {e}")
            return False

    async def stop_job(self, job_id: int) -> bool:
        """
        Stop a running job

        Args:
            job_id: Job ID to stop

        Returns:
            True if job stopped successfully, False otherwise
        """
        try:
            if job_id not in self._running_jobs:
                logger.warning(f"Job {job_id} is not running")
                return False

            # Cancel the job task
            task = self._running_jobs[job_id]
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Remove from running jobs
            del self._running_jobs[job_id]

            # Update job status in database
            await self._update_job_status(job_id, False)

            logger.info(f"Stopped job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop job {job_id}: {e}")
            return False

    async def get_job_status(self, job_id: int) -> Optional[str]:
        """
        Get the current status of a job

        Args:
            job_id: Job ID to check

        Returns:
            Job status string or None if job not found
        """
        try:
            async with self.db.async_session() as session:
                result = await session.execute(
                    select(Job.enabled, Job.last_run, Job.next_run)
                    .where(Job.id == job_id)
                )
                row = result.first()

                if not row:
                    return None

                is_enabled = row.enabled
                is_running = job_id in self._running_jobs
                last_run = row.last_run
                next_run = row.next_run

                if is_running:
                    return "running"
                elif is_enabled and next_run and next_run > datetime.now(timezone.utc):
                    return "scheduled"
                elif is_enabled:
                    return "ready"
                else:
                    return "disabled"

        except Exception as e:
            logger.error(f"Failed to get status for job {job_id}: {e}")
            return None

    async def get_running_jobs(self) -> Set[int]:
        """
        Get set of currently running job IDs

        Returns:
            Set of running job IDs
        """
        return set(self._running_jobs.keys())

    async def shutdown(self):
        """Shutdown job manager and stop all running jobs"""
        logger.info("Shutting down job manager...")
        self._shutdown = True

        # Cancel all running jobs
        jobs_to_stop = list(self._running_jobs.keys())
        for job_id in jobs_to_stop:
            await self.stop_job(job_id)

        logger.info("Job manager shutdown complete")

    async def _execute_job(self, job_id: int, job_config: JobConfig, run_id: int):
        """
        Execute a job and collect metrics

        Args:
            job_id: Job ID
            job_config: Job configuration
            run_id: Job run ID
        """
        start_time = datetime.now(timezone.utc)
        metrics_collected = 0
        destinations_successful = 0
        destinations_failed = 0
        error_message = None

        try:
            logger.info(f"Executing job {job_id} with {len(job_config.destinations)} destinations")

            # Collect metrics for each destination
            for destination_config in job_config.destinations:
                try:
                    # Get destination ID from host
                    destination = await self.destination_manager.get_destination_by_host(destination_config.host)
                    if not destination:
                        logger.warning(f"Destination not found for host: {destination_config.host}")
                        destinations_failed += 1
                        continue

                    destination_id = destination['id']

                    # Collect configured metrics
                    for metric_type in job_config.metrics:
                        if metric_type == "ping":
                            await self._collect_ping_metric(
                                job_id, destination_id, destination_config, run_id
                            )
                            metrics_collected += 1
                        else:
                            logger.warning(f"Metric type '{metric_type}' not yet implemented")

                    destinations_successful += 1

                except Exception as e:
                    logger.error(f"Failed to collect metrics for {destination_config.host}: {e}")
                    destinations_failed += 1

            # Create execution result
            result = JobExecutionResult(
                job_id=job_id,
                success=(destinations_failed == 0),
                metrics_collected=metrics_collected,
                destinations_successful=destinations_successful,
                destinations_failed=destinations_failed,
                error_message=error_message
            )

            # Update job run record
            await self._complete_job_run(run_id, result)

            # Update job status and next run time
            await self._update_job_after_run(job_id, job_config.interval, result)

            logger.info(f"Job {job_id} completed: {metrics_collected} metrics collected")

        except Exception as e:
            logger.error(f"Job {job_id} execution failed: {e}")
            error_message = str(e)

            # Update with failure result
            result = JobExecutionResult(
                job_id=job_id,
                success=False,
                metrics_collected=metrics_collected,
                destinations_successful=destinations_successful,
                destinations_failed=destinations_failed,
                error_message=error_message
            )

            await self._complete_job_run(run_id, result)

        finally:
            # Remove from running jobs
            if job_id in self._running_jobs:
                del self._running_jobs[job_id]

    async def _collect_ping_metric(self, job_id: int, destination_id: int,
                                 destination_config: DestinationConfig, run_id: int):
        """
        Collect ping metric for a destination

        Args:
            job_id: Job ID
            destination_id: Destination ID
            destination_config: Destination configuration
            run_id: Job run ID
        """
        try:
            # Perform ping test
            ping_result = await self.ping_collector.ping_host(
                destination_config.host,
                count=4,
                timeout=5
            )

            # Store metric in database
            metric = MetricRecord(
                job_id=job_id,
                destination_id=destination_id,
                metric_type="ping",
                value=ping_result['latency_ms'],
                unit="ms",
                status="success" if ping_result['success'] else "failed",
                timestamp=datetime.now(timezone.utc),
                metadata={
                    'run_id': run_id,
                    'packet_loss': ping_result.get('packet_loss', 0),
                    'jitter': ping_result.get('jitter_ms', 0),
                    'min_latency': ping_result.get('min_latency_ms'),
                    'max_latency': ping_result.get('max_latency_ms')
                }
            )

            async with self.db.async_session() as session:
                session.add(metric)
                await session.commit()

            logger.debug(f"Stored ping metric for {destination_config.host}: {ping_result['latency_ms']}ms")

        except Exception as e:
            logger.error(f"Failed to collect ping metric for {destination_config.host}: {e}")

            # Store failed metric
            metric = MetricRecord(
                job_id=job_id,
                destination_id=destination_id,
                metric_type="ping",
                value=0,
                unit="ms",
                status="failed",
                timestamp=datetime.now(timezone.utc),
                metadata={
                    'run_id': run_id,
                    'error': str(e)
                }
            )

            async with self.db.async_session() as session:
                session.add(metric)
                await session.commit()

    async def _create_job_run(self, job_id: int, total_destinations: int) -> Optional[int]:
        """
        Create a job run record

        Args:
            job_id: Job ID
            total_destinations: Number of destinations to monitor

        Returns:
            Run ID if created successfully, None otherwise
        """
        try:
            async with self.db.async_session() as session:
                run = JobRun(
                    job_id=job_id,
                    start_time=datetime.now(timezone.utc),
                    status="running",
                    total_destinations=total_destinations,
                    successful_destinations=0,
                    failed_destinations=0
                )

                session.add(run)
                await session.commit()
                await session.refresh(run)

                return run.id

        except Exception as e:
            logger.error(f"Failed to create job run for job {job_id}: {e}")
            return None

    async def _complete_job_run(self, run_id: int, result: JobExecutionResult):
        """
        Complete a job run record

        Args:
            run_id: Run ID
            result: Execution result
        """
        try:
            async with self.db.async_session() as session:
                await session.execute(
                    update(JobRun)
                    .where(JobRun.id == run_id)
                    .values(
                        end_time=result.end_time,
                        status="completed" if result.success else "failed",
                        successful_destinations=result.destinations_successful,
                        failed_destinations=result.destinations_failed,
                        error_message=result.error_message
                    )
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to complete job run {run_id}: {e}")

    async def _update_job_status(self, job_id: int, enabled: bool):
        """
        Update job enabled status

        Args:
            job_id: Job ID
            enabled: Whether job is enabled
        """
        try:
            async with self.db.async_session() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(enabled=enabled)
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")

    async def _update_job_after_run(self, job_id: int, interval: int, result: JobExecutionResult):
        """
        Update job information after a run

        Args:
            job_id: Job ID
            interval: Job interval in seconds
            result: Execution result
        """
        try:
            next_run = datetime.now(timezone.utc)
            if result.success:
                # Schedule next run based on interval
                from datetime import timedelta
                next_run += timedelta(seconds=interval)

            async with self.db.async_session() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(
                        last_run=result.end_time,
                        next_run=next_run,
                        enabled=result.success  # Disable job if it failed
                    )
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to update job {job_id} after run: {e}")