
import logging

import httpx

logger = logging.getLogger(__name__)

async def get_coordinates(address: str) -> tuple[float | None, float | None]:
    """
    Get latitude and longitude for an address using OpenStreetMap (Nominatim).
    Returns (latitude, longitude) or (None, None) if not found.
    """
    if not address:
        return None, None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Nominatim usage policy requires a valid User-Agent
            headers = {
                "User-Agent": "BuddyIntelligence/1.0 (dev@buddy.localhost)"
            }

            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": address,
                    "format": "json",
                    "limit": 1
                },
                headers=headers
            )

            response.raise_for_status()
            data = response.json()

            if data and len(data) > 0:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                logger.info(f"Geocoded '{address}' to ({lat}, {lon})")
                return lat, lon

    except Exception as e:
        logger.error(f"Geocoding error for address '{address}': {str(e)}")

    return None, None
