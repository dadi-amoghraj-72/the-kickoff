"""Preview the NBA section as a page.

  .venv/bin/python scripts/preview_nba.py            from saved real data: the 11 games of Saturday 31 October and Sunday 1 November 2026, as the Tuesday 3 November edition shows them
  .venv/bin/python scripts/preview_nba.py --live     from ESPN right now, for today's Singapore date (about 12 to 25 calls)
add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/nba.html, --no-open to skip opening it.
Nothing is saved either way. No Claude, no key, no cost.
"""
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
else:
    load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
    sbs, boxes, std, car = load("nba_scoreboards.json"), load("nba_boxes.json"), load("nba_standings.json"), load("nba_careers.json")
    day = date(2026, 11, 3)
    now = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)

    class Saved:
        calls = 0
        scoreboard = lambda self, d: sbs.get(str(d), {"events": []})  # noqa: E731
        box = lambda self, event_id: boxes[event_id]  # noqa: E731
        career = lambda self, athlete_id: car[athlete_id]  # noqa: E731
        standings = lambda self: std  # noqa: E731
    source, st = Saved(), {}
    note = f"Built from saved real data: the 11 games of 31 October and 1 November 2026 as the {day:%A %-d %B} edition would show them."
out = nba.run(now, day, st, source)
if not out["html"]:
    sys.exit(f"Nothing to show for {day:%A} ({out['stats']}).")
edition = {"date": day.isoformat(), "dummy": False, "banner": f"NBA preview. {note}", "home": "../index.html", "headlines": [],
           "sections": [{"id": "nba", "title": "NBA", "html": out["html"]}]}
page = ROOT / "docs" / "demo" / "nba.html"
page.parent.mkdir(parents=True, exist_ok=True)
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | {out['stats']}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/nba.html")
    done = git("commit", "-m", "Update NBA demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/nba.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
