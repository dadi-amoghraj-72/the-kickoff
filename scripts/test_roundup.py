"""Offline tests for the round-up box. Run: .venv/bin/python scripts/test_roundup.py"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import overview, roundup  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
ODDS = json.loads((FIX / "espn_cl_odds_20261021.json").read_text())
SCORES = json.loads((FIX / "espn_cl_20261021.json").read_text())
TABLE = json.loads((FIX / "espn_cl_table.json").read_text())
espn.get_json = lambda url, params=None, **kw: TABLE if "standings" in url else (ODDS[params["event"]] if "/summary" in url else SCORES)
MS = espn.get_matches_on("uefa.champions", date(2026, 10, 21))
ROWS = espn.get_table("uefa.champions")
FACTS = overview.matchday_facts("UEFA Champions League", MS, overview.collect_odds("uefa.champions", MS), ROWS)
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


text = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()  # noqa: E731
L = roundup.lines(FACTS, len(ROWS) // 2, "night")
check("the Champions League round is 18 games (36 teams), so this window is 9/18", L[0] == ("Games played", "9/18", ""), L[0])
check("favourites won: 5 of the 6 clear favourites", L[1] == ("Favourites won", "5/6", ""), L[1])
check("biggest upset: Sporting 2-3 LASK, with the favourite's pre-match chance",
      L[2] == ("Biggest upset", "", "Sporting CP 2-3 LASK Linz (Sporting CP had a 70% chance)"), L[2])
check("game of the night: the match, its goals, and that it was a comeback", L[3] == ("Game of the night", "", "Sporting CP 2-3 LASK Linz · 5 goals · comeback"), L[3])
check("the same four lines in the same order every time", [x[0] for x in L] == ["Games played", "Favourites won", "Biggest upset", "Game of the night"])
one_goal = {**FACTS, "matches": [{**FACTS["matches"][0], "total_goals": 1}], "game_of_the_night": FACTS["matches"][0]["match"]}
check("one goal is '1 goal', not '1 goals'", roundup.lines(one_goal, 10)[-1][2].endswith("· 1 goal"), roundup.lines(one_goal, 10)[-1])
check("a domestic league says 'day' not 'night'", roundup.lines(FACTS, 10, "day")[3][0] == "Game of the day")

h = roundup.html(FACTS, 18, "night")
check("the box is a four-row list with the figures highlighted", h.count("<li>") == 4 and h.count('class="n"') == 2 and h.startswith('<ul class="roundup">'), h[:200])
check("it reads cleanly as text", text(h).startswith("Games played 9/18 Favourites won 5/6 Biggest upset Sporting CP 2-3 LASK Linz"), text(h))

# ---- Where we are in the season ----
league = lambda played: [{"played": p} for p in played]  # noqa: E731
mon = roundup.round_info(league([9] * 18 + [8] * 2), "Game week")
check("Monday: 18 of 20 teams are on 9 games, so Game week 9/38 and 9 of 10 played", (mon["number"], mon["total"], mon["so_far"], mon["size"]) == (9, 38, 9, 10), mon)
check("the round is finished when every team is on the same number: 10/10", roundup.round_info(league([9] * 20))["so_far"] == 10)
check("a new round has begun: two teams on 10 games, so Game week 10 and 1 of 10", (lambda i: (i["number"], i["so_far"]))(roundup.round_info(league([10] * 2 + [9] * 18))) == (10, 1))
check("a postponed game does not break the count: 19 teams on 9 games is still 9 of 10", roundup.round_info(league([9] * 19 + [8]))["so_far"] == 9)
check("an 18-team league has 34 rounds and 9 games a round", (lambda i: (i["total"], i["size"]))(roundup.round_info(league([5] * 18))) == (34, 9))
cl = roundup.round_info(ROWS, "Matchday", 8)
check("Champions League: Matchday 3/8 with all 18 games of the matchday played", (cl["label"], cl["number"], cl["total"], cl["so_far"], cl["size"]) == ("Matchday", 3, 8, 18, 18), cl)
check("no table, no season row", roundup.round_info([]) is None and roundup.round_info(None) is None)
L2 = roundup.lines(FACTS, 18, "night", cl)
check("with the season info the box gets a first row, and games played shows today's and the round's count",
      L2[0] == ("Matchday", "3/8", "") and L2[1] == ("Games played", "9/18", "[18/18 so far this matchday]"), L2[:2])
sunday = roundup.lines({**FACTS, "matches": FACTS["matches"][:3]}, 10, "day", mon)
check("D's example: a Monday with 3 games played and 9 of 10 done this game week", sunday[1] == ("Games played", "3/10", "[9/10 so far this game week]"), sunday[1])
check("the box is the same five rows in the same order", [x[0] for x in roundup.lines(FACTS, 18, "night", cl)] == ["Matchday", "Games played", "Favourites won", "Biggest upset", "Game of the night"])
check("without season info the box is the old four rows", len(roundup.lines(FACTS, 18, "night")) == 4)

# ---- Edge cases ----
no_upset = {**FACTS, "matches": [x for x in FACTS["matches"] if x.get("result_vs_expectation") != "big_upset"]}
no_upset["tally"] = {**FACTS["tally"], "upsets": 0}
check("no upset: 'None'", dict((a, c) for a, _, c in roundup.lines(no_upset, 18, "night"))["Biggest upset"] == "None")
none_clear = {**FACTS, "tally": {**FACTS["tally"], "clear_favourites": 0, "favourite_won": 0}}
check("no clear favourites is stated plainly", dict((a, c) for a, _, c in roundup.lines(none_clear, 18, "night"))["Favourites won"] == "No clear favourites")
no_odds = overview.matchday_facts("X", MS, {m["id"]: None for m in MS}, ROWS)
nl = dict((a, c) for a, _, c in roundup.lines(no_odds, 18, "night"))
check("without odds the box says so, and still gives games and game of the night",
      nl["Favourites won"] == "No odds available" and nl["Biggest upset"] == "No odds available" and "Game of the night" in nl and "Games played" in nl, nl)
check("a league with no results has no box", roundup.html(overview.matchday_facts("X", [], {}, ROWS), 10) == "" and roundup.html(None, 10) == "")
check("two upsets: the bigger one (higher favourite chance) is shown",
      "Sporting" in dict((a, c) for a, _, c in roundup.lines({**FACTS, "matches": FACTS["matches"] + [{**FACTS["matches"][0], "match": "Small 0-1 Upset", "result_vs_expectation": "upset",
                                                                                                    "pre_match_chances_pct": {"Small": 52, "draw": 20, "Upset": 28}}]}, 18, "night"))["Biggest upset"])
check("text from data is escaped", "&lt;" in roundup.html({**FACTS, "matches": [{**FACTS["matches"][0], "match": "<b> 1-0 X"}], "game_of_the_night": "<b> 1-0 X"}, 18))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
