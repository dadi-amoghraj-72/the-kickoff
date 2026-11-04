"""Preview how a Test match reads, on the real South Africa v Australia 3rd Test (Cape Town, 27 to 31 October 2026), from saved ESPN pages. No key, no calls.

  .venv/bin/python scripts/preview_cricket_test.py            writes docs/demo/cricket-test-day3.html and docs/demo/cricket-test-final.html
  add --publish to put them at https://dadi-amoghraj-72.github.io/the-kickoff/demo/cricket-test-day3.html and ...-final.html, --no-open to skip opening them.

Final day: the real finished match (all four innings, South Africa won by 176 runs): the first two innings are one line each (shown on earlier days), the third and
fourth in full, then the series table with the whole series. Day 3: a layout mock built from the REAL first two innings (South Africa 329, Australia 429) with the
day and the lead as our assumption: ESPN keeps no day-by-day snapshots, so the status line 'Day 3: Stumps, Australia lead by 100 runs' is ours. No series table
while the Test is on."""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket, render  # noqa: E402
from kickoff.sources import espn_cricket as ec  # noqa: E402

FX = ROOT / "tests" / "fixtures"
PAGE, SERIES = (FX / "espn_cricket_scorecard_sa_aus_test.html").read_text(), (FX / "espn_cricket_series_sa_aus.html").read_text()


def build(ended, upto=4, status=None, from_innings=0):
    """The Test's cricket block: `upto` innings so far, `ended` for the finished match."""
    card, meta = ec.parse_scorecard(PAGE)[:upto], ec.parse_meta(PAGE)
    score = [{"inning": inn["inning"].replace(" 1st Innings", " Inning 1").replace(" 2nd Innings", " Inning 2"), "r": inn["espn"]["total"]["r"], "w": inn["espn"]["total"]["w"],
              "o": inn["espn"]["total"]["o"]} for inn in card]
    m = {"id": "sa-aus-3", "name": "South Africa vs Australia, 3rd Test, Australia tour of South Africa 2026", "matchType": "test", "teams": ["South Africa", "Australia"],
         "matchStarted": True, "matchEnded": ended, "status": status or meta["status"], "score": score, "dateTimeGMT": "2026-10-27T08:30:00"}
    m["class"] = cricket.classify(m)
    entry = {"innings": cricket.slim_card({"scorecard": card}, m), "standouts": [], "potm": meta["potm"] if ended else [], "status": m["status"]}
    series = cricket.series_html(ec.parse_series(SERIES), "test", current=m) if ended else ""
    return cricket.results_html([m], {m["id"]: entry}, {}, {m["id"]: series} if series else {}, {m["id"]: from_innings})


pages = {"cricket-test-day3": build(False, upto=2, status="Day 3: Stumps - Australia lead by 100 runs", from_innings=1),
         "cricket-test-final": build(True, upto=4, from_innings=2)}
notes = {"cricket-test-day3": "LAYOUT MOCK of day 3: the first two innings are real; the day and the lead are our assumption (ESPN keeps no day-by-day snapshots). Innings 1 is one line (shown on day 2), innings 2 in full, no series table.",
         "cricket-test-final": "The real finished Test: innings 1 and 2 one line each (shown on earlier days), innings 3 and 4 in full, then the series table."}
for name, html in pages.items():
    edition = {"date": "2026-10-31", "dummy": False, "banner": notes[name], "home": "../index.html", "headlines": [], "sections": [{"id": "cricket", "title": "Cricket", "html": html}]}
    out = ROOT / "docs" / "demo" / f"{name}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render.render_edition(edition))
    print("Built", out.relative_to(ROOT))
    if "--no-open" not in sys.argv and sys.platform == "darwin":
        subprocess.run(["open", str(out)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/cricket-test-day3.html", "docs/demo/cricket-test-final.html")
    done = git("commit", "-m", "Update cricket Test demo pages")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/cricket-test-final.html and ...-day3.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
