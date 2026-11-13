"""Tests for D's comments on the 11 Nov 2026 edition: the player of the match's figures, 40-point NBA games always Stars, prime-time NFL always a key score,
NFL and NBA moves in Biggest News.
Run: .venv/bin/python scripts/test_morning5.py"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import bigstuff, cricket, events, nba  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# 1. Player of the match: her figures on the line
entry = {"potm": [{"name": "Emma de Broughe", "team": "Adelaide Strikers Women"}],
         "innings": [{"batting": [{"name": "Nicola Carey", "r": 66, "b": 53, "out": "not out"}], "bowling": [{"name": "Emma de Broughe", "o": 1.0, "r": 9, "w": 0}]},
                     {"batting": [{"name": "Emma de Broughe", "r": 41, "b": 37, "out": "c Carey b Malgioglio"}], "bowling": []}]}
got = cricket.potm_html(entry, True)
check("POTM line carries her score in gold", '<span class="n">41 (37)</span>' in got and "Emma de Broughe" in got, got)
check("a wicketless spell is not shown", "0/9" not in got, got)
allround = {"potm": [{"name": "A", "team": "X"}], "innings": [{"batting": [{"name": "A", "r": 30, "b": 20, "out": "not out"}], "bowling": []},
                                                            {"batting": [], "bowling": [{"name": "A", "o": 4.0, "r": 24, "w": 2}]}]}
got = cricket.potm_html(allround, True)
check("an all-rounder: both figures, not out marked", "30* (20)" in got and "2/24</span> (4 ov)" in got, got)
check("a name not on the card: the line as before", cricket.potm_html({"potm": [{"name": "Z", "team": "X"}], "innings": []}, True).endswith("(X)</span>"))

# 2. NBA: 40 points or a triple-double is a milestone, always a Star
p40 = {"PTS": 43, "REB": 10, "AST": 6, "STL": 3, "BLK": 0}
check("43 points is a milestone", nba.big_night(p40))
check("a triple-double is a milestone", nba.big_night({"PTS": 25, "REB": 16, "AST": 10, "STL": 0, "BLK": 0}))
check("32-8-10 is not", not nba.big_night({"PTS": 32, "REB": 8, "AST": 10, "STL": 5, "BLK": 2}))
perfs = events.nba_perf([("Wembanyama (SAS): 40 pts", 95, True), ("Doncic (LAL): 32 pts", 90, False), ("Flagg (DAL): 43 pts", 80, True), ("Davis (WSH): 44 pts", 78, True)])
names = [p["text"].split(" ")[0] for p in bigstuff.stars(perfs)]
check("11 Nov: Wembanyama, Doncic, Flagg and Davis are all Stars", names == ["Wembanyama", "Doncic", "Flagg", "Davis"], names)
check("old two-item rows still work", events.nba_perf([("x", 80)])[0].get("milestone") is None)

# 3. NFL: a prime-time game always makes Key Overnight Scores
mnf = {"status": "final", "date": datetime(2026, 11, 10, 1, 15, tzinfo=timezone.utc), "away": {"name": "Buffalo Bills", "score": 23, "abbr": "BUF"},
       "home": {"name": "Minnesota Vikings", "score": 6, "abbr": "MIN"}}
early = {**mnf, "date": datetime(2026, 11, 8, 18, 0, tzinfo=timezone.utc)}
check("MNF is prime time", events.nfl([mnf], 2, 10, 2)[0].get("primetime"))
check("a 1pm Sunday game is not", not events.nfl([early], 2, 10, 2)[0].get("primetime"))
nbas = [{**events.story("nba", "NBA", f"NBA: game {i}", 6 + i, False, "regular"), "kind": "result"} for i in range(4)]
cric = {**events.story("cricket", "Cricket", "Cricket: NZ v India", 9, True, "regular"), "kind": "result"}
picked = [s["text"] for s in bigstuff.select(nbas + [cric] + events.nfl([mnf], 2, 10, 2), 2)]
check("11 Nov: MNF makes it on a full Wednesday", "NFL: Buffalo Bills 23–6 Minnesota Vikings" in picked, picked)
dull = {**mnf, "away": {**mnf["away"], "score": 10}, "home": {**mnf["home"], "score": 7}}
picked = [s["text"] for s in bigstuff.select(events.nfl([dull], 2, 10, 2), 2)]
check("a dull prime-time game still makes it (below the usual bar)", len(picked) == 1, picked)

# 4. Biggest News order (the other sports' reader itself is tested in test_morning6.py)
foot = [{"text": "Arsenal sign A Player"}, {"text": "Spurs sack Their Manager"}, {"text": "Chelsea appoint New Boss"}]
us = [{"text": "NFL: Raiders name Fernando Mendoza starting QB after trading Kirk Cousins", "us": True}, {"text": "F1: Racing Bulls keep Lawson and Lindblad", "us": True}]
check("Biggest News: football first, then the other sports' best, then football's next", [i["text"] for i in bigstuff.top_news(foot + us)] == [foot[0]["text"], us[0]["text"], foot[1]["text"]])
check("only other sports: their two", [i["text"] for i in bigstuff.top_news(us)] == [us[0]["text"], us[1]["text"]])
check("one football item: it, then the other sports' two", [i["text"] for i in bigstuff.top_news(foot[:1] + us)] == [foot[0]["text"], us[0]["text"], us[1]["text"]])
check("no other sports: football's three", [i["text"] for i in bigstuff.top_news(foot)] == [f["text"] for f in foot])

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
