"""The cricket cache: scorecards, points tables and series tables that only ESPN's web pages have, collected on D's Mac and read by the daily run.

Why: from GitHub's servers ESPN's cricket pages come back empty (HTTP 202) and Cricinfo answers 403; from a home connection they work. So a small job on the Mac
Mini (scripts/cricket_collect.py, about 6:50am Singapore time) reads the pages and saves what it finds in data/cricket_cache.json, which it commits. The 7:15 daily
run on GitHub uses those entries (by match id) and falls back to the live pages, which fail quietly there. If the Mac was off, the cache is simply old or empty and
the edition has result lines and scores without the batting and bowling cards: it never depends on the Mac.

File: {"cards": {match id: {"built", "scorecard", "status", "potm"}}, "tables": {league label: {"built", "rows"}}, "series": {match id: {"built", "rows"}}}.
Entries older than MAX_AGE_DAYS are ignored and dropped on the next save."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "cricket_cache.json"
MAX_AGE_DAYS = 4
KINDS = ("cards", "tables", "series")


def stamp(now):
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path=None):
    """The cache as saved, or an empty one when there is no file or it cannot be read."""
    path = path or PATH
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    return {k: dict(data.get(k) or {}) for k in KINDS}


def fresh(cache, now, max_age_days=MAX_AGE_DAYS):
    """The cache without entries older than `max_age_days` (or with no valid stamp)."""
    limit = now - timedelta(days=max_age_days)
    out = {}
    for kind in KINDS:
        out[kind] = {}
        for key, entry in (cache.get(kind) or {}).items():
            try:
                built = datetime.strptime(entry["built"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except (KeyError, ValueError, TypeError):
                continue
            if built >= limit:
                out[kind][key] = entry
    return out


def save(cache, path=None):
    path = path or PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def getters(cache, source=None):
    """(card, table, series) functions for cricket.run: each looks in the cache first (by match id, or league label for a table), then asks `source`
    (espn_cricket.Source, which fails quietly from GitHub), then gives None. The card returned has the shape espn_cricket.Source.card gives."""
    def card(m):
        e = cache["cards"].get(m["id"])
        if e:
            return {"scorecard": e["scorecard"], "status": e.get("status", ""), "potm": e.get("potm", [])}
        return source.card(m) if source else None

    def table(m):
        e = cache["tables"].get(m["class"]["label"]) if m.get("class") else None
        return e["rows"] if e else (source.table(m) if source else None)

    def series(m):
        e = cache["series"].get(m["id"])
        return e["rows"] if e else (source.series(m) if source else None)
    return card, table, series


def collect(picked, source, now, cache=None):
    """Read the pages for each picked match (cricket.pick's output, each with a "class") from `source` and return the updated cache: a consistent scorecard for
    every match, a points table once per league that played, a series table for each match that has one. Anything a page does not give is left as it was."""
    from kickoff import cricket
    cache = fresh(cache or {"cards": {}, "tables": {}, "series": {}}, now)
    built, done = stamp(now), set()
    for m in picked:
        card = source.card(m)
        if card and card.get("scorecard"):
            if cricket.card_consistent(card, m):
                cache["cards"][m["id"]] = {"built": built, "scorecard": card["scorecard"], "status": card.get("status", ""), "potm": card.get("potm", [])}
            else:
                cache["cards"].pop(m["id"], None)          # a page that contradicts the match (a stale copy) also removes an older entry for it
        label = m["class"]["label"]
        if m["class"]["kind"] == "league" and label not in done:           # once per league per run: the table changes with every match
            done.add(label)
            rows = source.table(m)
            if rows:
                cache["tables"][label] = {"built": built, "rows": rows}
        if m.get("matchType") in cricket.SERIES_FORMATS:
            rows = source.series(m)
            if rows:
                cache["series"][m["id"]] = {"built": built, "rows": rows}
    return cache
