"""Build a demo page of the Arsenal and Football sections from live data, into docs/demo/index.html.

  .venv/bin/python scripts/build_demo.py                      plain text, free, no Claude (shows layout and all the data)
  .venv/bin/python scripts/build_demo.py --claude             with Claude's notes, overviews and news (a few cents to ~30 cents)
  .venv/bin/python scripts/build_demo.py 2026-10-22 --claude  a past date, e.g. a Champions League night

The demo uses a private copy of the state in preview/demo-state/, so the real state files are never changed.
Tables and FPL data are always as of now, so a past date mixes old results with current tables.
"""
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import football, render, settings, state  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
day = date.fromisoformat(args[0]) if args else datetime.now(ZoneInfo("Asia/Singapore")).date()
use_claude = "--claude" in sys.argv

demo_state = ROOT / "preview" / "demo-state"
shutil.rmtree(demo_state, ignore_errors=True)
if (ROOT / "data" / "state").exists():
    shutil.copytree(ROOT / "data" / "state", demo_state)
names = ["tables", "clean_sheets", "injuries", "fpl", "news_seen", "costs"]
st = {n: state.load(n, directory=demo_state) for n in names}

client = None
if use_claude:
    import anthropic
    load_env()
    client = anthropic.Anthropic()
out = football.run(day, client=client, st=st, now=datetime.now(timezone.utc))

if not out["sections"]:
    sys.exit("Nothing to show for this date. Problems: " + ", ".join(out["problems"]))
banner = (f"Football preview built from real data for {render.nice_date(day.isoformat())}. "
          + ("Written with Claude. " if use_claude else "Plain text, no AI. ")
          + "Cricket, F1, tennis, NFL, NBA and the other sections are not built yet.")
edition = {"date": day.isoformat(), "dummy": False, "banner": banner, "home": "../index.html",
           "headlines": out["headlines"], "sections": out["sections"]}
(ROOT / "docs" / "demo").mkdir(parents=True, exist_ok=True)
(ROOT / "docs" / "demo" / "index.html").write_text(render.render_edition(edition))

led = out["ledger"]
print(f"Edition {day} | {'with Claude' if use_claude else 'plain, no Claude'} | sections: {', '.join(s['id'] for s in out['sections'])}")
print("Results found:", out["stats"]["matches"], "| Champions League matches:", out["stats"]["cl_matches"])
print(f"News: {out['stats']['news_candidates']} candidates, {out['stats']['news_shown']} shown | injury items: {out['stats']['injury_items']}")
print("Headlines:", out["headlines"])
if out["problems"]:
    print("Parts that failed (the rest was built):", ", ".join(out["problems"]))
if led.rows:
    print("\nClaude calls:")
    print("\n".join(led.lines()))
print(f"Total cost this build: ${led.total():.4f}")
print("\nWrote docs/demo/index.html  (open it on this Mac with: open docs/demo/index.html)")
