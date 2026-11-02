"""Preview the Grand Slam tennis section as a page.

  .venv/bin/python scripts/preview_tennis.py                      from saved real data: the 2026 Australian Open as the edition of 27 January would show it
  .venv/bin/python scripts/preview_tennis.py --date 2026-01-21    the same Slam as of another day (the saved data runs 18 January to 1 February 2026)
  .venv/bin/python scripts/preview_tennis.py --news               add the top-10 withdrawal check from the BBC, Guardian and ESPN tennis feeds (live news)
  .venv/bin/python scripts/preview_tennis.py --live               from ESPN right now: whatever Slam is on (none in November: the next is the Australian Open in January)
add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/tennis.html, --no-open to skip opening it.
Nothing is saved either way: a preview never uses up what the daily edition would report. No Claude, no key, no cost.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import render, tennis  # noqa: E402
from kickoff.sources import espn_tennis, feeds  # noqa: E402

news = (lambda: feeds.fetch_all(tennis.FEEDS)) if "--news" in sys.argv or "--live" in sys.argv else None  # noqa: E731
if "--live" in sys.argv:
    now = datetime.now(timezone.utc)
    source = espn_tennis.Source()
    note = "Built live from ESPN's tennis scoreboard."
else:
    day = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else "2026-01-27"
    now = datetime.fromisoformat(day).replace(hour=12, tzinfo=timezone.utc)
    event = json.loads((ROOT / "tests" / "fixtures" / "espn_tennis_ao.json").read_text())["events"][0]

    class Saved:
        calls = 0
        slam_events = lambda self, when: [event]  # noqa: E731
        top10 = lambda self, tour: ["Jannik Sinner", "Carlos Alcaraz"]  # noqa: E731
    source = Saved()
    note = f"Built from saved real data: the 2026 Australian Open as the edition of {now:%-d %B} would show it (matches from the three days before, all in one go)."
out = tennis.run(now, {}, source, fetch_news=news)
if not out["html"]:
    sys.exit(f"Nothing to show right now ({out['stats']}, Slams running: {out['slams']}). The Slams are Australian Open (January), Roland-Garros (May to June), Wimbledon (late June to July) and the US Open (late August to September).")
edition = {"date": now.date().isoformat(), "dummy": False, "banner": f"Tennis preview. {note}", "home": "../index.html", "headlines": [],
           "sections": [{"id": "tennis", "title": "Tennis", "html": out["html"]}]}
page = ROOT / "docs" / "demo" / "tennis.html"
page.parent.mkdir(parents=True, exist_ok=True)
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | {out['stats']} | Slams: {out['slams']}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/tennis.html")
    done = git("commit", "-m", "Update tennis demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/tennis.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
