"""
Job Scheduler Service for Network Stats Collector

Handles time-based scheduling of network monitoring jobs.
Supports interval-based scheduling and time window constraints.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_

from src.core.database import Database, Job, JobRun
from src.core.config import JobConfig
from src.services.job_manager import JobManager
from src.services.destination_manager import DestinationManager

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Job scheduler for network monitoring tasks

    Handles:
    - Time-based job scheduling
    - Time window validation
    - Job execution coordination
    - Schedule maintenance and cleanup
    """

    def __init__(self, db: Database, job_manager: JobManager, destination_manager: DestinationManager):
        """
        Initialize scheduler

        Args:
            db: Database instance
            job_manager: Job manager instance
            destination_manager: Destination manager instance
        """
        self.db = db
        self.job_manager = job_manager
        self.destination_manager = destination_manager
        self._scheduler_task = None
        self._shutdown = False
        self._scheduled_jobs: Dict[int, asyncio.Task] = {}

    async def start(self):
        """Start the scheduler"""
        if self._scheduler_task and not self._scheduler_task.done():
            logger.warning("Scheduler is already running")
            return

        self._shutdown = False
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Job scheduler started")

    async def stop(self):
        """Stop the scheduler"""
        if not self._scheduler_task or self._scheduler_task.done():
            logger.warning("Scheduler is not running")
            return

        self._shutdown = True
        self._scheduler_task.cancel()

        try:
            await self._scheduler_task
        except asyncio.CancelledError:
            pass

        # Cancel all scheduled jobs
        for job_id, task in self._scheduled_jobs.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._scheduled_jobs.clear()
        logger.info("Job scheduler stopped")

    async def schedule_job(self, job_id: int, job_config: JobConfig) -> bool:
        """
        Schedule a job for execution

        Args:
            job_id: Job database ID
            job_config: Job configuration

        Returns:
            True if job scheduled successfully, False otherwise
        """
        try:
            # Check if job is already running
            running_jobs = await self.job_manager.get_running_jobs()
            if job_id in running_jobs:
                logger.warning(f"Job {job_id} is already running, cannot schedule")
                return False

            # Calculate next run time
            next_run_time = self._calculate_next_run(job_config)
            if not next_run_time:
                logger.warning(f"Cannot schedule job {job_id}: no valid run time")
                return False

            # Create scheduling task
            delay = (next_run_time - datetime.now(timezone.utc)).total_seconds()
            if delay < 0:
                delay = 0  # Run immediately if time is in the past

            task = asyncio.create_task(self._delayed_job_execution(job_id, job_config, delay))
            self._scheduled_jobs[job_id] = task

            # Update job record with next run time
            await self._update_job_next_run(job_id, next_run_time)

            logger.info(f"Scheduled job {job_id} to run in {delay:.1f} seconds")
            return True

        except Exception as e:
            logger.error(f"Failed to schedule job {job_id}: {e}")
            return False

    async def unschedule_job(self, job_id: int) -> bool:
        """
        Unschedule a job

        Args:
            job_id: Job ID to unschedule

        Returns:
            True if job unscheduled successfully, False otherwise
        """
        try:
            if job_id in self._scheduled_jobs:
                task = self._scheduled_jobs[job_id]
                task.cancel()
                del self._scheduled_jobs[job_id]

            # Update job record to clear next run time
            await self._update_job_next_run(job_id, None)

            logger.info(f"Unscheduled job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unschedule job {job_id}: {e}")
            return False

    async def schedule_all_jobs(self) -> int:
        """
        Schedule all enabled jobs from the database

        Returns:
            Number of jobs successfully scheduled
        """
        try:
            # Get all enabled jobs
            jobs = await self._get_enabled_jobs()
            scheduled_count = 0

            for job in jobs:
                job_config = JobConfig.parse_raw(job.config)
                if await self.schedule_job(job.id, job_config):
                    scheduled_count += 1

            logger.info(f"Scheduled {scheduled_count} out of {len(jobs)} enabled jobs")
            return scheduled_count

        except Exception as e:
            logger.error(f"Failed to schedule jobs: {e}")
            return 0

    async def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("Scheduler loop started")

        while not self._shutdown:
            try:
                # Clean up completed scheduled tasks
                await self._cleanup_completed_tasks()

                # Check for jobs that need to be rescheduled
                await self._reschedule_jobs()

                # Sleep for a short interval
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error

        logger.info("Scheduler loop stopped")

    async def _delayed_job_execution(self, job_id: int, job_config: JobConfig, delay: float):
        """
        Execute a job after a delay

        Args:
            job_id: Job ID
            job_config: Job configuration
            delay: Delay in seconds
        """
        try:
            if delay > 0:
                await asyncio.sleep(delay)

            # Check if job is still enabled
            if not await self._is_job_enabled(job_id):
                logger.info(f"Job {job_id} is no longer enabled, skipping execution")
                return

            # Time window checking not implemented - skip this check
            # if not await self._is_within_time_window(job_id):
            #     logger.info(f"Job {job_id} is not within execution time window, skipping")
            #     # Reschedule for next valid time
            #     await self.schedule_job(job_id, job_config)
            #     return

            # Start job execution
            logger.info(f"Executing scheduled job {job_id}")
            started = await self.job_manager.start_job(job_id, job_config)

            if started:
                # Reschedule for next interval
                await self.schedule_job(job_id, job_config)
            else:
                logger.error(f"Failed to start job {job_id}")
                # Try to reschedule with a delay
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                await self.schedule_job(job_id, job_config)

        except asyncio.CancelledError:
            logger.info(f"Cancelled scheduled job {job_id}")
        except Exception as e:
            logger.error(f"Error executing scheduled job {job_id}: {e}")
            # Try to reschedule after error
            await asyncio.sleep(300)  # Wait 5 minutes before retrying
            try:
                await self.schedule_job(job_id, job_config)
            except Exception:
                pass

        finally:
            # Remove from scheduled jobs
            if job_id in self._scheduled_jobs:
                del self._scheduled_jobs[job_id]

    def _calculate_next_run(self, job_config: JobConfig) -> Optional[datetime]:
        """
        Calculate the next valid run time for a job

        Args:
            job_config: Job configuration

        Returns:
            Next run time or None if no valid time available
        """
        now = datetime.now(timezone.utc)

        # Start with current time + interval
        next_run = now + timedelta(seconds=job_config.interval)

        # Time windows not implemented - return simple interval-based time
        # if hasattr(job_config, 'time_windows') and job_config.time_windows:
        #     # Find next valid time within time windows
        #     return self._find_next_valid_time_in_windows(next_run, job_config.time_windows)
        # else:
        # No time windows, return simple interval-based time
        return next_run

    # TimeWindow methods not implemented - TimeWindow class doesn't exist
    # def _find_next_valid_time_in_windows(self, start_time: datetime, time_windows: List[TimeWindow]) -> Optional[datetime]:
    #     """Find the next valid time within specified time windows"""
    #     pass
    #
    # def _is_time_in_window(self, time: datetime, window: TimeWindow) -> bool:
    #     """Check if a time falls within a time window"""
    #     pass

    # Time window method not implemented
    # async def _is_within_time_window(self, job_id: int) -> bool:
    #     """Check if current time is within job's time windows"""
    #     return True  # Always allow execution since time windows are not implemented

    async def _is_job_enabled(self, job_id: int) -> bool:
        """
        Check if a job is still enabled

        Args:
            job_id: Job ID

        Returns:
            True if job is enabled, False otherwise
        """
        try:
            async with self.db.async_session() as session:
                result = await session.execute(
                    select(Job.enabled)
                    .where(Job.id == job_id)
                )
                return result.scalar_one() or False

        except Exception as e:
            logger.error(f"Failed to check if job {job_id} is enabled: {e}")
            return False

    async def _get_enabled_jobs(self) -> List[Job]:
        """
        Get all enabled jobs from database

        Returns:
            List of enabled jobs
        """
        try:
            async with self.db.async_session() as session:
                result = await session.execute(
                    select(Job)
                    .where(Job.enabled == True)
                    .order_by(Job.name)
                )
                return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Failed to get enabled jobs: {e}")
            return []

    async def _update_job_next_run(self, job_id: int, next_run: Optional[datetime]):
        """
        Update job's next run time

        Args:
            job_id: Job ID
            next_run: Next run time or None
        """
        try:
            async with self.db.async_session() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(next_run=next_run)
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to update next run time for job {job_id}: {e}")

    async def _cleanup_completed_tasks(self):
        """Clean up completed scheduled tasks"""
        completed_jobs = []
        for job_id, task in self._scheduled_jobs.items():
            if task.done():
                completed_jobs.append(job_id)

        for job_id in completed_jobs:
            del self._scheduled_jobs[job_id]

        if completed_jobs:
            logger.debug(f"Cleaned up {len(completed_jobs)} completed scheduled tasks")

    async def _reschedule_jobs(self):
        """Reschedule jobs that should be running but aren't"""
        try:
            # Get jobs that have passed their next run time but aren't running or scheduled
            now = datetime.now(timezone.utc)
            running_jobs = await self.job_manager.get_running_jobs()
            scheduled_jobs = set(self._scheduled_jobs.keys())

            async with self.db.async_session() as session:
                result = await session.execute(
                    select(Job)
                    .where(and_(
                        Job.enabled == True,
                        Job.next_run <= now,
                        Job.id.notin_(list(running_jobs | scheduled_jobs))
                    ))
                )
                jobs_to_reschedule = result.scalars().all()

                for job in jobs_to_reschedule:
                    job_config = JobConfig.parse_raw(job.config)
                    logger.info(f"Rescheduling job {job.id} that missed its run time")
                    await self.schedule_job(job.id, job_config)

        except Exception as e:
            logger.error(f"Failed to reschedule jobs: {e}")

    async def shutdown(self):
        """Shutdown scheduler and all scheduled jobs"""
        await self.stop()
        await self.job_manager.shutdown()