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

# ---- Scorecard for Arsenal ----
bay = next(m for m in wed if m["home"]["name"] == "Bayern Munich")
check("scorers: each side lists its own goals, with penalties tagged",
      (champions.scorers(bay, "home"), champions.scorers(bay, "away")) == ("Davies 35', Kane 61' (pen)", "Eze 25', Rice 82'"),
      (champions.scorers(bay, "home"), champions.scorers(bay, "away")))
og = {"goals": [{"side": "home", "player": "Nikola Milenkovic", "minute": "30'", "own_goal": True, "penalty": False}]}
check("an own goal is listed under the team it counted for, tagged (og)", champions.scorers(og, "home") == "Milenkovic 30' (og)" and champions.scorers(og, "away") == "")
check("the scoreboard gives only Arsenal's match a scorecard", html.count('class="gh"') + html.count('class="ga"') == 2, (html.count('class="gh"'), html.count('class="ga"')))
check("Arsenal's scorecard shows both teams' scorers under their own side",
      "Davies 35&#x27;, Kane 61&#x27; (pen)" in html.split('class="ga"')[0] and "Eze 25&#x27;, Rice 82&#x27;" in html and html.index("Davies") < html.index("Eze"))
check("Arsenal's name is marked in the scoreboard", '<span class="mine">Arsenal</span>' in html and html.count('class="mine"') == 1)
check("a goalless scorecard side shows nothing", "<span class=\"ga\">" not in champions.scores_html([{**bay, "goals": [g for g in bay["goals"] if g["side"] == "home"]}]))

# ---- Table: the whole thing ----
t = champions.table_html(rows)
check("the full table: header + 36 rows", t.count("<tr") == 37, t.count("<tr"))
check("zone bars: 8 blue, 16 lilac, 12 rose", (t.count("z-blue"), t.count("z-lilac"), t.count("z-rose")) == (8, 16, 12), (t.count("z-blue"), t.count("z-lilac"), t.count("z-rose")))
check("a heavier line marks the cuts after 8th and 24th only", t.count("cut") == 2 and rows[7]["team"] in t.split("cut")[0][-400:] + t.split("cut")[1][:400])
listed = [x for x in rows if champions.is_listed(x["id"])]
check("listed clubs are bold-marked, nobody else", t.count("mine") == len(listed) and len(listed) >= 5, (t.count("mine"), len(listed)))
check("caption has the matchday", "League Phase After Matchday 3" in t)
check("no legend and none of the old text lines", all(x not in t for x in ("legend", "Your clubs", "cut line", "play off")))
check("a table that is too short is left out", champions.table_html(rows[:10]) == "")
check("zones", [champions.zone(n) for n in (1, 8, 9, 24, 25, 36)] == ["blue", "blue", "lilac", "lilac", "rose", "rose"])

# ---- Bold team names ----
check("bold_names bolds both clubs, wherever they appear",
      r.bold_names("Como beat Manchester United. Como led.", ("Como", "Manchester United")) ==
      "<strong>Como</strong> beat <strong>Manchester United</strong>. <strong>Como</strong> led.")
check("bold_names copes with possessives and ampersands",
      r.bold_names("Brighton & Hove Albion's win.", ("Brighton & Hove Albion",)) == "<strong>Brighton &amp; Hove Albion</strong>&#x27;s win.")
check("bold_names never double-bolds overlapping names", r.bold_names("Manchester United won.", ("United", "Manchester United")).count("<strong>") == 1)
check("bold_names escapes everything else", r.bold_names("<b>x</b> Como", ("Como",)) == "&lt;b&gt;x&lt;/b&gt; <strong>Como</strong>")
check("render.table adds row classes after the zone", 'class="z-blue cut mine"' in r.table("t", [("a", False)], [["x"]], zones=["blue"], row_classes=["cut mine"]))

# ---- The whole block ----
written = {m["id"]: {"note": "Como beat Manchester United 4-1."} for m, _ in picked[:1]}
full = champions.section_html(wed, rows, written)
check("block: heading, scoreboard, the note with bold names, then the table",
      full.index("Champions League") < full.index('class="scores"') < full.index("<strong>Como</strong> beat <strong>Manchester United</strong>") < full.index("<table"))
check("no matches, no block", champions.section_html([], rows, {}) == "")
ko = champions.section_html([{**m, "stage": "round-of-16"} for m in wed], rows, {})
check("knockout matchday: scores but no league-phase table", 'class="scores"' in ko and "<table" not in ko)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
