import json
import os

from flask import Flask, Response, redirect, render_template, url_for
from scraper import get_parking_spots
from geocoder import enrich
from researcher import enrich_hours

app = Flask(__name__)

DATA_FILE = "data/spots.json"
CITY = "Metro Vancouver, BC"
TYPE_COLORS = {
    "mall":    "#4285F4",
    "grocery": "#34A853",
    "lot":     "#FBBC04",
    "other":   "#9AA0A6",
}


def _load() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE) as f:
        return json.load(f)


def _save(spots: list[dict]) -> None:
    os.makedirs("data", exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(spots, f, indent=2)


@app.route("/")
def index():
    spots = [s for s in _load() if s.get("lat")]
    return render_template("map.html", spots=spots, city=CITY, type_colors=TYPE_COLORS)


@app.route("/list")
def list_view():
    spots = _load()
    return render_template("index.html", spots=spots, city=CITY)


@app.route("/scrape")
def scrape():
    existing = {s["url"]: s for s in _load() if s.get("url")}
    fresh = get_parking_spots()
    merged = []
    for s in fresh:
        cached = existing.get(s["url"])
        if cached:
            s["lat"] = cached.get("lat")
            s["lng"] = cached.get("lng")
            s["max_hours"] = cached.get("max_hours")
            s["hours_source_url"] = cached.get("hours_source_url")
            s["hours_confirmed"] = cached.get("hours_confirmed")
        merged.append(s)
    _save(merged)
    return "", 204


@app.route("/geocode")
def geocode():
    spots = enrich(_load())
    _save(spots)
    return "", 204


@app.route("/research")
def research():
    spots = enrich_hours(_load())
    _save(spots)
    return "", 204


@app.route("/export.kml")
def export_kml():
    spots = [s for s in _load() if s.get("lat")]
    kml = render_template("export.kml", spots=spots, city=CITY)
    return Response(kml, mimetype="application/vnd.google-earth.kml+xml",
                    headers={"Content-Disposition": "attachment; filename=free_parking_nw.kml"})


@app.route("/clear")
def clear():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(port=8080, debug=True)
