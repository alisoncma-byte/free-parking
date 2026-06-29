import json
import re
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

CITIES = ["New Westminster BC", "Burnaby BC"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SEED_FILE = "data/seed.json"

JUNK_DOMAINS = {
    "youtube.com", "facebook.com", "instagram.com", "reddit.com",
    "realtor.ca", "craigslist.org", "yandex.com", "qwen.ai",
    "jsononlineformatter.com", "parkers.co.uk", "anony-ig.com",
    "westminster-ca.gov", "dailyhive.com",
    # City government sites — general parking info, not specific free spots
    "newwestcity.ca", "burnaby.ca",
    # Review/directory/aggregator sites — lists or reviews, not specific spots
    "yelp.com", "yelp.ca", "tripadvisor.com", "tripadvisor.ca",
    "tiktok.com", "spotangels.com", "vrbo.com", "vrbo.ca",
    "expedia.ca", "expedia.com", "airbnb.com", "airbnb.ca",
    "parksy.ca", "parkme.com", "parkopedia.com", "en.parkopedia.ca",
    "roomies.ca", "newwestminster.com", "burnaby.com",
    "waze.com", "flyerbox.ca", "birdeye.com", "openinghours.ca",
    "mallfinder.ca", "shopping-canada.com", "parkopedia.ca",
}

CATEGORY_KEYWORDS = {
    "mall":    ["mall", "centre", "plaza", "square", "anvil", "columbia", "carnarvon", "metrotown", "brentwood", "highgate"],
    "grocery": ["save-on", "safeway", "no frills", "t&t", "superstore", "grocery", "food", "market", "walmart"],
    "lot":     ["lot", "parkade", "garage", "carpark"],
}


def _queries():
    for city in CITIES:
        yield f"free parking {city} mall no validation"
        yield f"free parking {city} grocery store validation"
        yield f"{city} free public parking lots"


def _categorize(text: str) -> str:
    t = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in t for k in keywords):
            return cat
    return "other"


def _validation_flag(text: str) -> bool:
    return bool(re.search(r"\bvalidat", text, re.I))


def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return m.group(1) if m else ""


def _is_junk(r: dict) -> bool:
    if _domain(r["href"]) in JUNK_DOMAINS:
        return True
    title = r["title"].lower()
    junk_keywords = [
        "youtube", "instagram", "json validator", "real estate", "for sale", "craigslist",
        "city of ", "pay parking", "parking meters", "parking bylaw", "parking regulations",
        "top 10", "best free parking", "complete guide", "local's guide", "your guide",
        "a guide to", "find & reserve", "find parking", "sleeps ", "br•", "br •",
        "- review of", "reviews of", "parking app", "parking lots, parkades",
        "map of parking", "map of free parking", "cheap parking",
    ]
    if any(k in title for k in junk_keywords):
        return True
    # Skip results whose title is just a URL fragment or over 100 chars (truncated search snippets)
    if len(r["title"]) > 100 or r["title"].startswith("http"):
        return True
    return False


def _load_seed() -> list[dict]:
    try:
        with open(SEED_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def scrape_web() -> list[dict]:
    results = []
    seen = set()
    with DDGS() as ddg:
        for query in _queries():
            for r in ddg.text(query, max_results=6):
                if r["href"] in seen or _is_junk(r):
                    continue
                seen.add(r["href"])
                body = r.get("body", "")
                combined = r["title"] + " " + body
                results.append({
                    "name": r["title"],
                    "address": "",
                    "snippet": body[:300],
                    "url": r["href"],
                    "type": _categorize(combined),
                    "validation_required": _validation_flag(body),
                    "source": "web",
                })
    return results


def get_parking_spots() -> list[dict]:
    seed = _load_seed()
    seed_names = {s["name"].lower() for s in seed}
    web = scrape_web()
    scraped = [s for s in web if s["name"].lower() not in seed_names]
    return seed + scraped
