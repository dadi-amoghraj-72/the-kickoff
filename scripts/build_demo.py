"""Build a demo page of the Arsenal and Football sections from live data, into docs/demo/index.html.

  .venv/bin/python scripts/build_demo.py                      plain text, free, no Claude: builds the page and OPENS it in your browser
  .venv/bin/python scripts/build_demo.py --claude             with Claude's notes and news (a few cents to ~30 cents)
  .venv/bin/python scripts/build_demo.py --claude --publish   ... and also puts it on the website (the phone link)
  .venv/bin/python scripts/build_demo.py 2026-10-22 --claude  a past date, e.g. a Champions League night
  add --no-open to build without opening the browser
  add --showcase to show EVERYTHING on one page whatever day it is: football, cricket, F1 and tennis are live as usual, and the NFL (a Wednesday wrap),
    the NBA (Sunday 1 November's games) and MLB (a weekly round-up) are replayed from saved real days, so their sections are always there

The demo shows the FPL deadline reminder, squad alerts and transfer hints even when the deadline is far off.
The demo uses a private copy of the state in preview/demo-state/, so the real state files are never changed.
Tables and FPL data are always as of now, so a past date mixes old results with current tables.
"""
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket, cricketcache, football, render, settings, state  # noqa: E402
from kickoff.sources import cricket as cricket_source  # noqa: E402
from kickoff.sources import espn_cricket  # noqa: E402

_espn = espn_cricket.Source()
from kickoff.sources import espn  # noqa: E402
from kickoff import f1, mlb, nba, nfl, tennis  # noqa: E402
from kickoff.sources import espn_mlb, espn_nba, espn_nfl, espn_tennis, feeds, jolpica  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
day = date.fromisoformat(args[0]) if args else datetime.now(ZoneInfo("Asia/Singapore")).date()
use_claude = "--claude" in sys.argv

demo_state = ROOT / "preview" / "demo-state"
shutil.rmtree(demo_state, ignore_errors=True)
if (ROOT / "data" / "state").exists():
    shutil.copytree(ROOT / "data" / "state", demo_state)
names = ["tables", "clean_sheets", "injuries", "fpl", "news_seen", "costs", "top30", "cricket"]
st = {n: state.load(n, directory=demo_state) for n in names}

load_env()
client = None
if use_claude:
    import anthropic
    client = anthropic.Anthropic()
out = football.run(day, client=client, st=st, now=datetime.now(timezone.utc), demo=True)

# Cricket: only when the key is available, and always within the free daily call budget (no Claude involved).
cricket_stats = None
if os.environ.get("CRICKET_DATA_API_KEY") and "--no-cricket" not in sys.argv:
    try:
        now = datetime.now(timezone.utc)
        _cc = cricketcache.getters(cricketcache.fresh(cricketcache.load(), now), _espn)   # the Mac's cache first, then ESPN's pages (they fail quietly on GitHub)
        c = cricket.run(now, espn.window_start(day), {"cards": state.load("cricket").get("cards", {})}, cricket_source.get_matches, cricket_source.get_scorecard,
                        cricket_source.scorecards_affordable, espn_card=_cc[0], espn_table=_cc[1], espn_series=_cc[2],
                        espn_extra=lambda ms: cricket.espn_matches(espn_cricket.Feed()))
        cricket_stats = {**c["stats"], "calls_used_today": c["used"]}
        cricket.persist_cards(c["state"]["cards"])  # into the real state: bought scorecards are never paid for twice
        if c["html"]:
            out["sections"].append({"id": "cricket", "title": "Cricket", "html": c["html"]})
    except Exception as e:
        out["problems"].append(f"cricket ({type(e).__name__})")
# F1: free, no key. Reads the real API; nothing is saved (a demo never uses up what the daily edition would report).
if "--no-f1" not in sys.argv:
    try:
        api = jolpica.Api()
        got = f1.run(datetime.now(timezone.utc), espn.window_start(day), {}, api)
        if got["html"]:
            out["sections"].append({"id": "f1", "title": "F1", "html": got["html"]})
    except Exception as e:
        out["problems"].append(f"f1 ({type(e).__name__})")
# Tennis: free, no key, no Claude. Real data; nothing is saved. Only a Grand Slam in progress (or a top-10 withdrawal headline) shows anything.
if "--no-tennis" not in sys.argv:
    try:
        got = tennis.run(datetime.now(timezone.utc), {}, espn_tennis.Source(), fetch_news=lambda: feeds.fetch_all(tennis.FEEDS))
        if got["html"]:
            out["sections"].append({"id": "tennis", "title": "Tennis", "html": got["html"]})
    except Exception as e:
        out["problems"].append(f"tennis ({type(e).__name__})")
