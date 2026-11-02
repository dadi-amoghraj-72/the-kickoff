"""Preview the cricket section as a page.

  .venv/bin/python scripts/preview_cricket.py --espn       saved match list + ESPN's pages live (no key, no CricketData calls): real scorecards and league tables
  .venv/bin/python scripts/preview_cricket.py              from saved real data (no key, no calls): NZ v India has its real scorecard
  .venv/bin/python scripts/preview_cricket.py --live       from CricketData.org (match list: 1 call per 25 matches) and ESPN's scorecard pages (free); CricketData scorecards (10 calls each) only when ESPN has none
add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/cricket.html, --no-open to skip opening it.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket, render, state  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.sources import cricket as src  # noqa: E402
from kickoff.sources import espn_cricket  # noqa: E402

_espn = espn_cricket.Source()
from kickoff.sources import espn  # noqa: E402

if "--live" in sys.argv:
    load_env()
    now = datetime.now(timezone.utc)
    day = now.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Singapore")).date()
    start = espn.window_start(day)
    out = cricket.run(now, start, {"cards": state.load("cricket").get("cards", {})}, src.get_matches, src.get_scorecard, src.scorecards_affordable,
                       espn_card=_espn.card, espn_table=_espn.table, espn_series=_espn.series)
    cricket.persist_cards(out["state"]["cards"])  # keep what was bought, so re-running never pays twice
    note = "Built live: match list from CricketData.org, scorecards from ESPN's pages (CricketData scorecards only as a fallback)."
else:
    fx = ROOT / "tests" / "fixtures"
    matches = json.loads((fx / "cricket_current.json").read_text())
    card = json.loads((fx / "cricket_scorecard_nz_ind.json").read_text())
    now, start = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc), datetime(2026, 10, 31, 23, 15, tzinfo=timezone.utc)

    def get_card(mid):
        if mid != card["id"]:
            raise RuntimeError("not saved")  # only one real scorecard is saved, so the others show as 'not checked'
        return card, 40
    live_espn = "--espn" in sys.argv
    out = cricket.run(now, start, {}, lambda: (matches, 30), get_card, lambda used: 1 if used < 50 else 0,
                      **({"espn_card": _espn.card, "espn_table": _espn.table, "espn_series": _espn.series} if live_espn else {}))
    note = ("Built from the saved match list for 2 November 2026, with scorecards and league tables read live from ESPN." if live_espn
            else "Built from saved real data for 2 November 2026: only the NZ v India match has its scorecard checked.")
if not out["html"]:
    sys.exit("No cricket to report in the window.")
edition = {"date": now.date().isoformat(), "dummy": False, "banner": f"Cricket preview. {note}", "home": "../index.html", "headlines": [],
           "sections": [{"id": "cricket", "title": "Cricket", "html": out["html"]}]}
page = ROOT / "docs" / "demo" / "cricket.html"
page.parent.mkdir(parents=True, exist_ok=True)
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | {out['stats']} | calls used today: {out['used']}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/cricket.html")
    done = git("commit", "-m", "Update cricket demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/cricket.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
