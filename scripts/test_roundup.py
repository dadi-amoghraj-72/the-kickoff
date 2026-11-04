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
sp_ = next(x for x in FACTS["matches"] if x["match"] == "Sporting CP 2-3 LASK Linz")
check("the Champions League round is 18 games (36 teams), so this window is 9/18", L[0] == ("Games played", "9/18", "", ""), L[0])
check("underdogs won: 1 of the 6 clear favourites lost (Sporting), counted from the odds labels, not from the favourites count", L[1] == ("Underdogs won", "1/6", "", "") and FACTS["tally"]["upsets"] == 1 == sum(1 for x in FACTS["matches"] if x.get("result_vs_expectation") in ("upset", "big_upset")), L[1])
check("biggest upset: the team codes, with the favourite's pre-match chance on the line below", L[2] == ("Biggest upset", "", sp_["codes"], "Sporting CP had a 70% chance") and re.fullmatch(r"[A-Z]+ \d+-\d+ [A-Z]+", sp_["codes"]), L[2])
check("best game: the team codes and the score and nothing underneath (no goals, no comeback line: D's choice)", L[3] == ("Best game", "", sp_["codes"], ""), L[3])
check("the rows are in the same order every time: games played, underdogs won, biggest upset, best game", [x[0] for x in L] == ["Games played", "Underdogs won", "Biggest upset", "Best game"])
one_goal = {**FACTS, "matches": [{**FACTS["matches"][0], "total_goals": 1}], "game_of_the_night": FACTS["matches"][0]["match"]}
check("the best game row has no second line however many goals there were", roundup.lines(one_goal, 10)[-1][3] == "" and roundup.lines(FACTS, 10)[-1][3] == "", roundup.lines(one_goal, 10)[-1])
check("the best game is called 'Best game' in a league and in the Champions League alike", roundup.lines(FACTS, 10, "day")[3][0] == "Best game" == roundup.lines(FACTS, 10, "night")[3][0])
fallback = {**FACTS, "matches": [{k: v for k, v in FACTS["matches"][0].items() if k != "codes"}], "game_of_the_night": FACTS["matches"][0]["match"]}
check("a match without codes falls back to its full-name line", roundup.lines(fallback, 10)[-1][2] == FACTS["matches"][0]["match"])

h = roundup.html(FACTS, 18, "night")
check("the box is a list with the figures highlighted and the small second lines under their rows", h.count("<li>") == 4 and h.count('class="n"') == 2 and h.count('class="sub"') == 1 and h.startswith('<ul class="roundup">'), h[:200])
check("it reads cleanly as text", text(h).startswith("Games played 9/18 Underdogs won 1/6 Biggest upset " + sp_["codes"]) and "Sporting CP had a 70% chance" in text(h), text(h))

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
check("with the season info the box gets a first row; all 18 games of the matchday are done, so the second line says the matchday is complete",
      L2[0] == ("Matchday", "3/8", "", "") and L2[1] == ("Games played", "9/18", "", "Matchday complete"), L2[:2])
day1 = roundup.round_info(league([4] * 18 + [3] * 18), "Matchday", 8)
check("day 1 of a two-day matchday: 9 of 18 games played so far gives 'Rest on day 2' under Games played", roundup.lines(FACTS, 18, "night", day1)[1] == ("Games played", "9/18", "", "Rest on day 2"), (day1, roundup.lines(FACTS, 18, "night", day1)[1]))
sunday = roundup.lines({**FACTS, "matches": FACTS["matches"][:3]}, 10, "day", mon)
check("a league: 3 games played and 9 of 10 done this game week says the rest are still to play", sunday[1] == ("Games played", "3/10", "", "Rest still to play"), sunday[1])
whole = roundup.lines(FACTS, 9, "night", {"label": "Game week", "number": 9, "total": 38, "so_far": 9, "size": 9})
check("a whole round played in one go has no second line", whole[1] == ("Games played", "9/9", "", ""), whole[1])
check("the box is the same rows in the same order", [x[0] for x in roundup.lines(FACTS, 18, "night", cl)] == ["Matchday", "Games played", "Underdogs won", "Biggest upset", "Best game"])
check("without season info the box has no round row", len(roundup.lines(FACTS, 18, "night")) == 4)

# ---- Edge cases ----
no_upset = {**FACTS, "matches": [x for x in FACTS["matches"] if x.get("result_vs_expectation") not in ("upset", "big_upset")]}
no_upset["tally"] = {**FACTS["tally"], "upsets": 0}
check("no upset: the 'Biggest upset' row is left out altogether (no 'None' line)", "Biggest upset" not in [x[0] for x in roundup.lines(no_upset, 18, "night")] and roundup.lines(no_upset, 18, "night")[1] == ("Underdogs won", "0/6", "", ""))
none_clear = {**FACTS, "tally": {**FACTS["tally"], "clear_favourites": 0, "favourite_won": 0, "upsets": 0}}
check("no clear favourites is stated plainly", dict((a, c) for a, _, c, _ in roundup.lines(none_clear, 18, "night"))["Underdogs won"] == "No clear favourites")
no_odds = {k: v for k, v in FACTS.items() if k != "tally"}
check("no odds is stated plainly", dict((a, c) for a, _, c, _ in roundup.lines(no_odds, 18, "night"))["Underdogs won"] == "No odds available")
check("no matches, no box", roundup.html({"matches": []}, 18) == "" and roundup.html(None, 18) == "")

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
