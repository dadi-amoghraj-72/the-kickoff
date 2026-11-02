"""Offline tests for the Champions League block. Run: .venv/bin/python scripts/test_champions.py"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import champions  # noqa: E402
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
check("a line reads home, score, away (both listed clubs in bold)", '<span class="h"><span class="mine">Como</span></span><span class="s">4–1</span><span><span class="mine">Man Utd</span></span>' in html, html[:300])
check("no matches, no scoreboard", champions.scores_html([]) == "")

# ---- Scorecard for Arsenal ----
bay = next(m for m in wed if m["home"]["name"] == "Bayern Munich")
check("scorers: each side lists its own goals, with penalties tagged",
      (champions.scorers(bay, "home"), champions.scorers(bay, "away")) == ("Davies 35', Kane 61' (pen)", "Eze 25', Rice 82'"),
      (champions.scorers(bay, "home"), champions.scorers(bay, "away")))
og = {"goals": [{"side": "home", "player": "Nikola Milenkovic", "minute": "30'", "own_goal": True, "penalty": False}]}
two = {"goals": [{"side": "home", "player": "Nico Paz", "minute": "2'", "own_goal": False, "penalty": False},
                 {"side": "home", "player": "Anastasios Douvikas", "minute": "49'", "own_goal": False, "penalty": False},
                 {"side": "home", "player": "Nico Paz", "minute": "57'", "own_goal": False, "penalty": True}]}
check("a player who scores twice is listed once, with both minutes (tags per goal)", champions.scorers(two, "home") == "Paz 2', 57' (pen), Douvikas 49'", champions.scorers(two, "home"))
check("each scorer is kept together on one line", champions.scorers_html(two, "home").count('class="p"') == 2)
check("an own goal is listed under the team it counted for, tagged (OG)", champions.scorers(og, "home") == "Milenkovic 30' (OG)" and champions.scorers(og, "away") == "")
with_goals = sum(1 for m in wed for side in ("home", "away") if champions.scorers(m, side))
check("every match with goals gets a scorecard, each side under its own team",
      html.count('class="gh"') + html.count('class="ga"') == with_goals and with_goals >= 12, (html.count('class="gh"'), html.count('class="ga"'), with_goals))
row = next(x for x in html.split("<li>") if "Arsenal" in x)
check("Arsenal's scorecard shows both teams' scorers under their own side",
      "Davies 35&#x27;</span>, <span class=\"p\">Kane 61&#x27; (pen)" in row.split('class="ga"')[0] and "Eze 25&#x27;</span>, <span class=\"p\">Rice 82&#x27;" in row.split('class="ga"')[1], row)
listed_sides = sum(1 for m in wed for side in ("home", "away") if m[side]["id"] in champions.scoreboard_highlight)
check("every listed club's name is in bold in the scoreboard, and nobody else's",
      '<span class="mine">Arsenal</span>' in html and html.count('class="mine"') == listed_sides >= 5 and '<span class="mine">Lille</span>' not in html, (html.count('class="mine"'), listed_sides))
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

# ---- Movement arrows and game colours in the league-phase table (retrofit of 2026-11-03) ----
import re as _re  # noqa: E402
t0 = champions.table_html(rows)
check("the league-phase table has a +/- column, blank when there is no earlier table", "+/-" in t0 and "▲" not in t0 and "▼" not in t0)
before = {x["id"]: x["rank"] for x in rows}
before[rows[0]["id"]], before[rows[1]["id"]] = 2, 1   # last time the top two were the other way round
before[rows[20]["id"]] = 25                           # and the team now 21st was 25th
t1 = champions.table_html(rows, before)
check("arrows against the last table: 1st is up 1, 2nd down 1, 21st up 4, everyone else level (33 dashes)", t1.count("▲1") == 1 and t1.count("▼1") == 1 and t1.count("▲4") == 1 and t1.count("–") == 33, (t1.count("▲"), t1.count("▼"), t1.count("–")))
cm = {rows[0]["id"]: 0, rows[17]["id"]: 0, rows[3]["id"]: 1, rows[30]["id"]: 1}
t2 = champions.table_html(rows, None, cm)
sp = _re.findall(r'<span class="gc(\d)">([^<]+)</span>', t2)
check("teams of tonight's matches are coloured in pairs: 4 teams, two colours, nobody else", len(sp) == 4 and {n for _, n in sp} == {rows[i]["short"] for i in (0, 17, 3, 30)} and len({c for c, _ in sp}) == 2, sp)

# ---- Knockout ties as series tables (last season's real Arsenal v Leverkusen round of 16 and the final, saved from ESPN) ----
import re as _re2  # noqa: E402
from kickoff.sources import espn as _espn  # noqa: E402
KS = json.loads((FIX / "espn_cl_ko_schedule.json").read_text())
KSUM = json.loads((FIX / "espn_cl_ko_summaries.json").read_text())
LEG2 = json.loads((FIX / "espn_cl_ko_20260317.json").read_text())["events"][0]
FINAL = json.loads((FIX / "espn_cl_final_20260530.json").read_text())["events"][0]
_old_get = _espn.get_json


def _fake_get(url, params=None, **kw):
    if "schedule" in url:
        return KS
    if "summary" in url:
        return KSUM[params["event"]]
    raise AssertionError(url)


_espn.get_json = _fake_get
m2 = _espn.parse_match(LEG2, _espn.CHAMPIONS_LEAGUE)
legs = _espn.get_tie_legs(m2)
raw_ties = [e for e in KS["events"] if {c["team"]["abbreviation"] for c in e["competitions"][0]["competitors"]} == {"ARS", "B04"}]
check("independent: ESPN's own schedule has exactly two Arsenal v Leverkusen matches (11 and 17 March 2026) and the code finds those two legs, in date order", len(raw_ties) == 2 and [g["id"] for g in legs] == [e["id"] for e in sorted(raw_ties, key=lambda e: e["date"])], [g["id"] for g in legs])
check("the first leg was at Leverkusen (1-1) and the second at Arsenal (2-0), as the raw scores say", (legs[0]["home"]["abbr"], legs[0]["home_score"], legs[0]["away_score"]) == ("B04", 1, 1) and (legs[1]["home"]["abbr"], legs[1]["home_score"], legs[1]["away_score"]) == ("ARS", 2, 0), legs)
agg = champions.aggregate(legs)
esp = {k: v for k, v in legs[1]["agg"].items()}
check("independent: the aggregate counted from the legs (Arsenal 3, Leverkusen 1) equals ESPN's own aggregateScore on the second leg", {k: float(v) for k, v in agg.items()} == esp and sorted(agg.values()) == [1, 3], (agg, esp))
tie = champions.tie_html("round-of-16", legs, lambda leg_id: _espn.get_match_details(leg_id, _espn.CHAMPIONS_LEAGUE)["goals"])
tt = _re2.sub(r"\s+", " ", _re2.sub(r"<[^>]+>", " ", tie)).strip()
check("the tie table: title 'Round of 16', the first leg's hosts (Bayer 04 Leverkusen) on the left with their aggregate 1, the word 'aggregate', Arsenal's 3 on the right", tt.startswith("Round of 16 ") and "1 aggregate 3" in tt and tt.index("Leverkusen") < tt.index("Arsenal"), tt[:160])
check("two game rows with the matchday as played in Europe (11 March, 17 March), the scores 1-1 and 0-2 in the left/right order (left = Leverkusen), the winner of the second leg in bold", "1st leg · 11 Mar" in tt and "2nd leg · 17 Mar" in tt and tie.count('<tr class="one') == 2 and tie.count('class="hm w"') == 1 and tie.count('class="aw w"') == 0 and "1 1st leg · 11 Mar 1" in tt and "0 2nd leg · 17 Mar 2" in tt, tt[:300])
raw_goals = sum(1 for d in KSUM[legs[0]["id"]]["header"]["competitions"][0]["details"] if d.get("scoringPlay")) + sum(1 for d in KSUM[legs[1]["id"]]["header"]["competitions"][0]["details"] if d.get("scoringPlay"))
check("independent: the scorers under the legs are every scoring play of the two raw summaries (4 goals), the 1-1 leg's goals listed under their own teams", raw_goals == 4 and tie.count('class="p"') == 4, (raw_goals, tie.count('class="p"')))
first_only = champions.tie_html("round-of-16", legs[:1], None)
ft_ = _re2.sub(r"\s+", " ", _re2.sub(r"<[^>]+>", " ", first_only))
check("after the first leg only: the aggregate is that leg's score (1 aggregate 1) and the second leg's row is already there, marked 'to be scheduled' when no date is known", "1 aggregate 1" in ft_ and first_only.count("pre") == 1 and "2nd leg · to be scheduled" in ft_, ft_)
sched_leg = dict(legs[1], completed=False, home_score=0, away_score=0, kickoff="2026-03-17T20:00Z")
upcoming = _re2.sub(r"\s+", " ", _re2.sub(r"<[^>]+>", " ", champions.tie_html("round-of-16", [legs[0], sched_leg], None)))
check("a second leg still to play shows its date and kick-off in Singapore time (17 March 20:00 UTC is 4:00am on 18 March)", "2nd leg · 18 Mar, 4:00am SGT" in upcoming, upcoming)
fm = _espn.parse_match(FINAL, _espn.CHAMPIONS_LEAGUE)
fl = _espn.get_tie_legs(fm)
ftie = champions.tie_html("final", fl, None)
fts = _re2.sub(r"\s+", " ", _re2.sub(r"<[^>]+>", " ", ftie))
raw_final = FINAL["competitions"][0]["competitors"]
check("independent: the final is one match, 1-1 after extra time, Paris Saint-Germain winning the shoot-out 4-3 by the raw feed; the table says 'final', not 'aggregate', and shows a Penalties row 4-3", fl[0]["pens"] is not None and sorted(fl[0]["pens"]) == [3, 4] and len(fl) == 1 and "final" in fts and "aggregate" not in fts and "Penalties" in fts and ftie.count('<tr class="one') == 2, fts[:200])
check("the winning shoot-out side is in bold on the Penalties row (PSG, the home team in the final)", ftie.count('class="aw w"') + ftie.count('class="hm w"') >= 1)
_espn.get_json = _old_get
sec = champions.section_html([m2], rows, None, "", legs_fn=lambda m: legs, goals_fn=lambda i: {"goals": []})
check("in the Champions League block a knockout match gets its tie table and no separate scoreboard line", 'class="nflsb nbaone ser"' in sec and "<ul class=\"scores\">" not in sec and "aggregate" in sec)
check("without a schedule feed (legs_fn None) the old scoreboard line is shown, and so it is when the feed fails or finds nothing", "<ul class=\"scores\">" in champions.section_html([m2], rows) and "<ul class=\"scores\">" in champions.section_html([m2], rows, legs_fn=lambda m: 1 / 0) and "<ul class=\"scores\">" in champions.section_html([m2], rows, legs_fn=lambda m: []))
lp = [x for x in wed][:2]
check("league-phase matches are untouched: with a feed available they still get the scoreboard lines and no tie table", 'class="nflsb' not in champions.section_html(lp, rows, legs_fn=lambda m: legs) and champions.section_html(lp, rows, legs_fn=lambda m: legs).count("<li>") == 2)

# ---- Bold team names ----
check("bold_names bolds both clubs, wherever they appear",
      r.bold_names("Como beat Manchester United. Como led.", ("Como", "Manchester United")) ==
      "<strong>Como</strong> beat <strong>Manchester United</strong>. <strong>Como</strong> led.")
check("bold_names copes with possessives and ampersands",
      r.bold_names("Brighton & Hove Albion's win.", ("Brighton & Hove Albion",)) == "<strong>Brighton &amp; Hove Albion</strong>&#x27;s win.")
check("bold_names also bolds an unambiguous first word ('LASK' for 'LASK Linz')",
      r.bold_names("LASK came from behind.", ("LASK Linz", "Sporting CP")) == "<strong>LASK</strong> came from behind.")
check("bold_names does not bold an ambiguous first word (two Manchester clubs)",
      "<strong>" not in r.bold_names("Manchester was busy.", ("Manchester City", "Manchester United")))
check("bold_names does not bold a bare 'Real' or 'Inter'", "<strong>" not in r.bold_names("Real and Inter won.", ("Real Madrid", "Real Betis", "Internazionale")))
check("bold_names never double-bolds overlapping names", r.bold_names("Manchester United won.", ("United", "Manchester United")).count("<strong>") == 1)
check("bold_names escapes everything else", r.bold_names("<b>x</b> Como", ("Como",)) == "&lt;b&gt;x&lt;/b&gt; <strong>Como</strong>")
check("render.table adds row classes after the zone", 'class="z-blue cut mine"' in r.table("t", [("a", False)], [["x"]], zones=["blue"], row_classes=["cut mine"]))

# ---- The whole block ----
text = "Como beat Manchester United 4-1, and Sporting went down to LASK."
full = champions.section_html(wed, rows, text)
check("block: heading, then the overview with bold team names, then the scoreboard, then the table",
      full.index("Champions League") < full.index("<strong>Como</strong> beat <strong>Manchester United</strong>") < full.index('class="scores"') < full.index("<table"))
check("short names are bolded in the overview too", "<strong>Sporting</strong> went down to <strong>LASK</strong>" in full, full[:400])
check("no overview given: the scoreboard and table still appear", 'class="scores"' in champions.section_html(wed, rows) and "<strong>" not in champions.section_html(wed, rows)[:60])
check("no matches, no block", champions.section_html([], rows, text) == "")
ko = champions.section_html([{**m, "stage": "round-of-16"} for m in wed], rows)
check("knockout matchday: scores but no league-phase table", 'class="scores"' in ko and "<table" not in ko)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
