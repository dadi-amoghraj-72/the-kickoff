"""Offline tests for the Champions League block. Run: .venv/bin/python scripts/test_champions.py"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import champions, notes  # noqa: E402
from kickoff import render as r  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
load = lambda n: json.loads((FIX / n).read_text())  # noqa: E731
DAYS = {"20261020": "espn_cl_20261020.json", "20261021": "espn_cl_20261021.json"}


def fake_get_json(url, params=None, **kw):
    if "standings" in url:
        return load("espn_cl_table.json")
    name = DAYS.get(params["dates"])
    return load(name) if name else {"events": []}


espn.get_json = fake_get_json
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


tue = champions.results(date(2026, 10, 21))   # Wednesday's edition: Tuesday's matches
wed = champions.results(date(2026, 10, 22))   # Thursday's edition: Wednesday's matches
check("each matchday edition holds that day's nine matches", (len(tue), len(wed)) == (9, 9), (len(tue), len(wed)))
check("a non-matchday edition is empty", champions.results(date(2026, 10, 25)) == [])
check("matches are marked league phase, and clubs carry short names", champions.in_league_phase(wed) and bool(wed[0]["home"]["short"]))
check("a knockout match is not league phase", not champions.in_league_phase([{**wed[0], "stage": "round-of-16"}]))

rows = espn.get_table(espn.CHAMPIONS_LEAGUE)
check("the table has 36 teams", len(rows) == 36, len(rows))

# ---- Scoreboard ----
html = champions.scores_html(wed)
check("one scoreboard line per match", html.count("<li>") == 9)
como = next(m for m in wed if m["home"]["short"] == "Como")
check("a line reads home, score, away", '<span class="h">Como</span><span class="s">4–1</span><span>Man Utd</span>' in html, html[:300])
check("no matches, no scoreboard", champions.scores_html([]) == "")

# ---- Which matches get a note ----
picked = champions.note_facts(wed, rows)
tiers = {m["id"]: f["length"] for m, f in picked}
check("Como v Man Utd (two listed clubs) gets the fuller length", tiers.get(como["id"]) == notes.TIERS["derby"][0], tiers)
check("Arsenal's match is left to the Arsenal section", all("Arsenal" not in (m["home"]["name"], m["away"]["name"]) for m, _ in picked))
check("every note is about a listed club", all(any(champions.is_listed(i) for i in (m["home"]["id"], m["away"]["id"])) for m, _ in picked))
check("facts name the competition and carry both teams' positions", all(f["competition"] == champions.COMPETITION and "table" in f for _, f in picked))

# ---- Table ----
t = champions.table_html(rows)
check("table: header + 8 + gap + cut line = 11 rows", t.count("<tr") == 11, t.count("<tr"))
check("table has a gap row and caption with the matchday", 'class="gap"' in t and "League Phase After Matchday 3" in t)
check("zone bars: top 8 blue, 24th lilac", t.count("z-blue") == 8 and t.count("z-lilac") == 1, (t.count("z-blue"), t.count("z-lilac")))
check("24th place is named in full as the cut line", rows[23]["team"] in t and f"{rows[23]['points']} points" in t and "cut line" in t)
shown = {x["id"] for x in rows[:8]} | {rows[23]["id"]}
elsewhere = [x for x in rows if champions.is_listed(x["id"]) and x["id"] not in shown]
check("'your clubs' lists only listed clubs the table doesn't already show",
      all(champions.code(x["id"], x["abbr"]) in t for x in elsewhere) and ("Your clubs elsewhere" in t) == bool(elsewhere), [x["team"] for x in elsewhere])
check("a table that is too short is left out", champions.table_html(rows[:10]) == "")
check("zones", [champions.zone(n) for n in (1, 8, 9, 24, 25, 36)] == ["blue", "blue", "lilac", "lilac", "rose", "rose"])

# ---- The whole block ----
written = {m["id"]: {"note": "Como beat Manchester United 4-1."} for m, _ in picked[:1]}
full = champions.section_html(wed, rows, written)
check("block: heading, scoreboard, the note, then the table", full.index("Champions League") < full.index('class="scores"') < full.index("Como beat") < full.index("<table"))
check("no matches, no block", champions.section_html([], rows, {}) == "")
ko = champions.section_html([{**m, "stage": "round-of-16"} for m in wed], rows, {})
check("knockout matchday: scores but no league-phase table", 'class="scores"' in ko and "<table" not in ko)
check("render.table draws a gap row for None", '<tr class="gap">' in r.table("t", [("a", False)], [["x"], None, ["y"]]))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
