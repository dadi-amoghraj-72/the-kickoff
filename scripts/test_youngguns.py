"""Tests for Young Guns: who counts as young, the thresholds and the watchlist, each sport's finder, the picking and the Claude check. Run: .venv/bin/python scripts/test_youngguns.py"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import daily, young_sports, youngguns as yg  # noqa: E402

results = []
DAY = date(2026, 11, 5)


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


class Lookup:
    """A fake age lookup: {(sport, id): {"dob", "years"}}; counts the calls."""

    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, sport, aid):
        self.calls.append((sport, aid))
        return self.table.get((sport, aid))


# ---- who is young ---------------------------------------------------------------------------------
check("age on a day: the birthday counts", yg.age_on("2006-11-05", DAY) == 20 and yg.age_on("2005-11-05", DAY) == 21 and yg.age_on("2005-11-06", DAY) == 20 and yg.age_on("junk", DAY) is None)
check("under 21 is young, 21 is not; a rookie is young at any age", yg.is_young(20, False) and not yg.is_young(21, False) and yg.is_young(24, True) and not yg.is_young(None, False))
lk = Lookup({("nba", "1"): {"dob": "2006-12-21", "years": 0, "age": 19}, ("nfl", "2"): {"dob": "2001-01-08", "years": 0, "age": 25}, ("nba", "3"): {"dob": "1996-01-01", "years": 6, "age": 30}})
ages = {}
check("a rookie of any age counts in the NBA/NFL (ESPN's 0 years of experience); an unknown athlete is not young",
      yg.lookup("nba", "1", DAY, ages, lk) == (19, True) and yg.lookup("nfl", "2", DAY, ages, lk) == (25, True) and yg.lookup("nba", "9", DAY, ages, lk) == (None, False))
n = len(lk.calls)
yg.lookup("nba", "1", DAY, ages, lk)
check("a lookup is remembered: the same player is never asked about twice", len(lk.calls) == n and "nba:1" in ages)
check("soccer and tennis have no rookie year: only age counts", yg.lookup("soccer", "5", DAY, {}, Lookup({("soccer", "5"): {"dob": "2010-01-01", "years": 0}})) == (16, False))

# ---- NBA ------------------------------------------------------------------------------------------
opp = {"name": "Orlando Magic"}
mk = lambda pid, name, pts, reb=3, ast=2, dnp=False: {"id": pid, "name": name, "team": "DET", "opp": opp, "dnp": dnp, "PTS": pts, "REB": reb, "AST": ast, "STL": 0, "BLK": 0, "TO": 1, "MIN": 30, "pos": "G"}  # noqa: E731
lk = Lookup({("nba", "1"): {"dob": "2006-12-21", "years": 0}, ("nba", "3"): {"dob": "1996-01-01", "years": 6}, ("nba", "4"): {"dob": "2005-03-01", "years": 0}})
st = {}
got = young_sports.nba([mk("1", "Cooper Flagg", 27, 8), mk("3", "Old Vet", 35), mk("4", "Quiet Rookie", 6), mk("5", "DNP Rookie", 30, dnp=True)], st, DAY, lk)
check("NBA: a rookie with 27 points is a candidate with his line and opponent; a veteran is not", [c["name"] for c in got] == ["Cooper Flagg"] and "27 pts" in got[0]["facts"] and "Orlando Magic" in got[0]["facts"], got)
check("NBA: the age lookup is made only for players over the lowest bar (no request for a quiet night or a player who did not play)", sorted(c[1] for c in lk.calls) == ["1", "3"], lk.calls)
st = {"watch": {"nba:4": {"name": "Quiet Rookie", "sport": "nba", "team": "DET", "days": ["2026-11-01", "2026-11-02", "2026-11-03"]}}}
check("NBA: a watched player needs only 70% of the bar (15 points counts, 15 points from an unwatched rookie does not)",
      [c["name"] for c in young_sports.nba([mk("4", "Quiet Rookie", 15)], st, DAY, lk)] == ["Quiet Rookie"] and young_sports.nba([mk("4", "Quiet Rookie", 15)], {}, DAY, lk) == [])

# ---- NFL ------------------------------------------------------------------------------------------
lk = Lookup({("nfl", "10"): {"dob": "2003-06-01", "years": 0}, ("nfl", "11"): {"dob": "1999-06-01", "years": 4}})
nfl_p = lambda pid, name, cat, **stats: {"id": pid, "name": name, "team": "JAX", "pos": "RB", "stats": {cat: {k: str(v) for k, v in stats.items()}}}  # noqa: E731
got = young_sports.nfl([nfl_p("10", "Rookie Back", "rushing", YDS=134, TD=1), nfl_p("11", "Vet Back", "rushing", YDS=150, TD=1), nfl_p("12", "Nobody", "rushing", YDS=20, TD=0)], {}, DAY, lk)
check("NFL: a rookie running back with 134 rushing yards is a candidate; a veteran is not; a quiet player costs no lookup", [c["name"] for c in got] == ["Rookie Back"] and "134 rushing yards" in got[0]["facts"] and ("nfl", "12") not in lk.calls, got)

# ---- F1 -------------------------------------------------------------------------------------------
rows = json.load(open(ROOT / "tests/fixtures/jolpica_results_18.json"))["MRData"]["RaceTable"]["Races"][0]["Results"]
got = young_sports.f1(rows, "United States Grand Prix", date(2026, 10, 26))
names = [c["name"] for c in got]
check("F1: only drivers under 21 on race day, with a podium, points finish, pole or fastest lap", all(c["age"] < 21 for c in got) and all(any(w in c["facts"] for w in ("finished", "pole", "fastest")) for c in got), got)
check("F1: Antonelli (born 25 Aug 2006) is 20 on 26 Oct 2026, so he is listed with his finish; his name uses the given name he is known by", "Kimi Antonelli" in names, names)
check("F1: the same race a year later, he is 21 and drops out", "Kimi Antonelli" not in [c["name"] for c in young_sports.f1(rows, "x", date(2027, 10, 26))])

# ---- football and tennis --------------------------------------------------------------------------
pl = lambda pid, name, goals, assists: {"id": pid, "name": name, "short": name.split()[-1], "team_abbr": "CHE", "goals": goals, "assists": assists, "match": "Chelsea 2\u20131 Spurs"}  # noqa: E731
lk = Lookup({("soccer", "20"): {"dob": "2008-02-01", "years": 0}, ("soccer", "21"): {"dob": "1995-02-01", "years": 0}})
got = young_sports.soccer([pl("20", "Lamine Yamal", 2, 1), pl("21", "Sam Old", 3, 0), pl("22", "No Goal", 0, 0)], {}, DAY, lk)
check("football: an 18-year-old with two goals and an assist is listed with his figures; a veteran and a player with no goal or assist are not (and cost no lookup)",
      [c["name"] for c in got] == ["Lamine Yamal"] and got[0]["facts"] == "2 goals, 1 assist (Chelsea 2\u20131 Spurs)" and ("soccer", "22") not in lk.calls, got)
m = lambda stage, seed, wid="30": {"stage": stage, "winner": {"id": wid, "name": "Joao Fonseca", "short": "J. Fonseca", "seed": None}, "loser": {"id": "31", "short": "A. Rublev", "seed": seed}, "status": "final", "sets": [{"w": 6, "l": 4, "tb": None, "won": True}, {"w": 6, "l": 3, "tb": None, "won": True}], "draw": "Men's Singles"}  # noqa: E731
lk = Lookup({("tennis", "30"): {"dob": "2006-08-04", "years": None}})
check("tennis: an under-21 who beats a seed (or wins in the last 16 or later) is listed; an early-round win over an unseeded player is not (no lookup)",
      len(young_sports.tennis([m("R2", 7)], {}, DAY, lk)) == 1 and young_sports.tennis([m("R4", None)], {}, DAY, lk) and not young_sports.tennis([m("R2", None)], {}, DAY, Lookup({})))

# ---- watchlist, picking, html ----------------------------------------------------------------------
c = lambda pid, score, day="2026-11-05", name=None: yg.make("nba", pid, name or f"P{pid}", "DET", "20 pts", score, 19, True, date.fromisoformat(day))  # noqa: E731
s = {}
for d in ("2026-11-01", "2026-11-02", "2026-11-03"):
    s = yg.update_watch(s, [c("1", 50, d)], date.fromisoformat(d))
check("three notable days put a young player on the watchlist for good; two do not", yg.watched(s, "nba", "1") and not yg.watched(yg.update_watch({}, [c("1", 50)], DAY), "nba", "1"))
s2 = yg.update_watch(s, [c("1", 50, "2026-11-03")], DAY)
check("the same day twice counts once", len(s2["watch"]["nba:1"]["days"]) == 3)
many = [c(str(i), i) for i in range(10)] + [c("3", 99, name="P3 again")]
sel = yg.select(many)
check("at most 5 lines, best first, one line per player", len(sel) == 5 and sel[0]["score"] == 99 and len({yg.watch_key(x) for x in sel}) == 5)
check("no candidates, no section", yg.html([]) == "" and yg.build([], {}, DAY)["html"] == "")
b = yg.build([c("1", 60, name="Cooper Flagg")], {}, DAY)
check("the plain line reads 'Name (team, rookie, age): facts' with gold figures", "Cooper Flagg (DET, rookie, 19): " in b["lines"][0] and '<span class="n">20 pts</span>' in b["html"], b["html"])

# ---- Claude phrasing ----------------------------------------------------------------------------
cand = yg.make("nba", "1", "Cooper Flagg", "DAL", "27 pts, 8 reb against Orlando Magic", 60, 19, True, DAY)
good = {"lines": [{"n": 1, "text": "Cooper Flagg (DAL, 19) scored 27 points with 8 rebounds against Orlando Magic."}]}
bad = {"lines": [{"n": 1, "text": "Cooper Flagg (DAL, 19) scored 31 points, a franchise record."}]}
check("Claude's line is used when every name and number is in the facts", yg.phrase(object(), [cand], lambda *a: (good, {"input": 1, "output": 1}))[0] == {"nba:1": good["lines"][0]["text"]})
check("a line with a number or claim not in the facts is dropped (the plain line stays)", yg.phrase(object(), [cand], lambda *a: (bad, {"input": 1, "output": 1}))[0] == {})
check("without Claude there is no call and no cost", yg.phrase(None, [cand]) == ({}, {"input": 0, "output": 0}))
check("a Claude failure never raises", yg.phrase(object(), [cand], lambda *a: 1 / 0)[0] == {})
b = yg.build([cand], {}, DAY, object())
check("build falls back to the plain line when Claude's call fails", b["lines"] == [yg.plain_line(cand)], b["lines"])

# ---- the edition ---------------------------------------------------------------------------------
now = datetime(2026, 11, 4, 23, 15, tzinfo=timezone.utc)
players = [mk("1", "Cooper Flagg", 27, 8)]
adapter = lambda n, d, s_: {"sections": [{"id": "nba", "title": "NBA", "html": "<p>x</p>"}], "state": {}, "young_in": {"nba": players}}  # noqa: E731
lk = Lookup({("nba", "1"): {"dob": "2006-12-21", "years": 0}})
ed = daily.build_edition(now, DAY, {}, [("nba", "NBA", adapter)], age_lookup=lk)
ids = [x["id"] for x in ed["edition"]["sections"]]
check("the edition has a Young Guns section after the sport sections, and saves the watchlist and the remembered ages",
      "young-guns" in ids and ids.index("young-guns") > ids.index("nba") and "nba:1" in ed["state"]["youngguns"]["ages"] and "nba:1" in ed["state"]["youngguns"]["watch"], ids)
ed = daily.build_edition(now, DAY, {}, [("nba", "NBA", lambda n, d, s_: {"sections": [{"id": "nba", "title": "NBA", "html": "<p>x</p>"}], "state": {}})])
check("a quiet day has no Young Guns section", "young-guns" not in [x["id"] for x in ed["edition"]["sections"]])
ed = daily.build_edition(now, DAY, {}, [("nba", "NBA", adapter)], age_lookup=lambda *a: 1 / 0)
check("a broken age lookup leaves that player out; the edition and the other sections stay and nothing is reported as failed", [x["id"] for x in ed["edition"]["sections"]] == ["nba"] and ed["problems"] == [], (ed["problems"], [x["id"] for x in ed["edition"]["sections"]]))
from kickoff.sources import espn  # noqa: E402,F401
simple = daily._simple("nba", "NBA", lambda n, d, s_: {"html": "<p>x</p>", "state": {}, "young_in": {"nba": [1]}}, "nba")[2](now, DAY, {})
check("the simple sports' adapter passes the Young Guns material on (the first real run found it dropped)", simple["young_in"] == {"nba": [1]})
check("youngguns is one of the saved states", "youngguns" in daily.STATE_NAMES)

# ---- one blank row between sports, gold figures, sports together (D, 2026-11-05)
_h = yg.html(["Darius Acuff Jr. (SAC, rookie, 19) scored 22 points and gave out 12 assists.", "Dylan Harper (SAS, 20) scored 21 points.", "Mattia Liberali (COMO, 19): 1 goal, 2 assists (Lens 1\u20139 Como)"], ["nba", "nba", "soccer"])
check("a blank row only where the sport changes: the first basketball line and the second have none, the first football line has it", _h.count("sport-gap") == 1 and _h.index("sport-gap") > _h.index("Harper"), _h)
check("the whole stat phrase is gold (22 points, 12 assists, 21 points, 1 goal, 2 assists) and the ages are not (19, 20)", all(f'<span class="n">{n}</span>' in _h for n in ("22 points", "12 assists", "21 points", "1 goal", "2 assists")) and '<span class="n">19' not in _h and '<span class="n">20' not in _h, _h)
_c = lambda sp, i: yg.make(sp, i, f"P{i}", "T", "1 goal", 50 - i, 19, False, DAY)  # noqa: E731
check("the picks are grouped by sport, sports in the order of their best player", [c["sport"] for c in yg.grouped([_c("nba", 1), _c("soccer", 2), _c("nba", 3), _c("soccer", 4)])] == ["nba", "nba", "soccer", "soccer"])

_s = yg.html(["Mattia Liberali (COMO, 19) scored once as Como won 9\u20131 at Lens, with 2 assists."], ["soccer"])
check("'scored once' and '2 assists' are gold, the score 9\u20131 and the age are not", '<span class="n">scored once</span>' in _s and '<span class="n">2 assists</span>' in _s and '<span class="n">9' not in _s and '9\u20131' in _s and '<span class="n">19' not in _s, _s)
_c = {"name": "Mattia Liberali", "team": "COMO", "age": 19, "facts": "1 goal, 2 assists (Lens 1\u20139 Como)", "rookie": False}
check("a count the facts do not carry is rejected: 'scored twice' for one goal, 'a hat-trick', '3 assists' (D, 2026-11-05)", not yg.supported("Mattia Liberali (COMO, 19) scored twice at Lens.", _c) and not yg.supported("Mattia Liberali (COMO, 19) scored a hat-trick.", _c)
      and not yg.supported("Mattia Liberali (COMO, 19) set up 3 assists.", _c) and yg.supported("Mattia Liberali (COMO, 19) scored once and set up 2 assists.", _c), "")
check("number words count too: 'two assists' passes, 'three assists' does not", yg.counts_agree("He had two assists.", "1 goal, 2 assists") and not yg.counts_agree("He had three assists.", "1 goal, 2 assists"))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
