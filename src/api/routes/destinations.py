"""
Destinations API Routes

REST API endpoints for managing global destinations including CRUD operations,
search, and status monitoring.
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel, Field

from src.core.config import DestinationConfig
from src.services.destination_manager import DestinationManager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Pydantic models for API requests/responses
class DestinationRequest(BaseModel):
    """Request model for destination operations"""
    name: str = Field(..., description="Unique destination name")
    host: str = Field(..., description="Hostname or IP address")
    display_name: str = Field(..., description="Human-readable display name")
    description: Optional[str] = Field(None, description="Optional description")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    status: str = Field("active", description="Destination status (active, inactive, error)")

class DestinationResponse(BaseModel):
    """Response model for destination data"""
    id: int
    name: str
    host: str
    display_name: str
    description: Optional[str]
    tags: List[str]
    status: str
    created_at: str
    updated_at: str
    last_seen: Optional[str]

class DestinationStatusResponse(BaseModel):
    """Response model for destination status"""
    id: int
    name: str
    host: str
    status: str
    last_seen: Optional[str]
    last_check: Optional[str]
    last_ping: Optional[float]
    success_rate: float
    total_checks: int
    recent_failures: int
    uptime_percentage: float

class DestinationSearchResponse(BaseModel):
    """Response model for destination search results"""
    destinations: List[DestinationResponse]
    total_count: int
    query: str
    filters: Dict[str, Any]

def get_destination_manager(request: Request) -> DestinationManager:
    """Dependency to get destination manager instance"""
    if not hasattr(request.app.state, 'destination_manager'):
        raise HTTPException(status_code=503, detail="Destination manager not available")
    return request.app.state.destination_manager

@router.get("/", response_model=List[DestinationResponse])
async def get_destinations(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Get all destinations with optional filtering

    Returns a list of all configured destinations with their current status.
    """
    try:
        destinations = await manager.get_all_destinations(active_only=False)

        # Apply filters
        if status:
            destinations = [d for d in destinations if d.get('status') == status]

        if tags:
            required_tags = [tag.strip() for tag in tags.split(',')]
            destinations = [
                d for d in destinations
                if all(tag in d.get('tags', []) for tag in required_tags)
            ]

        return [DestinationResponse(**dest) for dest in destinations]

    except Exception as e:
        logger.error(f"Failed to get destinations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve destinations")

