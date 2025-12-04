"""
Destination Management Service

Provides business logic for managing global destinations including CRUD operations,
health monitoring, and validation.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.core.config import Config, DestinationConfig
from src.core.database import Database, Destination
from src.collectors.ping_collector import PingCollector

logger = logging.getLogger(__name__)

class DestinationManager:
    """Service for managing global destinations"""

    def __init__(self, config: Config, database: Database):
        """
        Initialize destination manager

        Args:
            config: Application configuration
            database: Database instance
        """
        self.config = config
        self.db = database
        self.ping_collector = PingCollector()
        self._monitoring_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the destination manager"""
        logger.info("Initializing Destination Manager")

        # Sync configuration with database
        await self._sync_config_with_database()

        # Start health monitoring
        await self._start_health_monitoring()

    async def cleanup(self):
        """Cleanup resources"""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Destination Manager cleaned up")

    async def _sync_config_with_database(self):
        """Synchronize configuration destinations with database"""
        try:
            # Get destinations from config
            config_destinations = self.config.get_all_destinations()

            # Get destinations from database
            db_destinations = await self.db.get_destinations(active_only=False)
            db_dest_map = {dest.name: dest for dest in db_destinations}

            # Add missing destinations to database
            for name, dest_config in config_destinations.items():
                if name not in db_dest_map:
                    await self._create_destination_in_db(dest_config)
                    logger.info(f"Added destination '{name}' to database from config")

            # Update database destinations with config changes
            for dest in db_destinations:
                if dest.name in config_destinations:
                    config_dest = config_destinations[dest.name]
                    if self._destination_changed(dest, config_dest):
                        await self._update_destination_in_db(dest.id, config_dest)
                        logger.info(f"Updated destination '{dest.name}' in database from config")

            logger.info(f"Database synchronized with {len(config_destinations)} destinations")

        except Exception as e:
            logger.error(f"Failed to sync config with database: {e}")

    def _destination_changed(self, db_dest: Destination, config_dest: DestinationConfig) -> bool:
        """Check if destination configuration has changed"""
        return (
            db_dest.host != config_dest.host or
            db_dest.display_name != config_dest.display_name or
            db_dest.description != config_dest.description or
            db_dest.status != config_dest.status
        )

    async def _create_destination_in_db(self, dest_config: DestinationConfig) -> int:
        """Create destination in database from config"""
        dest_data = {
            'name': dest_config.name,
            'host': dest_config.host,
            'display_name': dest_config.display_name,
            'description': dest_config.description,
            'tags': str(dest_config.tags),  # Convert to string for JSON storage
            'status': dest_config.status
        }
        return await self.db.create_destination(dest_data)

    async def _update_destination_in_db(self, dest_id: int, dest_config: DestinationConfig):
        """Update destination in database from config"""
        update_data = {
            'host': dest_config.host,
            'display_name': dest_config.display_name,
            'description': dest_config.description,
            'tags': str(dest_config.tags),  # Convert to string for JSON storage
            'status': dest_config.status
        }
        await self.db.update_destination(dest_id, update_data)

    async def _start_health_monitoring(self):
        """Start background health monitoring"""
        self._monitoring_task = asyncio.create_task(self._health_monitoring_loop())

    async def _health_monitoring_loop(self):
        """Background loop for monitoring destination health"""
        while True:
            try:
                await self._check_destination_health()
                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _check_destination_health(self):
        """Check health of all active destinations"""
        try:
            active_destinations = await self.db.get_destinations(active_only=True)

            for dest in active_destinations:
                try:
                    # Perform ping test
                    result = await self.ping_collector.ping_async(dest.host)

                    # Update last_seen if successful
                    if result['success']:
                        await self.db.update_destination(dest.id, {
                            'last_seen': datetime.now(timezone.utc),
                            'status': 'active'
                        })
                    else:
                        logger.warning(f"Ping failed for destination '{dest.name}': {result.get('error', 'Unknown error')}")

                except Exception as e:
                    logger.error(f"Error checking health for destination '{dest.name}': {e}")
                    # Mark as error if multiple consecutive failures
                    # This logic could be enhanced with failure counting

        except Exception as e:
            logger.error(f"Error in destination health check: {e}")

    # Destination CRUD Operations
    async def create_destination(self, destination: DestinationConfig) -> int:
        """
        Create a new destination

        Args:
            destination: Destination configuration

        Returns:
            Database ID of created destination
        """
        # Validate destination doesn't exist
        existing = await self._get_destination_by_name(destination.name)
        if existing:
            raise ValueError(f"Destination '{destination.name}' already exists")

        # Validate host format
        if not self._validate_host(destination.host):
            raise ValueError(f"Invalid host format: {destination.host}")

        # Create in database
        dest_data = {
            'name': destination.name,
            'host': destination.host,
            'display_name': destination.display_name,
            'description': destination.description,
            'tags': str(destination.tags),
            'status': destination.status
        }

        dest_id = await self.db.create_destination(dest_data)

        # Add to configuration
        if self.config.add_destination(destination):
            await self.config.save_config()

        logger.info(f"Created destination '{destination.name}' with ID {dest_id}")
        return dest_id

    async def get_destination(self, dest_id: int) -> Optional[Dict[str, Any]]:
        """
        Get destination by ID

        Args:
            dest_id: Destination ID

        Returns:
            Destination data or None if not found
        """
        dest = await self.db.get_destination(dest_id)
        if not dest:
            return None

        return self._destination_to_dict(dest)

    async def get_destination_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get destination by name

        Args:
            name: Destination name

        Returns:
            Destination data or None if not found
        """
        dest = await self._get_destination_by_name(name)
        if not dest:
            return None

        return self._destination_to_dict(dest)

    async def _get_destination_by_name(self, name: str) -> Optional[Destination]:
        """Get destination by name from database"""
        all_dests = await self.db.get_destinations(active_only=False)
        for dest in all_dests:
            if dest.name == name:
                return dest
        return None

    async def get_all_destinations(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all destinations

        Args:
            active_only: Only return active destinations

        Returns:
            List of destination dictionaries
        """
        destinations = await self.db.get_destinations(active_only=active_only)
        return [self._destination_to_dict(dest) for dest in destinations]

    async def update_destination(self, dest_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update destination

        Args:
            dest_id: Destination ID
            updates: Update data

        Returns:
            True if updated successfully
        """
        # Get existing destination
        existing = await self.db.get_destination(dest_id)
        if not existing:
            raise ValueError(f"Destination with ID {dest_id} not found")

        # Prepare update data
        update_data = {}

        if 'host' in updates:
            if not self._validate_host(updates['host']):
                raise ValueError(f"Invalid host format: {updates['host']}")
            update_data['host'] = updates['host']

        if 'display_name' in updates:
            update_data['display_name'] = updates['display_name']

        if 'description' in updates:
            update_data['description'] = updates.get('description')

        if 'tags' in updates:
            update_data['tags'] = str(updates['tags'])

        if 'status' in updates:
            if updates['status'] not in ['active', 'inactive', 'error']:
                raise ValueError(f"Invalid status: {updates['status']}")
            update_data['status'] = updates['status']

        # Update in database
        success = await self.db.update_destination(dest_id, update_data)

        if success:
            # Update in configuration
            updated_dest = await self.db.get_destination(dest_id)
            dest_config = DestinationConfig(
                name=updated_dest.name,
                host=updated_dest.host,
                display_name=updated_dest.display_name,
                description=updated_dest.description,
                tags=eval(updated_dest.tags) if updated_dest.tags else [],
                status=updated_dest.status
            )

            if self.config.update_destination(existing.name, dest_config):
                await self.config.save_config()

            logger.info(f"Updated destination '{existing.name}'")

        return success

    async def delete_destination(self, dest_id: int) -> bool:
        """
        Delete destination

        Args:
            dest_id: Destination ID

        Returns:
            True if deleted successfully
        """
        # Get destination
        dest = await self.db.get_destination(dest_id)
        if not dest:
            raise ValueError(f"Destination with ID {dest_id} not found")

        # Check if used by any jobs
        jobs = self.config.get_all_jobs()
        used_by_jobs = []
        for job_name, job_config in jobs.items():
            if dest.name in job_config.destinations:
                used_by_jobs.append(job_name)

        if used_by_jobs:
            raise ValueError(f"Cannot delete destination '{dest.name}' - used by jobs: {', '.join(used_by_jobs)}")

        # Delete from database
        success = await self.db.delete_destination(dest_id)

        if success:
            # Remove from configuration
            self.config.remove_destination(dest.name)
            await self.config.save_config()

            logger.info(f"Deleted destination '{dest.name}'")

        return success

    async def get_destination_status(self, dest_id: int) -> Dict[str, Any]:
        """
        Get detailed status information for a destination

        Args:
            dest_id: Destination ID

        Returns:
            Status information dictionary
        """
        dest = await self.db.get_destination(dest_id)
        if not dest:
            raise ValueError(f"Destination with ID {dest_id} not found")

        # Get recent metrics for this destination
        recent_metrics = await self.db.get_metrics(
            destination_id=dest_id,
            limit=100
        )

        # Calculate statistics
        total_checks = len(recent_metrics)
        successful_checks = len([m for m in recent_metrics if m.status == 'success'])
        success_rate = (successful_checks / total_checks * 100) if total_checks > 0 else 0

        # Calculate average response time for successful pings
        ping_metrics = [m for m in recent_metrics if m.metric_type == 'ping' and m.status == 'success']
        avg_response_time = sum(m.response_time_ms for m in ping_metrics) / len(ping_metrics) if ping_metrics else None

        # Count recent failures
        recent_failures = len([m for m in recent_metrics[:20] if m.status != 'success'])

        return {
            'id': dest.id,
            'name': dest.name,
            'host': dest.host,
            'status': dest.status,
            'last_seen': dest.last_seen.isoformat() if dest.last_seen else None,
            'last_check': recent_metrics[0].timestamp.isoformat() if recent_metrics else None,
            'last_ping': avg_response_time,
            'success_rate': round(success_rate, 2),
            'total_checks': total_checks,
            'recent_failures': recent_failures,
            'uptime_percentage': round(success_rate, 1)
        }

    async def search_destinations(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search destinations

        Args:
            query: Search query
            filters: Additional filters (status, tags, etc.)

        Returns:
            List of matching destinations
        """
        destinations = await self.db.get_destinations(active_only=False)

        # Apply filters
        if filters:
            if 'status' in filters:
                destinations = [d for d in destinations if d.status == filters['status']]
            if 'tags' in filters:
                required_tags = set(filters['tags'])
                destinations = [
                    d for d in destinations
                    if required_tags.issubset(set(eval(d.tags) if d.tags else []))
                ]

        # Apply search query
        if query:
            query = query.lower()
            matching_dests = []
            for dest in destinations:
                if (query in dest.name.lower() or
                    query in dest.display_name.lower() or
                    query in dest.host.lower() or
                    (dest.description and query in dest.description.lower())):
                    matching_dests.append(dest)
            destinations = matching_dests

        return [self._destination_to_dict(dest) for dest in destinations]

    def _validate_host(self, host: str) -> bool:
        """Validate host format (basic validation)"""
        if not host or len(host.strip()) == 0:
            return False

        # Basic validation - can be enhanced with regex
        host = host.strip()

        # Check for valid hostname or IP format
        # This is a basic check - can be enhanced
        return len(host) > 0 and not host.isspace()

    def _destination_to_dict(self, dest: Destination) -> Dict[str, Any]:
        """Convert destination object to dictionary"""
        return {
            'id': dest.id,
            'name': dest.name,
            'host': dest.host,
            'display_name': dest.display_name,
            'description': dest.description,
            'tags': eval(dest.tags) if dest.tags else [],
            'status': dest.status,
            'created_at': dest.created_at.isoformat(),
            'updated_at': dest.updated_at.isoformat(),
            'last_seen': dest.last_seen.isoformat() if dest.last_seen else None
        }

    async def validate_destination_configuration(self, dest_config: DestinationConfig) -> List[str]:
        """
        Validate destination configuration

        Args:
            dest_config: Destination configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check name uniqueness
        existing = await self._get_destination_by_name(dest_config.name)
        if existing:
            errors.append(f"Destination '{dest_config.name}' already exists")

        # Validate host
        if not self._validate_host(dest_config.host):
            errors.append(f"Invalid host format: {dest_config.host}")

        # Validate status
        if dest_config.status not in ['active', 'inactive', 'error']:
            errors.append(f"Invalid status: {dest_config.status}")

        # Test connectivity if active
        if dest_config.status == 'active':
            try:
                result = await self.ping_collector.ping_async(dest_config.host)
                if not result['success']:
                    errors.append(f"Host {dest_config.host} is not reachable: {result.get('error', 'Unknown error')}")
            except Exception as e:
                errors.append(f"Failed to test connectivity to {dest_config.host}: {str(e)}")

        return errors