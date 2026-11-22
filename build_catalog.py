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
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://buster.cheapcharts.de/v1/gptapi/Deals.php"
# Undocumented backend behind the CheapCharts site (the public API echoes it in
# its own `originRequest` field). Unlike Deals.php it supports `offset` paging,
# a `listType` selector, and returns a `turned4K` timestamp on every row.
OFFERLIST = "https://buster.cheapcharts.de/v1/OfferList.php"
OUT = Path(__file__).parent / "docs"

# Two catalogs, mirroring the two CheapCharts pages.
#
#   order="api"    -> keep the API's own ordering
#   order="price"  -> re-sort cheapest first (kept as an option; unused by default,
#                     since we no longer surface pricing)
#
# Note on "upgraded": the primary path is OfferList.php?listType=4KUpgraded (see
# build_upgraded_family), which pages the *entire* upgrade list with real dates and
# also yields the "Last 30 Days" and per-year catalogs. The Deals.php `sorts`
# below are only the fallback if that endpoint fails; Deals.php never returns the
# turned4K date and only lists titles currently on sale.
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
    {
        # sort=releaseDate is a valid sort (invalid names return an empty list);
        # it orders newest release date first.
        "id": "cc-4k-new",
        "name": "Just Released",
        "sorts": ["releaseDate"],
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

UPGRADED_ID = "cc-4k-upgraded"
PAGE_SIZE = 50        # OfferList caps a page at 50 rows
MAX_PAGES = 100       # hard stop; ~1,900 rows exist today, so 5,000 is far beyond the end
UPGRADED_MIN = 1000   # floor for the full upgrade list (~1,870 today); below = endpoint broken
RECENT_DAYS = 30      # window for the "Last 30 Days" catalog

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
UPGRADED_MIN = int(os.environ.get("CC_MIN_UPGRADED", UPGRADED_MIN))


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
    # Deals.php calls it `genre`; OfferList.php calls it `primaryGenreName`.
    genre = item.get("genre") or item.get("primaryGenreName")
    if genre:
        meta["genres"] = [genre]
    if item.get("description"):
        meta["description"] = item["description"]
    return meta


def fetch_upgraded_page(offset, attempts=5):
    """One OfferList page of the 4K-upgrades list, with backoff on 429/5xx/network errors."""
    params = urllib.parse.urlencode({
        "store": "itunes",
        "country": "us",
        "itemType": "buymovies",
        "listType": "4KUpgraded",
        "sort": "turned4K",
        "quality": "4k",
        "genreIds": 0,
        "priceRange": "all",
        "imdbRange": 0,
        "rottenRange": 0,
        "releaseYear": f"1900-{datetime.now(timezone.utc).year}",
        "offset": offset,
        "limit": PAGE_SIZE,
    })
    req = urllib.request.Request(
        f"{OFFERLIST}?{params}",
        headers={"User-Agent": "nuvio-4k-sale-addon/1.0"},
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.load(r)
            if payload.get("status") != "success":
                raise RuntimeError(payload.get("message") or f"status={payload.get('status')}")
            results = payload.get("results")
            return (results.get("buymovies") if isinstance(results, dict) else results) or []
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            if not retryable or attempt == attempts - 1:
                raise
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
        time.sleep(REQUEST_DELAY * (2 ** attempt))
    return []


def collect_upgraded():
    """Page the whole 4KUpgraded list. Returns rows newest-upgrade-first.

    Raises RuntimeError (not SystemExit) on any problem so the caller can fall back:
    a truncated list would silently drop the oldest years, so partial = failure.
    """
    rows, seen = [], set()
    for page in range(MAX_PAGES):
        items = fetch_upgraded_page(page * PAGE_SIZE)
        if not items:
            break
        for item in items:
            imdb = item.get("imdbId")
            if not imdb or imdb in seen:   # bundles have no IMDb id; ties can repeat across pages
                continue
            seen.add(imdb)
            rows.append(item)
        if (page + 1) % 10 == 0:
            print(f"  page {page + 1:3}  unique titles so far: {len(rows)}")
        time.sleep(REQUEST_DELAY)
    else:
        raise RuntimeError(f"no end of list after {MAX_PAGES} pages")

    if len(rows) < UPGRADED_MIN:
        raise RuntimeError(f"only {len(rows)} titles (minimum {UPGRADED_MIN})")

    # The API already returns newest-first; sorting on the timestamp makes that an
    # invariant instead of an assumption. Python's sort is stable, so ties keep API order.
    rows.sort(key=lambda m: m.get("turned4K") or "", reverse=True)
    return rows


def group_upgraded(rows):
    """Split rows into {catalog_id: rows}: Last 30 Days plus one bucket per year."""
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=RECENT_DAYS)).isoformat()
    groups = {f"{UPGRADED_ID}-30d": []}
    for row in rows:
        stamp = row.get("turned4K") or ""
        if not stamp[:4].isdigit():
            continue                      # undated rows stay in the main catalog only
        if stamp[:10] >= cutoff:
            groups[f"{UPGRADED_ID}-30d"].append(row)
        groups.setdefault(f"{UPGRADED_ID}-{stamp[:4]}", []).append(row)
    return groups


