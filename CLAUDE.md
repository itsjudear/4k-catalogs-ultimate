# CLAUDE.md — project context for Claude Code

Drop this file in the repo root. Claude Code reads it automatically at the start of a
session, so it doesn't need to re-derive any of the below.

---

## What this project is

A **static Stremio-protocol catalog addon** for [Nuvio](https://github.com/tapframe/NuvioStreaming),
served as plain JSON files from GitHub Pages. No server, no API keys, no runtime.

`build_catalog.py` pulls from the CheapCharts public API, writes two catalog files plus a
manifest into `docs/`, and a GitHub Action re-runs it daily and commits the result.

```
build_catalog.py                       # the generator (stdlib only, Python 3.9+)
docs/manifest.json                     # addon manifest -> this URL goes into Nuvio
docs/catalog/movie/cc-4k-movies.json   # catalog: "Movies in 4K"
docs/catalog/movie/cc-4k-upgraded.json # catalog: "Upgraded to 4K"
.github/workflows/update-catalog.yml   # daily rebuild, 06:00 UTC
```

Everything in `docs/` is **generated**. Never hand-edit it — change `build_catalog.py`
and re-run.

---

## The one requirement that matters

Each catalog entry carries **title and artwork only**. No prices, no discounts, no
ratings. This is deliberate and was asked for explicitly.

If you're touching `to_meta()`, the permitted keys are: `id`, `type`, `name`, `poster`,
`background`, `logo`, `posterShape`, `releaseInfo`, `genres`, `description`. Do not
reintroduce pricing fields even though the API returns them.

---

## Data source

CheapCharts agent API, documented at <https://www.cheapcharts.com/llms.txt>.
Free, public, no key. Base URL `https://buster.cheapcharts.de/v1/gptapi/`.

Only `Deals.php` is used:

```
GET /Deals.php?action=getDeals&store=itunes&country=us&itemType=buymovies
    &quality=4k&genre=<genre>&sort=<sort>&limit=50
```

### Hard-won facts about this API — read before changing fetch logic

These were established by testing. They contradict the vendor docs in places.

1. **`limit` is capped at 50 and there is no `offset`.** Asking for 1000 returns 50. The
   only way past it is fanning out across `genre` and `sort` and merging, which is what
   `collect()` does.
2. **It rate-limits**, despite the docs claiming "no rate limiting concerns". Six parallel
   workers triggered mass HTTP 429s. Sequential with `REQUEST_DELAY = 1.0` is stable;
   0.4s also worked but leaves no margin. Backoff on 429 is already implemented in `fetch()`.
3. **`sort=turned4K` is a real sort parameter and is what powers the "Upgraded to 4K"
   catalog.** Verified: an invented sort name (`bogusSortXYZ`) returns an empty result,
   while `turned4K` returns a populated, distinctly-ordered list led by catalogue remasters.
4. **The `turned4K` and `firstSeen4K` *fields* are documented but never returned.** So we
   get upgrade *ordering* but not upgrade *dates*. Don't waste time hunting for them.
5. **`quality` accepts only `4k`, `hd4k`, `hd`, `sd`, `sdOnly`.** Anything else 500s.
6. **Three genres always error**: `MadeForTV`, `Classical`, `Anime`. They're already
   excluded from `GENRES`. Don't re-add them.
7. **Roughly 15% of results are bundles/collections with no `imdbId`.** These are dropped —
   Stremio metas require an IMDb id. That's correct behaviour, not a bug.

Artwork comes from Stremio's metahub CDN via deterministic URLs built from the IMDb id
(`https://images.metahub.space/poster/medium/{ttid}/img`). No lookup call needed. Spot
check measured 29/30 resolving; the rest fall back to Nuvio's placeholder.

---

## Local development

```bash
python3 build_catalog.py                          # full build, ~2 minutes
CC_CATALOGS=cc-4k-upgraded python3 build_catalog.py   # rebuild one catalog only
CC_GENRES=All,Horror CC_DELAY=0.4 CC_MIN_TITLES=20 python3 build_catalog.py   # smoke test
```

Env overrides exist purely for quick iteration — `CC_CATALOGS`, `CC_SORTS`, `CC_GENRES`,
`CC_DELAY`, `CC_MIN_TITLES`. **Don't set any of them in CI**; the Action should run the
full config.

`CC_CATALOGS` only filters which catalogs get *rebuilt*. Unselected ones are left on disk
untouched and still counted, so a partial run can't produce a broken manifest.

The committed catalogs were seeded with a reduced sort list to fit a time limit, so the
first full Action run will legitimately add several dozen titles. That's expected, not a bug.

`MIN_TITLES` (150) is a safety floor: if a build collects fewer, it raises and writes
nothing, so a bad API day can't blank a live catalog. Keep that guard.

### Verifying a change

```bash
python3 -m py_compile build_catalog.py
python3 -c "import json; [json.load(open(f)) for f in ['docs/manifest.json']]"
```

Then confirm every meta has an `id` starting `tt` and a non-empty `name`, and that no
pricing strings leaked into the output.

---

## Deployment task

If the repo isn't published yet, this is the job:

1. `gh repo create <name> --public --source=. --push` — must be **public**, GitHub Pages
   needs it on the free tier.
2. Enable Pages: branch `main`, folder `/docs`. Via API:
   `gh api -X POST repos/{owner}/{repo}/pages -f source[branch]=main -f source[path]=/docs`
3. Set Actions workflow permissions to **read and write**, otherwise the daily job builds
   fine but can't push its commit.
4. Verify the published manifest actually serves:
   `curl -sf https://<user>.github.io/<repo>/manifest.json | jq .catalogs`
5. Report the manifest URL back — the human pastes it into Nuvio by hand.

Steps you **cannot** do headlessly: authenticating `gh` the first time, and installing the
addon inside Nuvio.

---

## Open question — needs a human

The Nuvio collection JSON references catalogs through a `catalogSources` array on each
folder. The intended shape is:

```json
"catalogSources": [
  { "addonId": "com.dude.cheapcharts.4ksale",
    "type": "movie",
    "catalogId": "cc-4k-upgraded" }
]
```

**This key naming is inferred, not confirmed** — no published Nuvio schema was found. The
reliable path is to add one catalog through the Nuvio UI, export the collection, and copy
whatever shape it actually writes. Don't assume the above is right.

---

## Known limits (don't treat these as bugs to fix)

- Both catalogs come from the *deals* endpoint, so they skew towards titles with a recent
  price change. This is not a complete inventory of every 4K title on the store.
- For *Upgraded to 4K*, only the first ~50 entries are in true global upgrade order; the
  rest are appended genre by genre because of the 50-item cap.
- GitHub Pages sends no CORS headers. Irrelevant for Nuvio (a native app), but this addon
  won't load in Stremio's **web** client. Desktop and mobile Stremio are fine.

---

## Possible extensions, if asked

- **Real upgrade dates.** Save a daily snapshot of the IMDb ids in the `quality=4k` set;
  any id present today but absent yesterday is a genuine 4K upgrade. Builds a properly
  dated feed over a week or two and works around limit #4 above.
- **More catalogs.** Add an entry to `CATALOGS` — manifest and output files are both
  generated from that list, so nothing else needs touching.
- **Other regions/stores.** Change `country` / `store` in `fetch()`. Note `amazon` is US+DE
  only, and `vudu` and `googlePlay` are US only.
