"""
Database layer for Network Stats Collector

Handles time-series data storage and retrieval using SQLAlchemy with SQLite.
Optimized for network metrics storage and fast querying.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal

import aiosqlite
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Float, Boolean,
    Index, create_engine, MetaData, Table, select, insert, update, delete,
    ForeignKey
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# Base class for ORM models
Base = declarative_base()

class Destination(Base):
    """Global destination configuration"""
    __tablename__ = "destinations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # Unique destination name
    host = Column(String(255), nullable=False, index=True)  # IP address or hostname
    display_name = Column(String(255), nullable=False)  # Human-readable display name
    description = Column(Text, nullable=True)  # Optional description
    tags = Column(Text, nullable=True)  # JSON array of tags
    status = Column(String(20), nullable=False, default="active", index=True)  # active, inactive, error
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, nullable=True)  # Last time destination was reachable

    # Indexes for common queries
    __table_args__ = (
        Index('idx_host_status', 'host', 'status'),
        Index('idx_name_active', 'name', 'status'),
    )

class Job(Base):
    """Job configuration with destination references"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    interval = Column(Integer, nullable=False)  # Collection interval in seconds
    metrics = Column(Text, nullable=False)  # JSON array of metric types
    destination_ids = Column(Text, nullable=False)  # JSON array of destination IDs

    # Scheduling fields for time windows
    start_time = Column(DateTime, nullable=True)  # Job execution start time
    end_time = Column(DateTime, nullable=True)  # Job execution end time (optional)

    # Status tracking
    status = Column(String(20), nullable=False, default="stopped", index=True)  # running, stopped, scheduled, error
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    tags = Column(Text, nullable=True)  # JSON array of tags
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes for common queries
    __table_args__ = (
        Index('idx_name_enabled', 'name', 'enabled'),
        Index('idx_status_scheduled', 'status', 'next_run'),
        Index('idx_active_jobs', 'enabled', 'status'),
    )

class MetricRecord(Base):
    """Time-series metric record"""
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    job_id = Column(Integer, nullable=False, index=True)  # Foreign key reference to jobs.id
    destination_id = Column(Integer, nullable=False, index=True)  # Foreign key reference to destinations.id
    host = Column(String(255), nullable=False, index=True)  # Denormalized for query performance
    metric_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # success, failure, timeout
    response_time_ms = Column(Float, nullable=True)  # Response time in milliseconds
    additional_data = Column(Text, nullable=True)  # JSON string for metric-specific data
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_job_destination_timestamp', 'job_id', 'destination_id', 'timestamp'),
        Index('idx_job_host_timestamp', 'job_id', 'host', 'timestamp'),
        Index('idx_metric_type_timestamp', 'metric_type', 'timestamp'),
        Index('idx_status_timestamp', 'status', 'timestamp'),
        Index('idx_destination_metrics', 'destination_id', 'timestamp'),
    )

class JobRun(Base):
    """Job execution run tracking"""
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False, index=True)  # Foreign key reference to jobs.id
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running, completed, failed
    total_destinations = Column(Integer, nullable=False)  # Renamed from total_hosts for clarity
    successful_destinations = Column(Integer, default=0)  # Renamed from successful_hosts
    failed_destinations = Column(Integer, default=0)  # Renamed from failed_hosts
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Indexes for common queries
    __table_args__ = (
        Index('idx_job_status_time', 'job_id', 'status', 'start_time'),
    )

