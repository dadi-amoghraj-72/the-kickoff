"""Preview the NFL section as a page.

  .venv/bin/python scripts/preview_nfl.py                  from saved real data: week 8 of 2026 as the Monday 2 November edition shows it
  .venv/bin/python scripts/preview_nfl.py --day wed        the same saved week as a Wednesday wrap (all games so far, division tables)
  .venv/bin/python scripts/preview_nfl.py --week14         the saved standings with the playoff picture switched on (as a Wednesday of week 14)
  .venv/bin/python scripts/preview_nfl.py --live           from ESPN right now, for today's Singapore weekday (about 20 calls)
add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/nfl.html (Monday view) or nfl-wed.html (Wednesday views), --no-open to skip opening it.
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
from kickoff import nfl, render  # noqa: E402
from kickoff.sources import espn_nfl  # noqa: E402

FX = ROOT / "tests" / "fixtures"
if "--live" in sys.argv:
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
    source, st = espn_nfl.Source(), {}
    note = f"Built live from ESPN for {day:%A %-d %B}."
else:
    load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
    sb, boxes, pos, standings = load("nfl_w8_scoreboard.json"), load("nfl_w8_boxes.json"), load("nfl_w8_positions.json"), load("nfl_w8_standings.json")
    wed = "--day" in sys.argv and sys.argv[sys.argv.index("--day") + 1].lower().startswith("wed") or "--week14" in sys.argv
    day = date(2026, 11, 4) if wed else date(2026, 11, 2)
    now = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)

    class Saved:
        calls = 0
        scoreboard = lambda self, week=None, season_type=None: {**sb, "week": {**sb["week"], "number": 14} if "--week14" in sys.argv else sb["week"]}  # noqa: E731
        box = lambda self, event_id: boxes[event_id]  # noqa: E731
        roster = lambda self, team_id: {}  # noqa: E731
        standings = lambda self: standings  # noqa: E731
    source, st = Saved(), {"positions": pos}
    note = f"Built from saved real data: NFL week 8 of 2026 as the {day:%A %-d %B} edition would show it (12 of 14 games played at the time)."
out = nfl.run(now, day, st, source)
if not out["html"]:
    sys.exit(f"Nothing to show for {day:%A} ({out['stats']}).")
edition = {"date": day.isoformat(), "dummy": False, "banner": f"NFL preview. {note}", "home": "../index.html", "headlines": [],
           "sections": [{"id": "nfl", "title": "NFL", "html": out["html"]}]}
name = "nfl-wed.html" if day.weekday() == 2 else "nfl.html"
page = ROOT / "docs" / "demo" / name
page.parent.mkdir(parents=True, exist_ok=True)
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | {out['stats']}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", f"docs/demo/{name}")
    done = git("commit", "-m", "Update NFL demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        print(f"Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/{name}" if git("push", "origin", "main").returncode == 0 else "Push failed.")
