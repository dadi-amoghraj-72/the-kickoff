"""Save a real cricket morning from ESPN's JSON feeds as a test fixture (D, 2026-11-08): the header feed, each series scoreboard the run reads and every match's
summary (the scorecard source that works from GitHub), trimmed of commentary, news and pictures. scripts/test_cricket_feed.py replays it with ESPN's web pages blocked
and no Mac cache, exactly as GitHub sees cricket.

  .venv/bin/python scripts/save_cricket_summary_fixtures.py tests/fixtures/cricket_feed_2026-11-08.json"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket  # noqa: E402
from kickoff import http  # noqa: E402
from kickoff.sources import espn_cricket  # noqa: E402

KEEP = ("header", "rosters", "standings")


def trim(x):
    """Drop the long commentary text and links; keep every number."""
    if isinstance(x, dict):
        return {k: trim(v) for k, v in x.items() if k not in ("text", "links", "logos", "images", "media", "$ref", "href", "headshot", "flag")}
    if isinstance(x, list):
        return [trim(v) for v in x]
    return x


saved = {}


def record(url, *a, **k):
    got = http.get_json(url, *a, **k)
    saved[url] = trim({k_: v for k_, v in got.items() if k_ in KEEP}) if "/summary?" in url else got
    return got


matches = cricket.espn_matches(espn_cricket.Feed(get_json=record))
src = espn_cricket.Source(fetch_json=record)
for m in matches:
    if m.get("series") and m.get("event") and m.get("score"):
        src.feed_card(m)
Path(sys.argv[1]).write_text(json.dumps(saved, ensure_ascii=False, separators=(",", ":")))
print(f"saved {len(saved)} responses, {Path(sys.argv[1]).stat().st_size // 1024} KB")
