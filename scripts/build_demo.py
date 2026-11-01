"""Build a demo page of the Arsenal and Football sections from live data, into docs/demo/index.html.

  .venv/bin/python scripts/build_demo.py                      plain text, free, no Claude: builds the page and OPENS it in your browser
  .venv/bin/python scripts/build_demo.py --claude             with Claude's notes and news (a few cents to ~30 cents)
  .venv/bin/python scripts/build_demo.py --claude --publish   ... and also puts it on the website (the phone link)
  .venv/bin/python scripts/build_demo.py 2026-10-22 --claude  a past date, e.g. a Champions League night
  add --no-open to build without opening the browser

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
from kickoff import cricket, football, render, settings, state  # noqa: E402
from kickoff.sources import cricket as cricket_source  # noqa: E402
from kickoff.sources import espn  # noqa: E402
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
        c = cricket.run(now, espn.window_start(day), st.get("cricket") or {}, cricket_source.get_matches, cricket_source.get_scorecard,
                        cricket_source.scorecards_affordable)
        cricket_stats = {**c["stats"], "calls_used_today": c["used"]}
        if c["html"]:
            out["sections"].append({"id": "cricket", "title": "Cricket", "html": c["html"]})
    except Exception as e:
        out["problems"].append(f"cricket ({type(e).__name__})")
if not out["sections"]:
    sys.exit("Nothing to show for this date. Problems: " + ", ".join(out["problems"]))
banner = (f"Football preview built from real data for {render.nice_date(day.isoformat())}. "
          + ("Written with Claude. " if use_claude else "Plain text, no AI. ")
          + "The FPL deadline reminder and transfer hints are shown here even if the deadline is far off. "
          + "F1, tennis, NFL, NBA and the other sections are not built yet.")
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
