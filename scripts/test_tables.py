"""Offline tests for table change detection. Run: python3 scripts/test_tables.py"""
import copy
import json
import re
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
check("first run shows the full table (20 rows, the header and the title row)", html.count("<tr") == 22, html.count("<tr"))
check("first run saves a snapshot", st["eng.1"]["published"] == "2026-11-04" and len(st["eng.1"]["rows"]) == 20)

# 2. Tuesday is full-table day even when nothing changed
html2, st2 = tables.tables_html({"eng.1": PL}, st, TUE, LEAGUES)
check("Tuesday shows the full table even if unchanged", html2.count("<tr") == 22)

# 3. Unchanged midweek: one line, state untouched
html3, st3 = tables.tables_html({"eng.1": PL}, st2, THU, LEAGUES)
check("unchanged table gives a one-line note", "No change since Tuesday." in html3 and "<table" not in html3, html3[:200])
check("unchanged table leaves the snapshot alone", st3 == st2)

# 4. Changed midweek: top 6 plus the listed clubs outside it
moved = copy.deepcopy(PL)
moved[10]["points"] += 3
html4, st4 = tables.tables_html({"eng.1": moved}, st2, THU, LEAGUES)
check("changed table shows top 6 only (6 rows, the header and the title row 'Table (top 6 only)', D 2026-11-08)", html4.count("<tr") == 8 and '(top 6 only)</th>' in html4, html4.count("<tr"))
outside = [x for x in PL[6:] if tables.is_listed(x["id"])]
check("line names the listed clubs outside the top 6",
      all(tables.code(x["id"]) in html4 for x in outside) and "Other major clubs: " in html4, [x["team"] for x in outside])
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
check("zones: blue, lilac and rose bars, and no legend",
      all(k in html for k in ("z-blue", "z-lilac", "z-rose")) and 'class="legend"' not in html)
check("zone_for maps the labels", [tables.zone_for(x) for x in
      ("Champions League qualifying", "Conference League qualifying", "Relegation playoff", "Relegation", "Relegated", None)]
      == ["blue", "lilac", "lilac", "rose", "rose", None])

# 8. State files round-trip
with tempfile.TemporaryDirectory() as d:
    state.save("tables", st4, Path(d))
    check("state file saves and loads back identically", state.load("tables", directory=Path(d)) == st4)

# ---- Movement arrows (retrofit of 2026-11-03; the pair colours were dropped on 2026-11-04) ----
import re  # noqa: E402
import colorsys  # noqa: E402,F401
txt = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()  # noqa: E731
first_html, first_state = tables.tables_html({"eng.1": PL}, {}, WED, LEAGUES)
check("the table shows the short club names (Man City, Spurs) so six columns fit a 360px screen: 'Manchester City' is not in the page, 'Man City' is", "Man City" in first_html and "Manchester City" not in first_html and "Tottenham Hotspur" not in first_html)
check("the first table ever shown has a +/- column and no arrows (nothing to compare with)", "+/-" in first_html and "▲" not in first_html and "▼" not in first_html)
old_rank = {x["id"]: x["rank"] for x in PL}
ids = [x["id"] for x in PL]
prev_state = {"eng.1": {"published": "2026-11-03", "rows": [[x["id"], x["rank"], x["points"], x["played"]] for x in PL]}}
# last time the teams in places 3 and 4 were swapped and the team in 10th was 12th
a_, b_, c_ = PL[2]["id"], PL[3]["id"], PL[9]["id"]
for e in prev_state["eng.1"]["rows"]:
    if e[0] == a_:
        e[1] = 4
    elif e[0] == b_:
        e[1] = 3
    elif e[0] == c_:
        e[1] = 12
    elif e[0] in (PL[10]["id"], PL[11]["id"]):
        e[1] = e[1] - 1   # shifted by the 10th-for-12th move
        e[3] = e[3] - 1
