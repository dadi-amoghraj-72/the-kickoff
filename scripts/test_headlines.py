"""Offline tests for the morning's headlines (kickoff/headlines.py) and the match codes. Run: .venv/bin/python scripts/test_headlines.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import clubs, headlines, overview  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


def row(match, hs, as_, ids=("1", "2"), comeback=False, expect=None):
    return {"match": match, "total_goals": hs + as_, "margin": abs(hs - as_), "teams": list(ids), "comeback": comeback,
            **({"result_vs_expectation": expect} if expect else {})}


PSG, BAR, INT, MUN = "160", "83", "110", "360"
# Tuesday 3 November 2026 as it really was: Man United's 3-2 comeback against Roma was the only headline; PSG's 6-0 and the Barcelona and Inter wins were not
tue = {"UEFA Champions League": {"matches": [
    row("Galatasaray 2-0 Stuttgart", 2, 0, ("1", "2")),
    row("Barcelona 3-0 Aston Villa", 3, 0, (BAR, "3")),
    row("Feyenoord 0-3 Inter Milan", 0, 3, ("4", INT)),
    row("Manchester United 3-2 AS Roma", 3, 2, (MUN, "5"), comeback=True),
    row("Villarreal 0-6 Paris Saint-Germain", 0, 6, ("6", PSG)),
    row("Bodo/Glimt 0-0 Lille", 0, 0, ("7", "8"))]}}
h = headlines.pick(tue)
check("a Champions League night gives three headlines, not one", len(h) == 3, h)
check("the biggest story is PSG's 6-0 (a big margin and a listed club), ahead of Man United's 3-2 comeback", h[0] == "Champions League: Villarreal 0-6 Paris Saint-Germain", h)
check("then the other stories: Man United's comeback and Barcelona's or Inter's 3-0, never a goalless draw", set(h[1:]) <= {"Champions League: Manchester United 3-2 AS Roma", "Champions League: Barcelona 3-0 Aston Villa", "Champions League: Feyenoord 0-3 Inter Milan"} and not any("Lille" in x for x in h), h)
check("the competition is named in front without 'UEFA'", all(x.startswith("Champions League: ") for x in h))
check("Arsenal's result always comes first, and its match is not repeated", headlines.pick({"Premier League": {"matches": [row("Liverpool 0-1 Arsenal", 0, 1, ("364", "359")), row("Chelsea 4-0 Spurs", 4, 0, ("363", "367"))]}}, "Liverpool 0–1 Arsenal")
      == ["Arsenal: Liverpool 0–1 Arsenal", "Premier League: Chelsea 4-0 Spurs"])
mixed = {"Premier League": {"matches": [row("A 1-0 B", 1, 0)]}, "La Liga": {"matches": [row("Real Madrid 5-1 C", 5, 1, ("86", "9"))]}, "Serie A": {"matches": [row("D 2-2 E", 2, 2)]}}
check("headlines are picked across competitions: the 5-1 in La Liga leads", headlines.pick(mixed)[0] == "La Liga: Real Madrid 5-1 C" and len(headlines.pick(mixed)) == 3)
check("an upset counts for more than a plain win of the same size", headlines.score(row("x", 1, 0, expect="upset")) > headlines.score(row("x", 1, 0)) and headlines.score(row("x", 1, 0, expect="big_upset")) > headlines.score(row("x", 1, 0, expect="upset")))
check("a listed club's match scores higher than the same result between others, and a comeback adds to it",
      headlines.score(row("x", 2, 1, (PSG, "9"))) == headlines.score(row("x", 2, 1)) + headlines.LISTED_BONUS and headlines.score(row("x", 2, 1, comeback=True)) > headlines.score(row("x", 2, 1)))
check("no matches means no headlines, and Arsenal alone is one", headlines.pick({}) == [] and headlines.pick({"X": {"matches": []}}, "Arsenal 1–0 Y") == ["Arsenal: Arsenal 1–0 Y"])
check("the order does not depend on dictionary luck: equal scores keep the order they came in", headlines.pick({"A": {"matches": [row("p 1-0 q", 1, 0), row("r 1-0 s", 1, 0)]}}) == ["A: p 1-0 q", "A: r 1-0 s"])

# ---- Match codes ----
man = {"id": MUN, "name": "Manchester United", "abbr": "MAN"}
roma = {"id": "5", "name": "AS Roma", "abbr": "ROM"}
check("a listed club shows our own code (Man United is MUN, not ESPN's MAN); another club shows ESPN's", overview.team_code(man) == "MUN" and overview.team_code(roma) == "ROM")
check("a team with no abbreviation falls back to its first three letters", overview.team_code({"id": "9", "name": "Bodo/Glimt"}) == "BOD")

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