def build_upgraded_family():
    """Rebuild 'Upgraded to 4K' plus its dated catalogs from the 4KUpgraded list."""
    rows = collect_upgraded()
    folder = OUT / "catalog" / "movie"

    metas = [to_meta(r) for r in rows]
    (folder / f"{UPGRADED_ID}.json").write_text(json.dumps({"metas": metas}, indent=2))
    print(f"  -> {len(metas)} titles ({UPGRADED_ID})")

    groups = group_upgraded(rows)
    for cid, grows in groups.items():
        (folder / f"{cid}.json").write_text(
            json.dumps({"metas": [to_meta(r) for r in grows]}, indent=2))
        print(f"  -> {len(grows):4} titles ({cid})")

    # Drop year files that no longer have any titles, so the manifest can't list an empty year.
    for path in folder.glob(f"{UPGRADED_ID}-[0-9][0-9][0-9][0-9].json"):
        if path.stem not in groups:
            path.unlink()
            print(f"  (removed stale {path.name})")
    return len(metas)


def dated_catalog_specs():
    """Manifest entries for the dated upgrade catalogs, discovered from what is on disk.

    Reading disk (not the current run) keeps the manifest correct on partial runs
    and when the fallback path leaves the dated files untouched.
    """
    folder = OUT / "catalog" / "movie"
    specs = []
    if (folder / f"{UPGRADED_ID}-30d.json").exists():
        specs.append({"id": f"{UPGRADED_ID}-30d", "name": "Upgraded: Last 30 Days"})
    years = sorted(
        (int(p.stem.rsplit("-", 1)[1])
         for p in folder.glob(f"{UPGRADED_ID}-[0-9][0-9][0-9][0-9].json")),
        reverse=True,
    )
    specs += [{"id": f"{UPGRADED_ID}-{y}", "name": f"Upgraded in {y}"} for y in years]
    return specs


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

        merge_existing = False
        if spec["id"] == UPGRADED_ID:
            try:
                counts[spec["id"]] = build_upgraded_family()
                continue
            except Exception as exc:
                # Fallback: the old Deals.php path, merged with yesterday's file so a bad
                # day can never shrink the catalog. The dated catalogs are left as they are.
                print(f"::warning::4KUpgraded list failed ({exc}); "
                      "falling back to Deals.php and keeping the existing dated catalogs")
                merge_existing = True

        items = collect(spec["sorts"])

        if spec["order"] == "price":
            # Cheapest first; flip this line if you'd rather browse another way.
            items.sort(key=lambda x: x["price"] if x.get("price") is not None else 9e9)
        # order == "api" keeps the upgrade-recency ordering the API returned.

        metas = [to_meta(i) for i in items]
        if merge_existing and path.exists():
            have = {m["id"] for m in metas}
            metas += [m for m in json.loads(path.read_text())["metas"] if m["id"] not in have]
        counts[spec["id"]] = len(metas)
        path.write_text(json.dumps({"metas": metas}, indent=2))
        print(f"  -> {len(metas)} titles")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Dated upgrade catalogs sit directly after "Upgraded to 4K" in the manifest.
    dated = dated_catalog_specs()
    catalogs = []
    for s in CATALOGS:
        catalogs.append({"type": "movie", "id": s["id"], "name": s["name"]})
        if s["id"] == UPGRADED_ID:
            catalogs += [{"type": "movie", "id": d["id"], "name": d["name"]} for d in dated]

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
        "catalogs": catalogs,
        "behaviorHints": {"configurable": False},
    }

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nWrote {OUT/'manifest.json'}")
    for spec in CATALOGS:
        print(f"  {spec['name']:24} {counts[spec['id']]:4} titles"
              f"  ({spec['id']}.json)")
    for spec in dated:
        n = len(json.loads((OUT / "catalog" / "movie" / f"{spec['id']}.json").read_text())["metas"])
        print(f"  {spec['name']:24} {n:4} titles  ({spec['id']}.json)")


if __name__ == "__main__":
    main()