@router.get("/{destination_id}", response_model=DestinationResponse)
async def get_destination(
    destination_id: int,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Get a specific destination by ID

    Returns detailed information about a specific destination.
    """
    try:
        destination = await manager.get_destination(destination_id)
        if not destination:
            raise HTTPException(status_code=404, detail=f"Destination with ID {destination_id} not found")

        return DestinationResponse(**destination)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get destination {destination_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve destination")

@router.get("/name/{name}", response_model=DestinationResponse)
async def get_destination_by_name(
    name: str,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Get a specific destination by name

    Returns detailed information about a specific destination by name.
    """
    try:
        destination = await manager.get_destination_by_name(name)
        if not destination:
            raise HTTPException(status_code=404, detail=f"Destination '{name}' not found")

        return DestinationResponse(**destination)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get destination '{name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve destination")

@router.post("/", response_model=DestinationResponse, status_code=201)
async def create_destination(
    destination: DestinationRequest,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Create a new destination

    Adds a new destination to the global destination inventory.
    """
    try:
        # Validate destination configuration
        dest_config = DestinationConfig(
            name=destination.name,
            host=destination.host,
            display_name=destination.display_name,
            description=destination.description,
            tags=destination.tags,
            status=destination.status
        )

        # Perform additional validation
        validation_errors = await manager.validate_destination_configuration(dest_config)
        if validation_errors:
            raise HTTPException(
                status_code=422,
                detail=f"Validation failed: {'; '.join(validation_errors)}"
            )

        # Create destination
        dest_id = await manager.create_destination(dest_config)

        # Get created destination
        created_dest = await manager.get_destination(dest_id)
        return DestinationResponse(**created_dest)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create destination '{destination.name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to create destination")

@router.put("/{destination_id}", response_model=DestinationResponse)
async def update_destination(
    destination_id: int,
    updates: DestinationRequest,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Update an existing destination

    Updates destination configuration with new values.
    """
    try:
        # Prepare update data
        update_data = {
            'host': updates.host,
            'display_name': updates.display_name,
            'description': updates.description,
            'tags': updates.tags,
            'status': updates.status
        }

        # Only include non-None values
        update_data = {k: v for k, v in update_data.items() if v is not None or k == 'description'}

        # Update destination
        success = await manager.update_destination(destination_id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail=f"Destination with ID {destination_id} not found")

        # Get updated destination
        updated_dest = await manager.get_destination(destination_id)
        return DestinationResponse(**updated_dest)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update destination {destination_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update destination")

@router.delete("/{destination_id}")
async def delete_destination(
    destination_id: int,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Delete a destination

    Removes a destination from the global inventory.
    Destination cannot be deleted if it's used by any jobs.
    """
    try:
        success = await manager.delete_destination(destination_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Destination with ID {destination_id} not found")

        return {"message": f"Destination {destination_id} deleted successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete destination {destination_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete destination")

@router.get("/{destination_id}/status", response_model=DestinationStatusResponse)
async def get_destination_status(
    destination_id: int,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Get detailed status information for a destination

    Returns comprehensive status information including recent performance metrics,
    success rates, and health indicators.
    """
    try:
        status = await manager.get_destination_status(destination_id)
        return DestinationStatusResponse(**status)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get destination status {destination_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve destination status")

@router.get("/search", response_model=DestinationSearchResponse)
async def search_destinations(
    request: Request,
    query: str = Query(..., description="Search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Search destinations

    Search destinations by name, host, display_name, or description.
    Additional filters can be applied for status and tags.
    """
    try:
        # Prepare filters
        filters = {}
        if status:
            filters['status'] = status
        if tags:
            filters['tags'] = [tag.strip() for tag in tags.split(',')]

        # Perform search
        destinations = await manager.search_destinations(query, filters)

        return DestinationSearchResponse(
            destinations=[DestinationResponse(**dest) for dest in destinations],
            total_count=len(destinations),
            query=query,
            filters=filters
        )

    except Exception as e:
        logger.error(f"Failed to search destinations: {e}")
        raise HTTPException(status_code=500, detail="Failed to search destinations")

@router.post("/{destination_id}/test-connectivity")
async def test_connectivity(
    destination_id: int,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Test connectivity to a destination

    Performs a quick connectivity test to verify if the destination is reachable.
    """
    try:
        # Get destination
        destination = await manager.get_destination(destination_id)
        if not destination:
            raise HTTPException(status_code=404, detail=f"Destination with ID {destination_id} not found")

        # Test connectivity using ping collector
        ping_collector = manager.ping_collector
        result = await ping_collector.test_connectivity(destination['host'])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test connectivity for destination {destination_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to test connectivity")

@router.get("/summary")
async def get_destinations_summary(
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Get destinations summary statistics

    Returns summary information about all destinations including counts by status
    and health indicators.
    """
    try:
        all_destinations = await manager.get_all_destinations(active_only=False)

        # Calculate statistics
        total = len(all_destinations)
        active = len([d for d in all_destinations if d.get('status') == 'active'])
        inactive = len([d for d in all_destinations if d.get('status') == 'inactive'])
        error = len([d for d in all_destinations if d.get('status') == 'error'])

        # Get detailed status for active destinations
        active_destinations = [d for d in all_destinations if d.get('status') == 'active']
        total_checks = 0
        total_successful = 0

        for dest in active_destinations:
            try:
                status = await manager.get_destination_status(dest['id'])
                total_checks += status.get('total_checks', 0)
                total_successful += status.get('total_checks', 0) * (status.get('success_rate', 0) / 100)
            except Exception:
                # Skip if status check fails
                continue

        overall_success_rate = (total_successful / total_checks * 100) if total_checks > 0 else 0

        return {
            'total_destinations': total,
            'active_destinations': active,
            'inactive_destinations': inactive,
            'error_destinations': error,
            'overall_success_rate': round(overall_success_rate, 2),
            'total_checks_performed': total_checks,
            'health_status': 'healthy' if error == 0 and overall_success_rate > 95 else 'degraded'
        }

    except Exception as e:
        logger.error(f"Failed to get destinations summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve destinations summary")

@router.post("/validate")
async def validate_destination(
    destination: DestinationRequest,
    request: Request,
    manager: DestinationManager = Depends(get_destination_manager)
):
    """
    Validate destination configuration

    Performs comprehensive validation of destination configuration including
    connectivity testing and format validation.
    """
    try:
        # Create destination config
        dest_config = DestinationConfig(
            name=destination.name,
            host=destination.host,
            display_name=destination.display_name,
            description=destination.description,
            tags=destination.tags,
            status=destination.status
        )

        # Validate configuration
        validation_errors = await manager.validate_destination_configuration(dest_config)

        if validation_errors:
            return {
                'valid': False,
                'errors': validation_errors
            }
        else:
            return {
                'valid': True,
                'message': 'Destination configuration is valid'
            }

    except Exception as e:
        logger.error(f"Failed to validate destination: {e}")
        return {
            'valid': False,
            'errors': [f"Validation error: {str(e)}"]
        }