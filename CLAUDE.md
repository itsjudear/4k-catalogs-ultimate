# CLAUDE.md — project context for Claude Code

Drop this file in the repo root. Claude Code reads it automatically at the start of a
session, so it doesn't need to re-derive any of the below.

---

## What this project is

A **static Stremio-protocol catalog addon** for [Nuvio](https://github.com/tapframe/NuvioStreaming),
served as plain JSON files from GitHub Pages. No server, no API keys, no runtime.

`build_catalog.py` pulls from CheapCharts, writes the catalog files plus a manifest into
`docs/`, and a GitHub Action re-runs it daily and commits the result.

```
build_catalog.py                       # the generator (stdlib only, Python 3.9+)
docs/manifest.json                     # addon manifest -> this URL goes into Nuvio
docs/catalog/movie/cc-4k-movies.json   # catalog: "Movies in 4K"
docs/catalog/movie/cc-4k-upgraded.json # catalog: "Upgraded to 4K" (full list, newest upgrade first)
docs/catalog/movie/cc-4k-upgraded-30d.json   # catalog: "Upgraded: Last 30 Days"
docs/catalog/movie/cc-4k-upgraded-YYYY.json  # catalog: "Upgraded in 2026" (only years in YEAR_CATALOGS)
docs/catalog/movie/cc-4k-new.json      # catalog: "Just Released"
.github/workflows/update-catalog.yml   # daily rebuild, 06:00 UTC
```

The per-year catalogs are limited to the years listed in `YEAR_CATALOGS` (currently just
2026, by request; the user found the full 2018-2026 set too long). A year not in that tuple
gets no file and no manifest entry, and its stale file is deleted on the next upgrade-family
build. **Nothing rolls over automatically**: in January, add 2027 to the tuple. Re-adding an
older year is the same one-line edit. The dated entries are discovered from disk when the
manifest is written, restricted to those years.

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

Two endpoints are used:

```
# Movies in 4K, Just Released, and the fallback for Upgraded (documented, on-sale titles only)
GET /Deals.php?action=getDeals&store=itunes&country=us&itemType=buymovies
    &quality=4k&genre=<genre>&sort=<sort>&limit=50

# Upgraded to 4K and its dated catalogs (UNDOCUMENTED backend behind the CheapCharts site)
GET https://buster.cheapcharts.de/v1/OfferList.php?store=itunes&country=us&itemType=buymovies
    &listType=4KUpgraded&sort=turned4K&quality=4k&genreIds=0&priceRange=all&imdbRange=0
    &rottenRange=0&releaseYear=1900-<this year>&offset=<n>&limit=50
```

`OfferList.php` is not in the vendor docs, but the public API echoes it in every response's
`originRequest` field, so it is what the documented endpoints proxy to. It could change
without notice, which is why `build_upgraded_family()` has a fallback (see fact 10).

### Hard-won facts about this API — read before changing fetch logic

These were established by testing. They contradict the vendor docs in places.

1. **`Deals.php` caps `limit` at 50 and has no `offset`.** Asking for 1000 returns 50. The
   only way past it there is fanning out across `genre` and `sort` and merging, which is
   what `collect()` does. **`OfferList.php` does honour `offset`** and pages cleanly.
2. **It rate-limits**, despite the docs claiming "no rate limiting concerns". Six parallel
   workers triggered mass HTTP 429s. Sequential with `REQUEST_DELAY = 1.0` is stable;
   0.4s also worked but leaves no margin. Backoff on 429 is already implemented in `fetch()`.
3. **Two sort values work but aren't in the docs' sort list: `turned4K` and `releaseDate`.**
   They power the "Upgraded to 4K" and "Just Released" catalogs. Verified by probing:
   invented sort names (`bogusSortXYZ`, `justReleased`, `newReleases`, `latest`) all return
   an empty result, while these two return populated, distinctly-ordered lists. That empty
   vs. populated response is a reliable way to test whether any other sort name is real.
4. **`Deals.php` never returns the `turned4K` / `firstSeen4K` fields**, despite documenting
   them, so Deals can give upgrade *order* but not dates. Two places do return a date:
   `OfferList.php?listType=4KUpgraded` (a full `YYYY-MM-DD HH:MM:SS` timestamp on every
   row) and `Prices.php` (per title, 5 IDs per call). `firstSeen4K` is null everywhere.
5. **`quality` accepts only `4k`, `hd4k`, `hd`, `sd`, `sdOnly`.** Anything else 500s.
6. **Three genres always error**: `MadeForTV`, `Classical`, `Anime`. They're already
   excluded from `GENRES`. Don't re-add them.
7. **Roughly 15% of Deals results are bundles/collections with no `imdbId`.** These are
   dropped — Stremio metas require an IMDb id. That's correct behaviour, not a bug. (The
   `4KUpgraded` list contains none.)
