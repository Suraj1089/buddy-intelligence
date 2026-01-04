"""
Location search API using Nominatim (OpenStreetMap).
"""

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class LocationResult(BaseModel):
    """Location search result."""

    display_name: str
    lat: float
    lon: float
    postcode: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class LocationSearchResponse(BaseModel):
    """Response for location search."""

    results: list[LocationResult]


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@router.get("/search", response_model=LocationSearchResponse)
async def search_location(
    q: str = Query(
        ..., min_length=3, description="Search query (address, city, pincode)"
    ),
):
    """
    Search for locations using Nominatim (OpenStreetMap).
    Returns matching addresses with coordinates.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                NOMINATIM_URL,
                params={
                    "q": q,
                    "format": "json",
                    "addressdetails": 1,
                    "limit": 5,
                    "countrycodes": "in",  # Limit to India
                },
                headers={"User-Agent": "BuddyApp/1.0"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data:
            address = item.get("address", {})
            results.append(
                LocationResult(
                    display_name=item.get("display_name", ""),
                    lat=float(item.get("lat", 0)),
                    lon=float(item.get("lon", 0)),
                    postcode=address.get("postcode"),
                    city=address.get("city")
                    or address.get("town")
                    or address.get("village"),
                    state=address.get("state"),
                    country=address.get("country"),
                )
            )

        return LocationSearchResponse(results=results)

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503, detail=f"Location service unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error searching location: {str(e)}"
        )
