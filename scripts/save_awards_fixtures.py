"""Re-save the awards test fixtures from ESPN (real data, no key). Run: .venv/bin/python scripts/save_awards_fixtures.py
Records every request the awards code makes for the NBA 2026 awards (season 2025-26), the NFL 2025 awards and the MLB 2026 awards so far, with the athlete and team
lookups for their winners, into tests/fixtures/espn_awards.json ({url: response}); the tests replay it. The seasons are over (MLB's is still being announced,
so its fixture is a snapshot of 4 November 2026)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import http  # noqa: E402
from kickoff.sources import espn_awards  # noqa: E402

rec = {}


def get(url):
    rec[url] = http.get_json(url)
    return rec[url]


for sport, league, season, empty in (("basketball", "nba", 2026, 2027), ("football", "nfl", 2025, 2026), ("baseball", "mlb", 2026, None)):
    s = espn_awards.Source(sport, league, get_json=get, pause=0.1)
    got = s.awards(season)
    for a in got:
        for w in a["winners"]:
            s.athlete(season, w["athlete"])
            if w["team"]:
                s.team(season, w["team"])
    if empty:
        s.awards(empty)                      # the season about to start: nothing announced yet
    print(league, season, len(got), "awards;", s.calls, "calls")
(ROOT / "tests" / "fixtures" / "espn_awards.json").write_text(json.dumps(rec))
print("saved", len(rec), "responses")
