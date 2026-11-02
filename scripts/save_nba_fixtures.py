"""Re-save the NBA test fixtures from ESPN (real data, no key). Run: .venv/bin/python scripts/save_nba_fixtures.py
Saves: the finished games of 31 October and 1 November 2026 with their box scores and the standings; every game of the 2026-27 Cup window with
only the fields the code reads; and last season's Detroit-Orlando first-round series (schedule, box scores, one day's scoreboard)."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff.sources import espn_nba  # noqa: E402

FX = ROOT / "tests" / "fixtures"
s = espn_nba.Source()
dump = lambda name, obj: (FX / name).write_text(json.dumps(obj))  # noqa: E731


def slim(e):
    c = e["competitions"][0]
    return {"id": e["id"], "date": e["date"], "season": e["season"], "status": e["status"],
            "competitions": [{"neutralSite": c.get("neutralSite"), "notes": c.get("notes", []), "series": c.get("series"), "type": c.get("type"),
                              "competitors": [{"homeAway": x["homeAway"], "score": x.get("score"), "records": x.get("records", []),
                                               "team": {k: x["team"][k] for k in ("id", "abbreviation", "displayName", "shortDisplayName")}} for x in c["competitors"]]}]}


days = [date(2026, 10, 31), date(2026, 11, 1)]
sbs = {str(d): s.scoreboard(d) for d in days}
dump("nba_scoreboards.json", sbs)
dump("nba_boxes.json", {e["id"]: s.box(e["id"]) for sb in sbs.values() for e in sb["events"] if e["status"]["type"]["name"] == "STATUS_FINAL"})
dump("nba_standings.json", s.standings())
cup, d = {}, date(2026, 10, 20)
while d <= date(2026, 12, 20):
    cup[str(d)] = {"events": [slim(e) for e in s.scoreboard(d)["events"]]}
    d += timedelta(days=1)
dump("nba_window.json", cup)
sched = s.schedule("19", 2026)
dump("nba_series_schedule.json", sched)
dump("nba_series_boxes.json", {g["id"]: s.box(g["id"]) for g in sched})
dump("nba_series_scoreboard.json", {"2026-05-03": {"events": [slim(e) for e in s.scoreboard(date(2026, 5, 3))["events"]]}})
print("saved; calls:", s.calls)
