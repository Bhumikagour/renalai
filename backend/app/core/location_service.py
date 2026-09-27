"""
RenalAI location service: find nearby nephrologists, kidney hospitals, dialysis
centers, and emergency hospitals via the Google Places API.

Environment-configured (GOOGLE_MAPS_API_KEY). Never hardcodes fake doctors/hospitals --
if the key is missing or the upstream call fails, returns an explicit configuration/
unavailable state instead of a search result.
"""
import logging
import os
import httpx

logger = logging.getLogger("renalai.location")

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

SEARCH_QUERIES = {
    "nephrologist": "nephrologist",
    "kidney_hospital": "kidney hospital",
    "dialysis_center": "dialysis center",
    "emergency_hospital": "emergency hospital",
}


class LocationUnavailableError(Exception):
    pass


def location_is_configured() -> bool:
    return bool(GOOGLE_MAPS_API_KEY)


async def find_nearby(latitude: float, longitude: float, category: str, radius_m: int = 15000) -> dict:
    """
    Returns {"results": [...], "category": category} on success.
    Raises LocationUnavailableError if the key is missing or the API call fails --
    the router turns this into an explicit configuration-needed response, never a
    silent empty list dressed up as "no results found nearby".
    """
    if category not in SEARCH_QUERIES:
        raise ValueError(f"Unknown category '{category}'. Must be one of {list(SEARCH_QUERIES)}")

    if not location_is_configured():
        raise LocationUnavailableError(
            "Nearby specialist search is not configured (missing GOOGLE_MAPS_API_KEY). "
            "Core CKD prediction is unaffected."
        )

    keyword = SEARCH_QUERIES[category]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                PLACES_NEARBY_URL,
                params={
                    "location": f"{latitude},{longitude}",
                    "radius": radius_m,
                    "keyword": keyword,
                    "type": "hospital" if "hospital" in category else "health",
                    "key": GOOGLE_MAPS_API_KEY,
                },
            )
        if resp.status_code != 200:
            logger.error("Google Places API error %s: %s", resp.status_code, resp.text[:300])
            raise LocationUnavailableError(f"Places API upstream error (status {resp.status_code}).")

        data = resp.json()
        api_status = data.get("status")
        if api_status not in ("OK", "ZERO_RESULTS"):
            logger.error("Google Places API status: %s -- %s", api_status, data.get("error_message"))
            raise LocationUnavailableError(f"Places API error: {api_status}")

        results = [
            {
                "name": r.get("name"),
                "address": r.get("vicinity"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("user_ratings_total"),
                "location": r.get("geometry", {}).get("location"),
                "place_id": r.get("place_id"),
                "open_now": r.get("opening_hours", {}).get("open_now"),
            }
            for r in data.get("results", [])
        ]
        return {"category": category, "results": results}

    except httpx.RequestError as e:
        logger.error("Places API request failed: %s", e)
        raise LocationUnavailableError(f"Could not reach the location service: {e}")