# NFL: free, no key, no Claude. Real data; nothing is saved. What shows depends on today's Singapore weekday (Monday, Tuesday, Wednesday, Saturday).
if "--no-nfl" not in sys.argv:
    try:
        got = nfl.run(datetime.now(timezone.utc), day, {}, espn_nfl.Source())
        if got["html"]:
            out["sections"].append({"id": "nfl", "title": "NFL", "html": got["html"]})
    except Exception as e:
        out["problems"].append(f"nfl ({type(e).__name__})")
# NBA: free, no key, no Claude. Real data; nothing is saved (so every finished game of the last 60 hours counts as new).
if "--no-nba" not in sys.argv:
    try:
        got = nba.run(datetime.now(timezone.utc), day, {}, espn_nba.Source())
        if got["html"]:
            out["sections"].append({"id": "nba", "title": "NBA", "html": got["html"]})
    except Exception as e:
        out["problems"].append(f"nba ({type(e).__name__})")
# MLB: free, no key, no Claude. Real data; nothing is saved. Quiet except on Thursdays in the season, from the Dodgers' 155th game, and in the postseason.
if "--no-mlb" not in sys.argv:
    try:
        got = mlb.run(datetime.now(timezone.utc), day, {}, espn_mlb.Source())
        if got["html"]:
            out["sections"].append({"id": "mlb", "title": "MLB", "html": got["html"]})
    except Exception as e:
        out["problems"].append(f"mlb ({type(e).__name__})")
if "--showcase" in sys.argv:
    import re
    for sid, title, cmd, page in (("nfl", "NFL", ["preview_nfl.py", "--day", "wed"], "nfl-wed.html"), ("nba", "NBA", ["preview_nba.py"], "nba.html"),
                                  ("mlb", "MLB", ["preview_mlb.py", "--weekly"], "mlb-weekly.html")):
        subprocess.run([sys.executable, str(ROOT / "scripts" / cmd[0])] + cmd[1:] + ["--no-open"], cwd=ROOT, capture_output=True, text=True)
        m = re.search(rf'<section id="{sid}"><h2>[^<]*</h2>(.*?)</section>', (ROOT / "docs" / "demo" / page).read_text(), re.S)
        if m:
            out["sections"] = [x for x in out["sections"] if x["id"] != sid] + [{"id": sid, "title": title, "html": m.group(1)}]
    rank = {k: i for i, k in enumerate(("arsenal", "football", "cricket", "nba", "nfl", "mlb", "f1", "tennis"))}
    out["sections"].sort(key=lambda x: rank.get(x["id"], 99))
if not out["sections"]:
    sys.exit("Nothing to show for this date. Problems: " + ", ".join(out["problems"]))
banner = (f"Football preview built from real data for {render.nice_date(day.isoformat())}. "
          + ("Written with Claude. " if use_claude else "Plain text, no AI. ")
          + "The FPL deadline reminder and transfer hints are shown here even if the deadline is far off. "
          + ("Showcase: football, cricket, F1 and tennis are live from today; the NFL, NBA and MLB are replayed from saved real days so they are always shown. " if "--showcase" in sys.argv else "")
          + "Football, cricket, F1, tennis, NFL, NBA and MLB are built (MLB is quiet out of season); Young Guns, Around the sporting world and the cross-sport sections are not yet.")
edition = {"date": day.isoformat(), "dummy": False, "banner": banner, "home": "../index.html",
           "headlines": out["headlines"], "sections": out["sections"]}
(ROOT / "docs" / "demo").mkdir(parents=True, exist_ok=True)
(ROOT / "docs" / "demo" / "index.html").write_text(render.render_edition(edition))

led = out["ledger"]
print(f"Edition {day} | {'with Claude' if use_claude else 'plain, no Claude'} | sections: {', '.join(s['id'] for s in out['sections'])}")
print("Results found:", out["stats"]["matches"], "| Champions League matches:", out["stats"]["cl_matches"])
print(f"News: {out['stats']['news_candidates']} candidates, {out['stats']['news_shown']} shown | injury items: {out['stats']['injury_items']}")
print("Headlines:", out["headlines"])
if cricket_stats:
    print("Cricket:", cricket_stats)
if out["problems"]:
    print("Parts that failed (the rest was built):", ", ".join(out["problems"]))
if led.rows:
    print("\nClaude calls:")
    print("\n".join(led.lines()))
print(f"Total cost this build: ${led.total():.4f}")
page = ROOT / "docs" / "demo" / "index.html"
print(f"\nWrote {page.relative_to(ROOT)}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/index.html")
    done = git("commit", "-m", f"Update demo page ({day})")
    if done.returncode != 0 and "nothing to commit" in (done.stdout + done.stderr):
        print("Nothing new to publish: the page is the same as the one already online.")
    elif done.returncode != 0:
        print("Could not commit:", (done.stderr or done.stdout).strip()[:300])
    else:
        pushed = git("push", "origin", "main")
        print("Published." if pushed.returncode == 0 else "Committed, but the push failed: " + pushed.stderr.strip()[:300])
        if pushed.returncode == 0:
            print("It goes live in about 30 seconds at: https://dadi-amoghraj-72.github.io/the-kickoff/demo/")