8. **The Deals feed only contains titles currently on sale.** A title that has just gone 4K
   but isn't discounted is invisible to it, however far you page. This is why Baby Boy
   (4K on 2026-11-18, priced up, not down) never appeared. The `4KUpgraded` list has no
   such filter: roughly 1,100 of its ~1,870 titles are not on sale.
9. **`OfferList.php` tells you its valid values when you get one wrong.** An invalid
   `listType` or `sort` returns an error message enumerating the accepted ones. Valid
   `sort` values include `turned4K` and `releaseDate`; `listType` includes `4KUpgraded`,
   `4KMovies`, `justreleased`, `onSale`, `charts`. Use that instead of guessing.
   `4KMovies` returns Baby Boy too, so it is the likely route to fix *Movies in 4K*'s
   on-sale bias, but it has not been built or paged yet.
10. **The `4KUpgraded` list is ~1,900 rows, newest upgrade first, with no order violations**
    (0 across all of 1,902 rows when checked 2026-11-22), spanning 2018-06 to today. Paging
    it takes ~39 sequential requests. A handful of titles repeat across page boundaries, so dedupe by
    IMDb id. If the endpoint fails, `main()` falls back to Deals and *merges with the
    previous file* so the catalog can't shrink; the dated catalogs are left as they were and
    the run prints a `::warning::` annotation. A truncated list would silently lose the
    oldest years, so any page failure counts as total failure.

Artwork comes from Stremio's metahub CDN via deterministic URLs built from the IMDb id
(`https://images.metahub.space/poster/medium/{ttid}/img`). No lookup call needed. Spot
check measured 29/30 resolving; the rest fall back to Nuvio's placeholder.

---

## Local development

```bash
python3 build_catalog.py                          # full build, a few minutes
CC_CATALOGS=cc-4k-upgraded python3 build_catalog.py   # rebuild the upgrade family only (~39 requests)
CC_GENRES=All,Horror CC_DELAY=0.4 CC_MIN_TITLES=20 python3 build_catalog.py   # smoke test
```

Env overrides exist purely for quick iteration — `CC_CATALOGS`, `CC_SORTS`, `CC_GENRES`,
`CC_DELAY`, `CC_MIN_TITLES`, `CC_MIN_UPGRADED`. **Don't set any of them in CI**; the Action
should run the full config.

`CC_CATALOGS` only filters which catalogs get *rebuilt*. Unselected ones are left on disk
untouched and still counted, so a partial run can't produce a broken manifest.
`cc-4k-upgraded` is a family: selecting it rebuilds the main, 30-day and per-year files together.

To test the fallback without hurting the repo, copy `build_catalog.py` and `docs/` to a
scratch folder, point `OFFERLIST` at a dead port, and run there.

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

- *Movies in 4K* and *Just Released* still come from the *deals* endpoint, so they skew
  towards titles currently on sale and are capped by the genre fan-out. They are not a
  complete inventory of every 4K title. (*Upgraded to 4K* no longer has this limit.)
- *Upgraded to 4K* depends on an undocumented endpoint. If it breaks, the daily run falls
  back to Deals and warns; the upgrade catalogs then go stale rather than empty.
- The `turned4K` timestamp's timezone is unknown (CheapCharts is German-run). Its date part
  matched the date shown on the site for Baby Boy (2026-11-18), and "Last 30 Days" compares
  dates only, so a few hours of skew at the boundary is possible and harmless.
- Titles upgraded before ~2018-06 are not in the `4KUpgraded` list, so they appear in no
  dated catalog (and with only 2026 published, 2018-2025 upgrades appear only in the full list). (Bad Boys, for example, is absent from it.)

---

## Possible extensions, if asked

- **Fix *Movies in 4K*'s on-sale bias.** Page `OfferList.php?listType=4KMovies` the same
  way `collect_upgraded()` pages `4KUpgraded` (fact 9). Not built yet; untested beyond the
  first page.
- **More catalogs.** Add an entry to `CATALOGS` — manifest and output files are both
  generated from that list, so nothing else needs touching.
- **Other regions/stores.** Change `country` / `store` in `fetch()`. Note `amazon` is US+DE
  only, and `vudu` and `googlePlay` are US only.