moved_html, _ = tables.tables_html({"eng.1": PL}, prev_state, TUE, LEAGUES)   # Tuesday: the full table
exp_up = sum(1 for e in prev_state["eng.1"]["rows"] if e[1] > old_rank[e[0]])
exp_dn = sum(1 for e in prev_state["eng.1"]["rows"] if e[1] < old_rank[e[0]])
check("independent: arrows equal last table's rank minus today's, counted separately from the saved rows: as many up arrows as teams that were lower before, as many down arrows as teams that were higher", moved_html.count("▲") == exp_up and moved_html.count("▼") == exp_dn and (exp_up + exp_dn) > 0, (exp_up, exp_dn, moved_html.count("▲"), moved_html.count("▼")))
check("a team that did not move shows a dash (20 rows minus the 5 that moved = 15 dashes); the team in 3rd that was 4th last time shows ▲1 and the one in 10th that was 12th shows ▲2", moved_html.count("–") == 20 - exp_up - exp_dn == 15 and "▲1" in moved_html and "▲2" in moved_html, moved_html.count("–"))
check("an unchanged table is still just 'No change since', no arrows", "No change since" in tables.tables_html({"eng.1": PL}, first_state, THU, LEAGUES)[0])
top6, _ = tables.tables_html({"eng.1": PL}, prev_state, THU, LEAGUES)
check("movement works with the pure helper: movement(x, {id: 4}) for a team now 3rd is ▲1, for one now 3rd that was 3rd is –, with no earlier table it is blank", tables.movement({"id": "a", "rank": 3}, {"a": 4}) == "▲1" and tables.movement({"id": "a", "rank": 3}, {"a": 3}) == "–" and tables.movement({"id": "a", "rank": 3}, None) == "" and tables.movement({"id": "a", "rank": 3}, {"b": 1}) == "" and tables.movement({"id": "a", "rank": 5}, {"a": 2}) == "▼3")
check("no game colours in a league table, full or top-6 view: all white", "gc" not in tables.tables_html({"eng.1": PL}, {}, WED, LEAGUES)[0] and "gc" not in tables.tables_html({"eng.1": PL}, prev_state, THU, LEAGUES)[0] and "<span" not in tables.tables_html({"eng.1": PL}, {}, WED, LEAGUES)[0] and "▲" in tables.tables_html({"eng.1": PL}, prev_state, THU, LEAGUES)[0])

# ---- D, 2026-11-04: Arsenal's row in gold in a league table, nobody else's ----
full = tables.block("Premier League", PL, {"mode": "full"})
ars_row = next(r_ for r_ in full.split("<tr") if "Arsenal" in r_)
check("the Premier League table: Arsenal's row has the gold class", re.search(r'class="[^"]*\bhl\b', ars_row.split(">")[0]) is not None, ars_row[:80])
check("independent: exactly one row in the table has it, and it is the row of the club ESPN lists as Arsenal", len(re.findall(r'<tr class="[^"]*\bhl\b', full)) == 1 and any(x["short"] == "Arsenal" for x in PL), full.count("hl"))
changed = tables.block("Premier League", PL, {"mode": "changed"})
check("the 'top 6' view has it too when Arsenal is in it", changed.count("hl") >= 1 if any(x["short"] == "Arsenal" and x["rank"] <= 6 for x in PL) else True)

_mk = lambda i, team, tid, abbr: {"rank": i, "team": team, "short": team, "id": tid, "abbr": abbr, "played": 8, "gd": 10 - i, "points": 30 - 2 * i, "zone": ""}  # noqa: E731
_wsl = [_mk(1, "Man City", "382x", "MCI"), _mk(2, "Chelsea", "363x", "CHE"), _mk(3, "London City", "1", "LCL"), _mk(4, "Spurs", "367x", "TOT"), _mk(5, "Man Utd", "360x", "MUN"),
        _mk(6, "Brighton", "2", "BHA"), _mk(7, "Aston Villa", "3", "AVL"), _mk(8, "Everton", "4", "EVE"), _mk(9, "Arsenal", "19973", "ARS"), _mk(10, "Liverpool", "364x", "LIV")]
_h = tables.block("Table", _wsl, {"mode": "top6"})
check("D, 2026-11-08: Arsenal outside the top 6 get their own row in the table, set apart and in gold (Arsenal Women 9th in the WSL)",
      _h.count("<tr") == 9 and '<tr class="hl gapabove"><td class="n">9</td><td class="">Arsenal</td>' in _h and "Aston Villa" not in _h, _h[-600:])
check("and are not repeated in the 'Other major clubs' line", "Other major clubs" not in _h or "ARS" not in _h.split("Other major clubs")[1])
_top = tables.block("Table", [_wsl[8]] + _wsl[:8], {"mode": "top6"})
check("Arsenal inside the top 6: no extra row", _top.count("gapabove") == 0)
print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
