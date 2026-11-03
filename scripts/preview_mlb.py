"""Preview the MLB section as a page, from the saved real 2026 season (it is over, so every mode is shown as it would have looked on a given morning).

  .venv/bin/python scripts/preview_mlb.py --weekly      the Thursday 7 May 2026 round-up (the Dodgers' week to Wednesday; the tables are the final 2026 ones)
  .venv/bin/python scripts/preview_mlb.py --daily       Monday 21 September 2026: past the Dodgers' 155th game, so every game of the league
  .venv/bin/python scripts/preview_mlb.py --start       Sunday 4 October 2026: the division series begin (four series, game 1 each)
  .venv/bin/python scripts/preview_mlb.py --nlcs        Saturday 17 October 2026: the Dodgers' NLCS ends, 0-4
  .venv/bin/python scripts/preview_mlb.py --finale      Friday 30 October 2026: the World Series is decided and the season is closed
  .venv/bin/python scripts/preview_mlb.py --live        from ESPN right now, for today's Singapore date
add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/mlb-<name>.html, --no-open to skip opening it.
Nothing is saved either way. No Claude, no key, no cost."""
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import mlb, render  # noqa: E402
from kickoff.nfl import utc  # noqa: E402
from kickoff.sources import espn_mlb  # noqa: E402
from mlb_saved import Saved  # noqa: E402

MODES = {"--weekly": ("weekly", datetime(2026, 5, 7, tzinfo=timezone.utc), "the Thursday round-up of 7 May 2026 (the Dodgers' week to Wednesday night)"),
         "--daily": ("daily", datetime(2026, 9, 21, tzinfo=timezone.utc), "Monday 21 September 2026, past the Dodgers' 155th game: every game of the league"),
         "--start": ("start", datetime(2026, 10, 4, tzinfo=timezone.utc), "Sunday 4 October 2026: game 1 of each division series"),
         "--nlcs": ("nlcs", datetime(2026, 10, 17, tzinfo=timezone.utc), "Saturday 17 October 2026: the Dodgers' NLCS ends 0-4"),
         "--finale": ("finale", datetime(2026, 10, 30, tzinfo=timezone.utc), "Friday 30 October 2026: game 5 of the World Series and the end of the season")}
mode = next((MODES[a] for a in sys.argv if a in MODES), None)
if "--live" in sys.argv:
    now = datetime.now(timezone.utc)
    name, source, st = "live", espn_mlb.Source(), {}
    note = f"Built live from ESPN for {now.astimezone(ZoneInfo('Asia/Singapore')):%A %-d %B}."
elif mode:
    name, now, what = mode
    source = Saved(now)
    st = {}
    if name == "weekly":     # the Thursday before has already shown everything up to 30 April
        st = {"opened": 2026, "week_reported": [x["id"] for x in source.lad if utc(x["date"]) < now - timedelta(days=7)]}
    note = f"Built from saved real data as the {what} would show it. The standings tables are the final 2026 ones."
else:
    sys.exit(__doc__)
day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
out = mlb.run(now, day, st, source)
if not out["html"]:
    sys.exit(f"Nothing to show for {day:%A} ({out['stats']}).")
edition = {"date": day.isoformat(), "dummy": False, "banner": f"MLB preview. {note}", "home": "../index.html", "headlines": [],
           "sections": [{"id": "mlb", "title": "MLB", "html": out["html"]}]}
page = ROOT / "docs" / "demo" / f"mlb-{name}.html"
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
    done = git("commit", "-m", "Update MLB demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        print(f"Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/{page.name}" if git("push", "origin", "main").returncode == 0 else "Push failed.")
