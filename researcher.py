import re
import time
from urllib.parse import urlparse
from ddgs import DDGS

# Regex patterns to extract an hour count from text
HOUR_PATTERNS = [
    r'(\d+)[\s-]*hours?\s+(?:of\s+)?(?:free|complimentary)\s+parking',
    r'free\s+(?:parking\s+)?(?:for\s+)?(\d+)[\s-]*hours?',
    r'(\d+)[\s-]*hours?\s+free\s+parking',
    r'complimentary\s+(?:parking\s+)?(?:for\s+)?(\d+)[\s-]*hours?',
    r'park(?:ing)?\s+(?:is\s+)?free\s+(?:for\s+)?(\d+)',
    r'(?:up\s+to|max(?:imum)?)\s+(\d+)[\s-]*hours?\s+(?:free\s+)?(?:parking|stay)',
    r'(\d+)[\s-]*(?:hour|hr)s?\s+(?:max(?:imum)?|limit|stay)',
    r'maximum\s+(?:stay\s+(?:of\s+)?)?(\d+)\s*(?:hour|hr)',
    r'(\d+)\s*(?:hour|hr)\s+maximum',
    r'park\s+(?:for\s+)?(?:up\s+to\s+)?(\d+)\s*(?:hour|hr)',
]

# Known facts confirmed from official or community sources.
# Format: "name (lowercase)" -> (hours_string, is_official, source_url)
# Hours in quotes = community-sourced (may be inaccurate). Plain = official source.
# RULE: if is_official=False, source_url MUST link to the community post/search,
#       not the business website, so users can judge the info themselves.
KNOWN_HOURS: dict[str, tuple[str, bool, str]] = {
    # New Westminster
    "royal city centre": (
        '"~4 hrs free"', False,
        "https://en.parkopedia.ca/parking/parkade/royal_city_centre_lot_025/v3l/new_westminster/",
    ),
    "shops at new west": (
        '"1 hr free w/ any purchase; 2 hrs w/ $25+ Safeway"', False,
        "https://www.parkme.com/lot/1231177/shop-at-new-west-lot-2298-vancouver-bc-canada",
    ),
    "safeway new westminster station": (
        '"1 hr free w/ any purchase; 2 hrs w/ $25+"', False,
        "https://www.parkme.com/lot/1231177/shop-at-new-west-lot-2298-vancouver-bc-canada",
    ),
    "walmart supercentre new westminster": (
        '"Free (no posted limit)"', False,
        "https://www.walmart.ca/en/store/5777",
    ),
    # Burnaby — official sources
    "metropolis at metrotown": (
        "4 hrs free", True,
        "https://www.metropolisatmetrotown.com/visit/",
    ),
    "the amazing brentwood": (
        "3 hrs free (surface lots; register plate at kiosk)", True,
        "https://theamazingbrentwood.com/centre-info/parking",
    ),
    # Burnaby — community sources
    "crystal mall": (
        '"3 hrs free"', False,
        "https://www.yelp.com/biz/the-crystal-mall-burnaby",
    ),
    "no frills burnaby heights": (
        '"1.5 hrs free"', False,
        "https://www.instagram.com/reel/DUGu9hPEh4G/",
    ),
    "whole foods market north burnaby": (
        '"Free w/ validation"', False,
        "https://modernmixvancouver.com/2016/01/26/an-insiders-guide-to-whole-foods-markets-first-burnaby-location/",
    ),
    "costco burnaby": (
        '"Free parking"', False,
        "https://www.costco.ca/w/-/bc/burnaby/51",
    ),
}


def _extract_hours(text: str) -> str | None:
    for p in HOUR_PATTERNS:
        m = re.search(p, text, re.I)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 12:   # sanity check
                return f"{n} hr" if n == 1 else f"{n} hrs"
    return None


def _same_domain(url: str, official_url: str) -> bool:
    try:
        a = urlparse(url).netloc.lstrip("www.")
        b = urlparse(official_url).netloc.lstrip("www.")
        return a == b or a in b or b in a
    except Exception:
        return False


def _search_hours(name: str, official_url: str | None, city: str = "New Westminster BC") -> tuple[str | None, str | None, bool]:
    """Returns (hours, source_url, is_official)."""
    official_queries = [
        f'How many hours of free parking is at {name} {city}?',
        f'What is the maximum free parking time at {name} {city}?',
        f'How long can you park for free at {name} {city}?',
    ]
    community_queries = [
        f'How many hours of free parking is at {name} {city}? reddit',
        f'How long is free parking at {name} {city}? review',
        f'What is the free parking limit at {name} {city}?',
        f'How many hours free parking {name} {city}?',
    ]

    with DDGS() as ddg:
        for q in official_queries:
            try:
                for r in ddg.text(q, max_results=5):
                    hours = _extract_hours(r.get("body", ""))
                    if hours and official_url and _same_domain(r["href"], official_url):
                        return hours, r["href"], True
                time.sleep(0.5)
            except Exception:
                pass

        for q in community_queries:
            try:
                for r in ddg.text(q, max_results=6):
                    hours = _extract_hours(r.get("body", ""))
                    if hours:
                        return hours, r["href"], False
                time.sleep(0.5)
            except Exception:
                pass

    return None, None, False


def enrich_hours(spots: list[dict]) -> list[dict]:
    for spot in spots:
        key = spot["name"].lower()

        # Always apply KNOWN_HOURS — overrides any stale cached value
        if key in KNOWN_HOURS:
            hours_str, is_official, source_url = KNOWN_HOURS[key]
            spot["max_hours"] = hours_str
            spot["hours_confirmed"] = is_official
            spot["hours_source_url"] = source_url
            continue

        # Only web-search seed entries — web-scraped results are too noisy to search reliably
        if spot.get("source") != "seed":
            continue

        # Skip web search if already found
        existing = spot.get("max_hours", "")
        if existing and existing not in ("Not found online", ""):
            continue

        # Otherwise search the web
        city = spot.get("city", "New Westminster BC")
        hours, source_url, is_official = _search_hours(spot["name"], spot.get("url"), city)
        if hours and source_url:
            spot["max_hours"] = hours if is_official else f'"{hours}"'
            spot["hours_source_url"] = source_url
            spot["hours_confirmed"] = is_official

    return spots