class Database:
    """Database manager for network stats collector"""

    def __init__(self, database_url: str):
        """
        Initialize database manager

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.engine = None
        self.async_session_maker = None
        self._initialized = False

    async def initialize(self):
        """Initialize database connection and create tables"""
        try:
            # Create async engine with SQLite specific settings
            if self.database_url.startswith("sqlite"):
                # For SQLite, add connection pooling and other optimizations
                async_url = self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
                self.engine = create_async_engine(
                    async_url,
                    poolclass=StaticPool,
                    connect_args={
                        "check_same_thread": False,
                        "timeout": 20,
                    },
                    echo=False,  # Set to True for SQL debugging
                )
            else:
                # For other databases
                async_url = self.database_url
                self.engine = create_async_engine(async_url, echo=False)

            # Create session factory
            self.async_session_maker = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            self._initialized = True
            logger.info(f"Database initialized: {self.database_url}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def cleanup(self):
        """Cleanup database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections cleaned up")

    def _ensure_initialized(self):
        """Ensure database is initialized"""
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")

    # Destination Management Methods
    async def create_destination(self, destination_data: Dict[str, Any]) -> int:
        """Create a new destination"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                stmt = insert(Destination).values(**destination_data)
                result = await session.execute(stmt)
                await session.commit()
                return result.inserted_primary_key[0]
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create destination: {e}")
                raise

    async def get_destinations(self, active_only: bool = True) -> List[Destination]:
        """Get all destinations"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                query = select(Destination)
                if active_only:
                    query = query.where(Destination.status == "active")
                query = query.order_by(Destination.display_name)

                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Failed to get destinations: {e}")
                raise

    async def get_destination(self, destination_id: int) -> Optional[Destination]:
        """Get a specific destination by ID"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                query = select(Destination).where(Destination.id == destination_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to get destination {destination_id}: {e}")
                raise

    async def update_destination(self, destination_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a destination"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                update_data['updated_at'] = datetime.now(timezone.utc)
                stmt = update(Destination).where(Destination.id == destination_id).values(**update_data)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update destination {destination_id}: {e}")
                raise

    async def delete_destination(self, destination_id: int) -> bool:
        """Delete a destination"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                stmt = delete(Destination).where(Destination.id == destination_id)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete destination {destination_id}: {e}")
                raise

    # Job Management Methods
    async def create_job(self, job_data: Dict[str, Any]) -> int:
        """Create a new job"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                stmt = insert(Job).values(**job_data)
                result = await session.execute(stmt)
                await session.commit()
                return result.inserted_primary_key[0]
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create job: {e}")
                raise

    async def get_jobs(self, enabled_only: bool = False) -> List[Job]:
        """Get all jobs"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                query = select(Job)
                if enabled_only:
                    query = query.where(Job.enabled == True)
                query = query.order_by(Job.name)

                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Failed to get jobs: {e}")
                raise

    async def get_job(self, job_id: int) -> Optional[Job]:
        """Get a specific job by ID"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                query = select(Job).where(Job.id == job_id)
                result = await session.execute(query)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to get job {job_id}: {e}")
                raise

    async def update_job(self, job_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a job"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                update_data['updated_at'] = datetime.now(timezone.utc)
                stmt = update(Job).where(Job.id == job_id).values(**update_data)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update job {job_id}: {e}")
                raise

    async def delete_job(self, job_id: int) -> bool:
        """Delete a job"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                stmt = delete(Job).where(Job.id == job_id)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete job {job_id}: {e}")
                raise

    # Metric Management Methods (Updated for new schema)
    async def store_metric(self, metric_data: Dict[str, Any]) -> int:
        """Store a single metric record"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                stmt = insert(MetricRecord).values(**metric_data)
                result = await session.execute(stmt)
                await session.commit()
                return result.inserted_primary_key[0]
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to store metric: {e}")
                raise

    async def store_metrics_batch(self, metrics_data: List[Dict[str, Any]]) -> List[int]:
        """Store multiple metric records in a batch"""
        self._ensure_initialized()

        if not metrics_data:
            return []

        async with self.async_session_maker() as session:
            try:
                stmt = insert(MetricRecord).return_values(MetricRecord.id)
                result = await session.execute(stmt, metrics_data)
                await session.commit()
                return [row[0] for row in result.fetchall()]
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to store metrics batch: {e}")
                raise

    async def get_metrics(self,
                         job_id: Optional[int] = None,
                         destination_id: Optional[int] = None,
                         host: Optional[str] = None,
                         metric_type: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         limit: Optional[int] = None) -> List[MetricRecord]:
        """Get metrics with filtering options"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                query = select(MetricRecord)

                # Apply filters
                if job_id:
                    query = query.where(MetricRecord.job_id == job_id)
                if destination_id:
                    query = query.where(MetricRecord.destination_id == destination_id)
                if host:
                    query = query.where(MetricRecord.host == host)
                if metric_type:
                    query = query.where(MetricRecord.metric_type == metric_type)
                if start_time:
                    query = query.where(MetricRecord.timestamp >= start_time)
                if end_time:
                    query = query.where(MetricRecord.timestamp <= end_time)

                # Order by timestamp descending
                query = query.order_by(MetricRecord.timestamp.desc())

                # Apply limit
                if limit:
                    query = query.limit(limit)

                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Failed to get metrics: {e}")
                raise

    async def create_job_run(self, job_id: int, total_destinations: int) -> int:
        """Create a new job run record"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                run_data = {
                    'job_id': job_id,
                    'start_time': datetime.now(timezone.utc),
                    'total_destinations': total_destinations,
                    'status': 'running'
                }
                stmt = insert(JobRun).values(**run_data).return_values(JobRun.id)
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create job run: {e}")
                raise

    async def update_job_run(self,
                           run_id: int,
                           status: str,
                           successful_destinations: Optional[int] = None,
                           failed_destinations: Optional[int] = None,
                           error_message: Optional[str] = None) -> bool:
        """Update job run status"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                update_data = {
                    'status': status,
                    'end_time': datetime.now(timezone.utc)
                }

                if successful_destinations is not None:
                    update_data['successful_destinations'] = successful_destinations
                if failed_destinations is not None:
                    update_data['failed_destinations'] = failed_destinations
                if error_message:
                    update_data['error_message'] = error_message

                stmt = update(JobRun).where(JobRun.id == run_id).values(**update_data)
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount > 0
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update job run: {e}")
                raise

    async def get_job_runs(self,
                          job_id: Optional[int] = None,
                          limit: int = 100) -> List[JobRun]:
        """Get job runs with filtering"""
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                query = select(JobRun)

                if job_id:
                    query = query.where(JobRun.job_id == job_id)

                query = query.order_by(JobRun.start_time.desc()).limit(limit)

                result = await session.execute(query)
                return result.scalars().all()
            except Exception as e:
                logger.error(f"Failed to get job runs: {e}")
                raise