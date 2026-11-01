"""Offline tests for table change detection. Run: python3 scripts/test_tables.py"""
import copy
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import state, tables  # noqa: E402
from kickoff.sources import espn  # noqa: E402

espn.get_json = lambda url, params=None, **kw: json.loads((ROOT / "tests/fixtures/espn_pl_table.json").read_text())
PL = espn.get_table("eng.1")
LEAGUES = {"eng.1": "Premier League"}
TUE, WED, THU = date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)
results = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


# 1. No saved state yet: show the full table and remember it
html, st = tables.tables_html({"eng.1": PL}, {}, WED, LEAGUES)
check("first run shows the full table (20 rows)", html.count("<tr") == 21, html.count("<tr"))
check("first run saves a snapshot", st["eng.1"]["published"] == "2026-11-04" and len(st["eng.1"]["rows"]) == 20)

# 2. Tuesday is full-table day even when nothing changed
html2, st2 = tables.tables_html({"eng.1": PL}, st, TUE, LEAGUES)
check("Tuesday shows the full table even if unchanged", html2.count("<tr") == 21)

# 3. Unchanged midweek: one line, state untouched
html3, st3 = tables.tables_html({"eng.1": PL}, st2, THU, LEAGUES)
check("unchanged table gives a one-line note", "No change since Tuesday." in html3 and "<table" not in html3, html3[:200])
check("unchanged table leaves the snapshot alone", st3 == st2)

# 4. Changed midweek: top 6 plus the listed clubs outside it
moved = copy.deepcopy(PL)
moved[10]["points"] += 3
html4, st4 = tables.tables_html({"eng.1": moved}, st2, THU, LEAGUES)
check("changed table shows top 6 only (7 rows with the header)", html4.count("<tr") == 7, html4.count("<tr"))
outside = [x for x in PL[6:] if tables.is_listed(x["id"])]
check("line names the listed clubs outside the top 6",
      all(tables.code(x["id"]) in html4 for x in outside) and "Your clubs outside the top 6" in html4, [x["team"] for x in outside])
check("changed table updates the snapshot to today", st4["eng.1"]["published"] == "2026-11-05")
check("'No change since' now uses the new publish day",
      "since Thursday" in tables.tables_html({"eng.1": moved}, st4, date(2026, 11, 6), LEAGUES)[0])

# 5. A failed source shows 'No data' and keeps the old snapshot
html5, st5 = tables.tables_html({"eng.1": None}, st2, THU, LEAGUES)
check("failed source shows 'No data this morning'", "No data this morning" in html5)
check("failed source keeps the old snapshot", st5 == st2)

# 6. WSL appears on Tuesdays only
wsl = {"eng.w.1": "WSL"}
check("WSL skipped on a Wednesday", tables.tables_html({"eng.w.1": PL}, {}, WED, wsl, tuesday_only=("eng.w.1",))[0] == "")
check("WSL shown on a Tuesday", "<table" in tables.tables_html({"eng.w.1": PL}, {}, TUE, wsl, tuesday_only=("eng.w.1",))[0])

# 7. Zone bars and legend
check("zones: blue, lilac and rose bars with a legend",
      all(k in html for k in ("z-blue", "z-lilac", "z-rose", "Relegation")))
check("zone_for maps the labels", [tables.zone_for(x) for x in
      ("Champions League qualifying", "Conference League qualifying", "Relegation playoff", "Relegation", "Relegated", None)]
      == ["blue", "lilac", "lilac", "rose", "rose", None])

# 8. State files round-trip
with tempfile.TemporaryDirectory() as d:
    state.save("tables", st4, Path(d))
    check("state file saves and loads back identically", state.load("tables", directory=Path(d)) == st4)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
