import time
import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "FreeParkingNW/1.0 (alison.userbrain@gmail.com)"}


def geocode(query: str) -> tuple[float, float] | None:
    params = {"q": query, "format": "json", "limit": 1}
    r = requests.get(NOMINATIM, params=params, headers=HEADERS, timeout=10)
    data = r.json()
    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])
    return None


def enrich(spots: list[dict]) -> list[dict]:
    for spot in spots:
        if spot.get("lat"):
            continue
        city = spot.get("city", "New Westminster BC Canada")
        query = spot.get("address") or f"{spot['name']} {city}"
        coords = geocode(query)
        time.sleep(1)  # Nominatim rate limit: 1 req/sec
        if coords:
            spot["lat"], spot["lng"] = coords
    return spots
