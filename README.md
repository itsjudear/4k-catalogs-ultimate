# iTunes 4K — a static Nuvio / Stremio catalog addon

Serves **two** browsable catalogs from the Apple TV / iTunes US store, mirroring the two
CheapCharts pages:

| Catalog | Catalog id | What it is |
|---|---|---|
| **Movies in 4K** | `cc-4k-movies` | 4K movies, most popular first |
| **Upgraded to 4K** | `cc-4k-upgraded` | 4K movies in order of how recently they were upgraded |

Each entry carries **title and artwork only** — poster, background and logo. No pricing.

Built from the [CheapCharts public API](https://www.cheapcharts.com/llms.txt) and hosted free
on GitHub Pages. A GitHub Action rebuilds both every morning.

No server, no API keys, no cost.

---

## What you get

- `docs/manifest.json` — the addon manifest you paste into Nuvio
- `docs/catalog/movie/cc-4k-movies.json` — the 4K movies catalog
- `docs/catalog/movie/cc-4k-upgraded.json` — the upgrades catalog
- `build_catalog.py` — regenerates all of the above from the live API
- `.github/workflows/update-catalog.yml` — daily rebuild at 06:00 UTC

Posters, backgrounds and logos come from Stremio's own metahub CDN, derived from each
title's IMDb id. Roughly 29 in 30 titles resolve an image; the rest fall back to Nuvio's
placeholder.

---

## Setup (about ten minutes, one time)

**1. Create the repo**

Make a new **public** GitHub repository — Pages needs public on the free tier. Upload the
contents of this folder to the repo root, keeping the structure intact:

```
build_catalog.py
README.md
docs/
  manifest.json
  catalog/movie/cc-4k-movies.json
  catalog/movie/cc-4k-upgraded.json
.github/workflows/update-catalog.yml
```

**2. Turn on GitHub Pages**

Repo → **Settings** → **Pages** → Source: *Deploy from a branch* → Branch: `main`, folder
`/docs` → Save. Wait a minute or two, then confirm this loads in a browser:

```
https://<your-username>.github.io/<your-repo>/manifest.json
```

**3. Allow the Action to commit**

Repo → **Settings** → **Actions** → **General** → Workflow permissions → select
**Read and write permissions** → Save. Without this the daily job builds fine but can't
push the result.

**4. Install in Nuvio**

Nuvio → Addons → Add addon by URL → paste your manifest URL from step 2.

**5. Point your collection at it**

Your collection is already `TABBED_GRID`, so the natural layout is one folder per catalog —
they'll render as two tabs. Rename the existing `All 4K Upgrades` folder and add a second:

```json
"folders": [
  { "title": "Upgraded to 4K", "catalogSources": [
      { "addonId": "com.dude.cheapcharts.4ksale",
        "type": "movie", "catalogId": "cc-4k-upgraded" } ] },
  { "title": "Movies in 4K", "catalogSources": [
      { "addonId": "com.dude.cheapcharts.4ksale",
        "type": "movie", "catalogId": "cc-4k-movies" } ] }
]
```

(Keep each folder's other existing keys — `id`, `tileShape`, `hideTitle` and so on.)

The exact key names Nuvio writes into `catalogSources` are worth confirming — add one
catalog through the Nuvio UI, export the collection, and copy the shape it produces.
That's more reliable than hand-writing it.

---

## Refreshing

- **Automatic:** daily at 06:00 UTC via the Action.
- **Manual:** repo → Actions → *Update 4K catalogs* → *Run workflow*.
- **Locally:** `python3 build_catalog.py` (Python 3.9+, standard library only), then commit `docs/`.

---

## Tweaking

Everything worth changing sits in the `CATALOGS` list and the constants at the top of
`build_catalog.py`:

| What | How |
|---|---|
| Different country | `"country": "us"` in `fetch()` → `gb`, `de`, `ca`, `au`, … |
| Different store | `"store": "itunes"` → `amazon`, `vudu`, `googlePlay` (fewer countries) |
| HD as well as 4K | `"quality": "4k"` → `hd4k` |
| Catalog display names | the `name` field in `CATALOGS` |
| Browse order | a catalog's `sorts` list; `order` is `"api"` (keep API ordering) or `"price"` (cheapest first) |

Adding a third catalog is just another entry in `CATALOGS` — the manifest and the output
files are both generated from that list. For example, a highly-rated-only catalog:

```python
{"id": "cc-4k-popular", "name": "Popular in 4K",
 "sorts": ["popularity"], "order": "api"},
```

---

## Known limits

- **"Upgraded to 4K" is an ordering, not a dated feed.** `sort=turned4K` is a real sort
  parameter (an invalid sort name returns nothing, this one returns a distinct ordering),
  but the API never returns the `turned4K` *date* despite documenting it. So the catalog
  is ordered by upgrade recency, and you can't see or filter on when each upgrade happened.
- **Both catalogs are drawn from the deals endpoint**, so they lean towards titles that
  have had a recent price change. This isn't a complete inventory of every 4K title.
- **The API caps every response at 50 items with no paging.** The script works around this
  by querying each genre separately and merging, which gets both catalogs into the several
  hundreds. Some large genres are still truncated. A side effect for *Upgraded to 4K*:
  the first ~50 are in true global upgrade order, and the rest are appended genre by genre.
- **Bundles and multi-film collections are dropped** — they carry no IMDb id, and Stremio
  metas require one.
- **The endpoint rate-limits** despite its docs claiming otherwise. `REQUEST_DELAY` is set
  to 1 second with exponential backoff on 429.
- **GitHub Pages sends no CORS headers.** Irrelevant for Nuvio (a native app), but this
  addon won't work in Stremio's *web* client. Desktop and mobile Stremio are fine.
- The build refuses to publish if it collects fewer than `MIN_TITLES` (150), so a bad API
  day leaves your existing catalog untouched rather than emptying it.
