import logging
from fastapi import APIRouter, HTTPException, Query

from app.core import location_service

logger = logging.getLogger("renalai.location_router")
router = APIRouter(prefix="/location", tags=["location"])


@router.get("/status")
def status():
    return {"available": location_service.location_is_configured()}


@router.get("/nearby")
async def nearby(
    latitude: float = Query(...),
    longitude: float = Query(...),
    category: str = Query(..., description="nephrologist | kidney_hospital | dialysis_center | emergency_hospital"),
):
    try:
        result = await location_service.find_nearby(latitude, longitude, category)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except location_service.LocationUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
