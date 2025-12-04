#!/usr/bin/env python3
"""
Network Stats Collector - Main Application Entry Point

A Windows-based network monitoring tool that collects latency information
and exports data to Excel files for network administrators.
"""

import asyncio
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routes import jobs, dashboard, destinations
from src.core.config import Config
from src.core.database import Database
from src.services.destination_manager import DestinationManager
from src.services.job_manager import JobManager
from src.services.scheduler import Scheduler
from src.utils.logging import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Network Stats Collector",
    description="A Windows-based network monitoring tool that collects latency information and exports data to Excel files",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="web/templates")

# Include API routes
app.include_router(destinations.router, prefix="/api/destinations", tags=["destinations"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])

@app.on_event("startup")
async def startup_event():
    """Initialize application components"""
    logger.info("Starting Network Stats Collector...")

    # Load configuration
    config_path = Path("config/app.yaml")
    if not config_path.exists():
        config_path = Path("config/app.yaml.example")

    config = Config(config_path)
    logger.info(f"Configuration loaded from {config.config_path}")

    # Initialize database
    db = Database(config.database_url)
    await db.initialize()
    logger.info("Database initialized")

    # Initialize destination manager
    destination_manager = DestinationManager(config, db)
    await destination_manager.initialize()
    logger.info("Destination manager initialized")

    # Sync configuration with database
    await sync_configuration_with_database(config, db, destination_manager)
    logger.info("Configuration synced with database")

    # Initialize job manager
    job_manager = JobManager(db, destination_manager)
    logger.info("Job manager initialized")

    # Initialize scheduler
    scheduler = Scheduler(db, job_manager, destination_manager)
    await scheduler.start()
    await scheduler.schedule_all_jobs()
    logger.info("Scheduler initialized and jobs scheduled")

    # Store components in app state for access by routes
    app.state.config = config
    app.state.db = db
    app.state.destination_manager = destination_manager
    app.state.job_manager = job_manager
    app.state.scheduler = scheduler

    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup application components"""
    logger.info("Shutting down Network Stats Collector...")

    # Cleanup scheduler
    if hasattr(app.state, 'scheduler'):
        await app.state.scheduler.shutdown()

    # Cleanup destination manager
    if hasattr(app.state, 'destination_manager'):
        await app.state.destination_manager.cleanup()

    # Cleanup database connections
    if hasattr(app.state, 'db'):
        await app.state.db.cleanup()

    logger.info("Application shutdown complete")

@app.get("/")
async def root():
    """Root endpoint - redirect to dashboard"""
    return {
        "message": "Network Stats Collector API",
        "docs": "/docs",
        "redoc": "/redoc",
        "dashboard": "/dashboard"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "network-stats-collector"}

async def sync_configuration_with_database(config, db, destination_manager):
    """
    Sync configuration jobs and destinations with database

    This function ensures that:
    1. All destinations from job configurations exist in the database
    2. All jobs from configuration exist in the database with proper destination references
    """
    try:
        # Get all jobs from configuration
        jobs = config.get_all_jobs()

        # Collect all unique destinations from all jobs
        all_destinations = set()
        for job_config in jobs.values():
            for dest_config in job_config.destinations:
                all_destinations.add((dest_config.host, dest_config.display_name))

        # Ensure all destinations exist in database
        for host, display_name in all_destinations:
            destination = await destination_manager.get_destination_by_host(host)
            if not destination:
                # Create destination in database
                await destination_manager.add_destination(
                    host=host,
                    display_name=display_name,
                    tags=["config_import"],
                    description=f"Auto-imported from job configuration"
                )
                logger.info(f"Created destination in database: {host} ({display_name})")

        # Sync jobs with database
        for job_name, job_config in jobs.items():
            # Check if job exists in database
            job_record = await db.get_job_by_name(job_name)

            if not job_record:
                # Create new job in database
                destination_ids = []
                for dest_config in job_config.destinations:
                    destination = await destination_manager.get_destination_by_host(dest_config.host)
                    if destination:
                        destination_ids.append(destination['id'])

                if destination_ids:
                    await db.create_job(
                        name=job_name,
                        interval=job_config.interval,
                        enabled=job_config.enabled,
                        metrics=job_config.metrics,
                        destination_ids=destination_ids
                    )
                    logger.info(f"Created job in database: {job_name}")
                else:
                    logger.warning(f"Could not create job {job_name}: no valid destinations found")

        logger.info(f"Synced {len(jobs)} jobs and {len(all_destinations)} destinations with database")

    except Exception as e:
        logger.error(f"Failed to sync configuration with database: {e}")
        raise

def main():
    """Main entry point for the application"""
    import argparse

    parser = argparse.ArgumentParser(description="Network Stats Collector")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to (default: 8080)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--config", default="config/app.yaml", help="Path to configuration file")

    args = parser.parse_args()

    # Store config path in app state
    app.state.config_path = Path(args.config)

    # Configure uvicorn
    uvicorn_config = {
        "app": app,
        "host": args.host,
        "port": args.port,
        "log_level": "debug" if args.debug else "info",
        "reload": args.debug,
    }

    logger.info(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(**uvicorn_config)

if __name__ == "__main__":
    main()