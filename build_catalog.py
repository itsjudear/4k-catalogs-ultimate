#!/usr/bin/env python3
"""
Build a static Stremio/Nuvio addon catalog of iTunes US 4K movies currently on sale.

Data source: CheapCharts public agent API (https://www.cheapcharts.com/llms.txt)
Posters:     Stremio metahub (deterministic URLs derived from the IMDb id)

Writes:
    docs/manifest.json
    docs/catalog/movie/cc-4k-sale.json
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://buster.cheapcharts.de/v1/gptapi/Deals.php"
OUT = Path(__file__).parent / "docs"

# Two catalogs, mirroring the two CheapCharts pages.
#
#   order="api"    -> keep the API's own ordering
#   order="price"  -> re-sort cheapest first (kept as an option; unused by default,
#                     since we no longer surface pricing)
#
# Note on "upgraded": sort=turned4K is a genuine sort parameter - an invalid
# sort name returns an empty result, this one returns a distinct ordering led
# by catalog titles. The API does not return the turned4K *date*, only the order.
CATALOGS = [
    {
        "id": "cc-4k-movies",
        "name": "Movies in 4K",
        "sorts": ["popularity", "latestPricechange", "greatestSavings", "price"],
        "order": "api",
    },
    {
        "id": "cc-4k-upgraded",
        "name": "Upgraded to 4K",
        "sorts": ["turned4K"],
        "order": "api",
    },
]

# The API caps every response at 50 items and offers no offset parameter,
# so we fan out across genres and merge to get past that ceiling.
GENRES = [
    "All", "ActionAdventure", "Comedy", "Docus", "Drama", "Horror",
    "Romance", "Independent", "KidsFamily", "MusicDocumentation",
    "SciFiFantasy", "Sport", "Thriller", "Western", "Musicals",
]

REQUEST_DELAY = 1.0   # seconds between calls; the endpoint returns 429 if pushed
MIN_TITLES = 150      # sanity floor - below this we assume the API is broken

# Env overrides, handy for quick local runs and for building one catalog at a time:
#   CC_CATALOGS=cc-4k-upgraded python3 build_catalog.py
#   CC_SORTS=popularity CC_GENRES=All,Horror CC_DELAY=0.5 python3 build_catalog.py
#
# CC_CATALOGS only filters which catalogs are *rebuilt*; the manifest always
# declares all of them, so a partial run never breaks the addon.
if os.environ.get("CC_CATALOGS"):
    _want = set(os.environ["CC_CATALOGS"].split(","))
    BUILD_ONLY = _want
else:
    BUILD_ONLY = None
if os.environ.get("CC_SORTS"):
    for _c in CATALOGS:
        _c["sorts"] = os.environ["CC_SORTS"].split(",")
if os.environ.get("CC_GENRES"):
    GENRES = os.environ["CC_GENRES"].split(",")
REQUEST_DELAY = float(os.environ.get("CC_DELAY", REQUEST_DELAY))
MIN_TITLES = int(os.environ.get("CC_MIN_TITLES", MIN_TITLES))


def fetch(genre, sort, attempts=5):
    """One API call, with backoff on 429. The endpoint rate-limits in practice."""
    params = urllib.parse.urlencode({
        "action": "getDeals",
        "store": "itunes",
        "country": "us",
        "itemType": "buymovies",
        "quality": "4k",
        "genre": genre,
        "sort": sort,
        "limit": 50,
    })
    req = urllib.request.Request(
        f"{API}?{params}",
        headers={"User-Agent": "nuvio-4k-sale-addon/1.0"},
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.load(r)
            return payload.get("results", {}).get("buymovies", []) or []
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                raise
            time.sleep(REQUEST_DELAY * (2 ** attempt))
    return []


def collect(sorts):
    """Fan out over genre x sort sequentially, dedupe by IMDb id.

    Insertion order is preserved, so for a single-sort catalog the result
    keeps the API's own ordering.
    """
    seen = {}
    failures = 0
    for genre in GENRES:
        for sort in sorts:
            try:
                items = fetch(genre, sort)
            except Exception as exc:
                failures += 1
                print(f"  ! {genre}/{sort}: {exc}")
                continue
            for item in items:
                imdb = item.get("imdbId")
                if not imdb:
                    continue  # bundles/collections have no IMDb id -> unusable as a Stremio meta
                seen.setdefault(imdb, item)
            time.sleep(REQUEST_DELAY)
        print(f"  {genre:22} running total: {len(seen)}")

    if failures:
        print(f"  ({failures} queries failed)")
    # Guard against publishing a gutted catalog if the API was mostly unavailable.
    if len(seen) < MIN_TITLES:
        raise SystemExit(
            f"Only {len(seen)} titles collected (minimum {MIN_TITLES}). "
            "Refusing to overwrite the existing catalog."
        )
    return list(seen.values())


def to_meta(item):
    """Title + artwork only. Pricing is deliberately not carried through."""
    imdb = item["imdbId"]

    meta = {
        "id": imdb,
        "type": "movie",
        "name": item.get("title", ""),
        "poster": f"https://images.metahub.space/poster/medium/{imdb}/img",
        "background": f"https://images.metahub.space/background/medium/{imdb}/img",
        "logo": f"https://images.metahub.space/logo/medium/{imdb}/img",
        "posterShape": "poster",
    }
    # Cheap, useful context for the detail view - drop any of these if you want
    # the leanest possible catalog.
    if item.get("releaseDate"):
        meta["releaseInfo"] = item["releaseDate"][:4]
    if item.get("genre"):
        meta["genres"] = [item["genre"]]
    if item.get("description"):
        meta["description"] = item["description"]
    return meta


def main():
    counts = {}
    (OUT / "catalog" / "movie").mkdir(parents=True, exist_ok=True)

    for spec in CATALOGS:
        path = OUT / "catalog" / "movie" / f"{spec['id']}.json"

        if BUILD_ONLY is not None and spec["id"] not in BUILD_ONLY:
            # Not selected this run - keep whatever is already on disk.
            existing = json.loads(path.read_text())["metas"] if path.exists() else []
            counts[spec["id"]] = len(existing)
            print(f"\nSkipping '{spec['name']}' ({len(existing)} titles left as-is)")
            continue

        print(f"\nBuilding '{spec['name']}' (iTunes US, 4K)...")
        items = collect(spec["sorts"])

        if spec["order"] == "price":
            # Cheapest first; flip this line if you'd rather browse another way.
            items.sort(key=lambda x: x["price"] if x.get("price") is not None else 9e9)
        # order == "api" keeps the upgrade-recency ordering the API returned.

        metas = [to_meta(i) for i in items]
        counts[spec["id"]] = len(metas)
        path.write_text(json.dumps({"metas": metas}, indent=2))
        print(f"  -> {len(metas)} titles")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    manifest = {
        "id": "com.dude.cheapcharts.4ksale",
        "version": "1.0." + datetime.now(timezone.utc).strftime("%Y%m%d"),
        "name": "iTunes 4K",
        "description": (
            "4K movies on the Apple TV / iTunes US store, and those recently "
            "upgraded to 4K. Data from CheapCharts. "
            f"Last updated {stamp} ("
            + ", ".join(f"{v} {k}" for k, v in counts.items()) + ")."
        ),
        "logo": "https://images.metahub.space/logo/medium/tt0468569/img",
        "resources": ["catalog"],
        "types": ["movie"],
        "idPrefixes": ["tt"],
        "catalogs": [
            {"type": "movie", "id": s["id"], "name": s["name"]} for s in CATALOGS
        ],
        "behaviorHints": {"configurable": False},
    }

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nWrote {OUT/'manifest.json'}")
    for spec in CATALOGS:
        print(f"  {spec['name']:18} {counts[spec['id']]:4} titles"
              f"  ({spec['id']}.json)")


if __name__ == "__main__":
    main()
