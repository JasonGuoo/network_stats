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
    Index, create_engine, MetaData, Table, select, insert, update, delete
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# Base class for ORM models
Base = declarative_base()

class MetricRecord(Base):
    """Time-series metric record"""
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    job_id = Column(String(100), nullable=False, index=True)
    host = Column(String(255), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # success, failure, timeout
    response_time_ms = Column(Float, nullable=True)  # Response time in milliseconds
    additional_data = Column(Text, nullable=True)  # JSON string for metric-specific data
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_job_host_timestamp', 'job_id', 'host', 'timestamp'),
        Index('idx_metric_type_timestamp', 'metric_type', 'timestamp'),
        Index('idx_status_timestamp', 'status', 'timestamp'),
    )

class JobRun(Base):
    """Job execution run tracking"""
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running, completed, failed
    total_hosts = Column(Integer, nullable=False)
    successful_hosts = Column(Integer, default=0)
    failed_hosts = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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

    async def store_metric(self, metric_data: Dict[str, Any]) -> int:
        """
        Store a single metric record

        Args:
            metric_data: Dictionary containing metric information

        Returns:
            ID of the inserted record
        """
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
        """
        Store multiple metric records in a batch

        Args:
            metrics_data: List of metric dictionaries

        Returns:
            List of inserted record IDs
        """
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
                         job_id: Optional[str] = None,
                         host: Optional[str] = None,
                         metric_type: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         limit: Optional[int] = None) -> List[MetricRecord]:
        """
        Get metrics with filtering options

        Args:
            job_id: Filter by job ID
            host: Filter by host
            metric_type: Filter by metric type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Limit number of results

        Returns:
            List of metric records
        """
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                query = select(MetricRecord)

                # Apply filters
                if job_id:
                    query = query.where(MetricRecord.job_id == job_id)
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

    async def create_job_run(self, job_id: str, total_hosts: int) -> int:
        """
        Create a new job run record

        Args:
            job_id: Job identifier
            total_hosts: Number of hosts being monitored

        Returns:
            ID of the created job run
        """
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                run_data = {
                    'job_id': job_id,
                    'start_time': datetime.now(timezone.utc),
                    'total_hosts': total_hosts,
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
                           successful_hosts: Optional[int] = None,
                           failed_hosts: Optional[int] = None,
                           error_message: Optional[str] = None) -> bool:
        """
        Update job run status

        Args:
            run_id: Job run ID
            status: New status
            successful_hosts: Number of successful hosts
            failed_hosts: Number of failed hosts
            error_message: Error message if failed

        Returns:
            True if update successful
        """
        self._ensure_initialized()

        async with self.async_session_maker() as session:
            try:
                update_data = {
                    'status': status,
                    'end_time': datetime.now(timezone.utc)
                }

                if successful_hosts is not None:
                    update_data['successful_hosts'] = successful_hosts
                if failed_hosts is not None:
                    update_data['failed_hosts'] = failed_hosts
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
                          job_id: Optional[str] = None,
                          limit: int = 100) -> List[JobRun]:
        """
        Get job runs with filtering

        Args:
            job_id: Filter by job ID
            limit: Maximum number of runs to return

        Returns:
            List of job runs
        """
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