"""Preview the league tables for an edition date, using live data.

  python3 scripts/check_tables.py 2026-11-03     (a Tuesday: full tables)
  python3 scripts/check_tables.py 2026-11-04     (next day: 'No change' or top 6)

Writes preview/tables.html and remembers what it showed in preview/state/ (not the real state files).
Pass --reset to forget the preview memory first.
"""
import os
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import render, state, tables  # noqa: E402
from kickoff.http import safe  # noqa: E402
from kickoff.sources import espn  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
day = date.fromisoformat(args[0])
preview = ROOT / "preview"
if "--reset" in sys.argv:
    shutil.rmtree(preview / "state", ignore_errors=True)

leagues = {**espn.LEAGUES, espn.WSL: "WSL"}
fetched = {lg: safe(f"{name} table", espn.get_table, lg) for lg, name in leagues.items()}
saved = state.load("tables", directory=preview / "state")
html, new_state = tables.tables_html(fetched, saved, day, leagues, tuesday_only=(espn.WSL,))
state.save("tables", new_state, preview / "state")

for lg, name in leagues.items():
    rows = fetched[lg]
    mode = "FAILED" if rows is None else tables.decide(rows, saved.get(lg), day, lg == espn.WSL)["mode"]
    print(f"{name:15} -> {mode}")

preview.mkdir(exist_ok=True)
body = f"<main>{render._masthead(render.nice_date(day.isoformat()))}<section><h2>Tables</h2>{html}</section></main>"
(preview / "tables.html").write_text(render._page("Tables preview", "", body))
print("\nWrote preview/tables.html")
