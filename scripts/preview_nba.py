"""Preview the NBA section as a page.

  .venv/bin/python scripts/preview_nba.py            from saved real data: the 11 games of Saturday 31 October and Sunday 1 November 2026, as the Tuesday 3 November edition shows them
  .venv/bin/python scripts/preview_nba.py --inprogress       the same, with the last game still being played when the edition goes out
  .venv/bin/python scripts/preview_nba.py --playoffs         last season's real Detroit-Orlando first-round series (2026): the whole series as it stood after game 7
  .venv/bin/python scripts/preview_nba.py --playoffs-mid     the same series as it stood the morning after game 3 (later games still to come)
  .venv/bin/python scripts/preview_nba.py --live     from ESPN right now, for today's Singapore date (about 12 to 25 calls)
add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/nba.html, --no-open to skip opening it.
Nothing is saved either way. No Claude, no key, no cost.
"""
import copy
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import nba, render  # noqa: E402
from kickoff.sources import espn_nba  # noqa: E402

FX = ROOT / "tests" / "fixtures"
if "--live" in sys.argv:
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
    source, st = espn_nba.Source(), {}
    note = f"Built live from ESPN for {day:%A %-d %B}."
elif any(a.startswith("--playoffs") for a in sys.argv):
    load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
    sched, boxes, std = load("nba_series_schedule.json"), load("nba_series_boxes.json"), load("nba_standings.json")
    mid = "--playoffs-mid" in sys.argv
    if mid:  # keep games 1 to 3 as played; the rest are still to come
        sched = [g if i < 3 else {**g, "status": "STATUS_SCHEDULED", "home": {**g["home"], "score": None}, "away": {**g["away"], "score": None}} for i, g in enumerate(sched)]
    now = datetime(2026, 4, 26, 0, 0, tzinfo=timezone.utc) if mid else datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)
    day = date(2026, 4, 26) if mid else date(2026, 5, 4)
    from kickoff.nfl import utc  # noqa: E402

    def event(g):  # a scoreboard event rebuilt from a schedule row
        side = lambda t, ha: {"homeAway": ha, "score": str(t["score"]) if t["score"] is not None else "0", "records": [], "team": {"id": t["id"], "abbreviation": t["abbr"], "displayName": t["name"], "shortDisplayName": t["short"]}}  # noqa: E731
        final = g["status"] == "STATUS_FINAL"
        return {"id": g["id"], "date": g["date"], "season": {"year": 2026, "type": 3}, "status": {"period": 4, "type": {"name": g["status"], "state": "post" if final else "pre"}},
                "competitions": [{"neutralSite": False, "notes": [{"headline": g["headline"]}], "series": None, "type": {}, "competitors": [side(g["home"], "home"), side(g["away"], "away")]}]}

    class Saved:
        calls = 0
        scoreboard = lambda self, d: {"events": [event(g) for g in sched if utc(g["date"]).astimezone(nba.ET).date() == d]}  # noqa: E731
        box = lambda self, event_id: boxes[event_id]  # noqa: E731
        schedule = lambda self, team_id, season=None, season_type=3: sched  # noqa: E731
        standings = lambda self: std  # noqa: E731
    source, st = Saved(), {}
    note = f"Built from last season's real data: the 2026 Detroit-Orlando first-round series as it stood on {day:%A %-d %B %Y} (" + ("after game 3, later games still to come" if mid else "after game 7") + ")."
else:
    load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
    sbs, boxes, std, window = load("nba_scoreboards.json"), load("nba_boxes.json"), load("nba_standings.json"), load("nba_window.json")
    day = date(2026, 11, 3)
    now = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)

    class Saved:
        calls = 0
        scoreboard = lambda self, d: sbs.get(str(d)) or window.get(str(d), {"events": []})  # noqa: E731
        box = lambda self, event_id: boxes[event_id]  # noqa: E731
        standings = lambda self: std  # noqa: E731
    sunday = [g for g in sbs["2026-11-01"]["events"]]
    if "--inprogress" in sys.argv:  # the last Sunday game is still being played when the edition goes out
        live = copy.deepcopy(sunday[-1])
        live["status"] = {"period": 3, "type": {"name": "STATUS_IN_PROGRESS", "state": "in", "shortDetail": "4:12 - 3rd Quarter"}}
        for c in live["competitions"][0]["competitors"]:
            c["score"] = str(int(c["score"]) - 38)
        sbs["2026-11-01"] = {**sbs["2026-11-01"], "events": sunday[:-1] + [live]}
    source = Saved()
    # the Monday edition showed Saturday's seven games, so this Tuesday edition shows what finished since: Sunday's four
    st = {"reported": [e["id"] for e in sbs["2026-10-31"]["events"]]}
    note = f"Built from saved real data as the {day:%A %-d %B} edition would show it: Sunday 1 November's games (Saturday's were in Monday's edition)" + (", one still in progress." if "--inprogress" in sys.argv else ".")
out = nba.run(now, day, st, source)
if not out["html"]:
    sys.exit(f"Nothing to show for {day:%A} ({out['stats']}).")
edition = {"date": day.isoformat(), "dummy": False, "banner": f"NBA preview. {note}", "home": "../index.html", "headlines": [],
           "sections": [{"id": "nba", "title": "NBA", "html": out["html"]}]}
page = ROOT / "docs" / "demo" / ("nba-playoffs-mid.html" if "--playoffs-mid" in sys.argv else "nba-playoffs.html" if "--playoffs" in sys.argv else "nba-live.html" if "--inprogress" in sys.argv else "nba.html")
page.parent.mkdir(parents=True, exist_ok=True)
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | {out['stats']}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", f"docs/demo/{page.name}")
    done = git("commit", "-m", "Update NBA demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        print(f"Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/{page.name}" if git("push", "origin", "main").returncode == 0 else "Push failed.")
