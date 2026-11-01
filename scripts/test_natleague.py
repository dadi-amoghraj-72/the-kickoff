"""Offline tests for the Nations League block. Run: .venv/bin/python scripts/test_natleague.py"""
import itertools
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import natleague as nl  # noqa: E402
from kickoff.sources import espn, natleague as src  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
STAND = json.loads((FIX / "nl_standings.json").read_text())
EVENTS = json.loads((FIX / "nl_events.json").read_text())["events"]


def fake(url, params=None, **kw):
    if "/standings" in url:
        return STAND
    day = params["dates"]
    return {"events": [e for e in EVENTS if e["date"][:10].replace("-", "") == day]}


espn.get_json = fake
src.get_json = fake
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


G = src.get_groups()
check("14 groups: four each in Leagues A, B and C, two in League D", sorted(g["league"] for g in G) == list("AAAABBBBCCCCDD"), [g["league"] for g in G])
check("groups have four teams, except League D's two groups of three", [len(g["rows"]) for g in G] == [4] * 12 + [3, 3], [len(g["rows"]) for g in G])
check("rows come out in rank order", all([r["rank"] for r in g["rows"]] == list(range(1, len(g["rows"]) + 1)) for g in G))

# ---- Zone rules, read from ESPN's own notes ----
R = nl.parse_rules(G)
check("League A: 1st and 2nd go to the quarter-finals, 3rd to a play-off, 4th is relegated",
      [R[("A", i)] for i in (1, 2, 3, 4)] == ["Qualifies for QFs", "Qualifies for QFs", "Relegation playoffs", "Relegation"], [R.get(("A", i)) for i in (1, 2, 3, 4)])
check("League B: promoted, promotion play-off, relegation play-off, relegated (expanded from 'B-D' and 'A, B')",
      [R[("B", i)] for i in (1, 2, 3, 4)] == ["Promotion", "Promotion playoffs", "Relegation playoffs", "Relegation"], [R.get(("B", i)) for i in (1, 2, 3, 4)])
check("League C: 1st promoted, 2nd promotion play-off, 3rd nothing, 4th relegation or play-offs",
      (R[("C", 1)], R[("C", 2)], R.get(("C", 3)), R[("C", 4)]) == ("Promotion", "Promotion playoffs", None, "Relegation or playoffs"), [R.get(("C", i)) for i in (1, 2, 3, 4)])
check("League D: 1st promoted, 2nd promotion play-off, 3rd nothing", (R[("D", 1)], R[("D", 2)], R.get(("D", 3))) == ("Promotion", "Promotion playoffs", None))
check("zone phrases and bar colours", [nl.zone(R, "A", i) for i in (1, 3, 4)] == [("the quarter-finals", "blue"), ("the relegation play-offs", "lilac"), ("relegation", "rose")]
      and nl.zone(R, "C", 3) == (None, None))
check("no rules at all means no zones, not a crash", nl.parse_rules([]) == {} and nl.zone({}, "A", 1) == (None, None))

# ---- Every possible finish: a hand-worked example ----
rows = [{"id": "X", "points": 9}, {"id": "Y", "points": 6}, {"id": "Z", "points": 3}, {"id": "W", "points": 0}]
f = nl.finishes(rows, [("Y", "Z")])
check("hand-worked: X (1,2), Y (1,3), Z (2,3), W (4,4)", {k: v[:2] for k, v in f.items()} == {"X": (1, 2), "Y": (1, 3), "Z": (2, 3), "W": (4, 4)}, f)
check("ties are recorded as spans of places (X level with Y for 1st-2nd; Y and Z level for 2nd-3rd)", f["X"][2] == {(1, 2)} and f["Y"][2] == {(1, 2), (2, 3)} and f["W"][2] == set(), f)
check("no matches left: everyone's finish is exactly where the points put them", {k: v[:2] for k, v in nl.finishes(rows, []).items()} == {"X": (1, 1), "Y": (2, 2), "Z": (3, 3), "W": (4, 4)})
check("a level pair with nothing left is a tie, not a guess", {k: v[:2] for k, v in nl.finishes([{"id": "A", "points": 4}, {"id": "B", "points": 4}], []).items()} == {"A": (1, 2), "B": (1, 2)})


# ---- Cross-check against an independent brute force, on every real group ----
def brute(rows, remaining):
    ids = [r["id"] for r in rows]
    lo, hi = {i: 99 for i in ids}, {i: 0 for i in ids}
    for outcome in itertools.product((3, 1, 0), repeat=len(remaining)):
        pts = {r["id"]: r["points"] for r in rows}
        for (h, a), o in zip(remaining, outcome):
            pts[h] += o
            pts[a] += 3 if o == 0 else (1 if o == 1 else 0)
        order = sorted(ids, key=lambda i: -pts[i])
        for i in ids:
            same = [k for k, j in enumerate(order) if pts[j] == pts[i]]
            lo[i], hi[i] = min(lo[i], same[0] + 1), max(hi[i], same[-1] + 1)
    return {i: (lo[i], hi[i]) for i in ids}


matches = src.matches_between(date(2026, 9, 20), date(2026, 11, 20), pause=0)
owner = src.group_of(G)
agree = True
for g in G:
    left = [(m["home"]["id"], m["away"]["id"]) for m in matches if not m["completed"] and owner.get(m["home"]["id"]) is g]
    ours = {k: v[:2] for k, v in nl.finishes(g["rows"], left).items()}
    if ours != brute(g["rows"], left):
        agree = False
check("on all 14 real groups, the finishes match an independent brute-force calculation", agree)
check("the real data has 52 matches still to play, 4 per full group per matchday pair (2 matchdays)", sum(1 for m in matches if not m["completed"]) == 52)

# ---- Facts for a real group ----
a1 = next(g for g in G if g["name"] == "Group A1")
rem = [m for m in matches if not m["completed"] and owner.get(m["home"]["id"]) is a1]
facts = nl.analyse(a1, rem, R)
check("Group A1: 2 matchdays left, 4 matches, every team's best <= worst within 1-4", facts["matchdays_left"] == 2 and len(facts["remaining"]) == 4
      and all(1 <= t["best_finish"] <= t["worst_finish"] <= 4 for t in facts["teams"]), facts)
fr = next(t for t in facts["teams"] if t["team"] == "France")
check("France (10 points) can still win the group but is not yet through", fr["best_finish"] == 1 and fr["worst_finish"] >= 2 and fr["settled"] is None, fr)

# ---- Plain lines ----
settled = {"group": "G", "league": "A", "matchdays_left": 1, "remaining": [], "teams": [
    {"team": "Spain", "settled": "the quarter-finals", "nothing_at_stake": False, "best_finish": 1, "worst_finish": 2, "tiebreak_decides_zone": False},
    {"team": "England", "settled": "the quarter-finals", "nothing_at_stake": False, "best_finish": 1, "worst_finish": 2, "tiebreak_decides_zone": False},
    {"team": "Croatia", "settled": None, "nothing_at_stake": False, "best_finish": 3, "worst_finish": 4, "tiebreak_decides_zone": True},
    {"team": "Czechia", "settled": "relegation", "nothing_at_stake": False, "best_finish": 4, "worst_finish": 4, "tiebreak_decides_zone": False}]}
L = nl.stake_lines(settled)
check("lines: matchdays left, who has secured what, who is still open, and the tie-break warning, in at most three lines",
      len(L) <= 3 and L[0].startswith("1 matchday left.") and "Spain and England have secured the quarter-finals" in L[0] and "Czechia has secured relegation" in L[0]
      and "Croatia (3rd to 4th)" in " ".join(L) and "goal difference or head-to-head" in L[-1], L)
fin = nl.stake_lines({**settled, "matchdays_left": 0})
check("a finished group says so and still states what was secured", fin[0].startswith("The group is finished.") and "secured" in fin[0], fin)
check("a team with nothing at stake is left out of 'still open'", "Nobody" not in " ".join(nl.stake_lines({**settled, "teams": [{**settled["teams"][2], "settled": None, "nothing_at_stake": True}]})))
check("a team whose place is certain reads as that place, not '3rd to 3rd'", "(3rd)" in " ".join(nl.stake_lines({**settled, "teams": [{**settled["teams"][2], "best_finish": 3, "worst_finish": 3}]})))

# ---- Display ----
h = nl.table_html(a1, R)
rows_part, legend_part = h.split('<ul class="legend">')
check("League A table: bars blue, blue, lilac, rose in order, with the League A legend",
      rows_part.index("z-blue") < rows_part.index("z-lilac") < rows_part.index("z-rose") and rows_part.count("z-blue") == 2
      and "Quarter-finals" in legend_part and "Relegation play-off" in legend_part and "Relegated" in legend_part, h[:200])
b1 = next(g for g in G if g["name"] == "Group B1")
check("League B table uses the promotion legend", "Promoted" in nl.table_html(b1, R) and "Quarter-finals" not in nl.table_html(b1, R))
d1 = next(g for g in G if g["name"] == "Group D1")
check("League D's group of three draws three rows", nl.table_html(d1, R).count("<tr") == 4)
check("the caption names the group and the league", "Group A1 · League A" in h)
check("team names in the lines are bold", "<strong>France</strong>" in nl.group_html(a1, R, ["France are close."]))

# ---- The safety net: never draw conclusions without every remaining fixture ----
none_found = nl.analyse(a1, [], R)
check("a group with games to play but no fixtures found is marked unconfirmed, with no positions", none_found["fixtures_confirmed"] is False
      and all(t["best_finish"] is None for t in none_found["teams"]), none_found["teams"][0])
check("its only line says the fixtures could not be confirmed, and never says the group is finished",
      nl.stake_lines(none_found) == ["Remaining fixtures could not be confirmed, so no finishing positions are given."] and "finished" not in " ".join(nl.stake_lines(none_found)))
partial = nl.analyse(a1, rem[:3], R)
check("finding only 3 of the 4 remaining matches is also unconfirmed", partial["fixtures_confirmed"] is False and partial["found_remaining_matches"] == 3 and partial["expected_remaining_matches"] == 4, partial)
done_rows = [{"id": str(i), "team": f"T{i}", "short": f"T{i}", "rank": i, "played": 6, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "gd": 0, "points": 12 - 3 * i, "note": None} for i in range(1, 5)]
fin = nl.analyse({"name": "Group Z", "league": "A", "rows": done_rows}, [], R)
check("a group where every team has played 6 is genuinely finished, and says so", fin["fixtures_confirmed"] is True and fin["matchdays_left"] == 0
      and nl.stake_lines(fin)[0].startswith("The group is finished."), nl.stake_lines(fin))
three = [dict(x) for x in done_rows[:3]]
for x in three:
    x["played"] = 4
check("a League D group of three needs 6 matches in all: after 4 games each, 0 remain", nl.analyse({"name": "Group D9", "league": "D", "rows": three}, [], R)["fixtures_confirmed"] is True)

# ---- Claude phrasing, checked (fake model) ----
import json as _json  # noqa: E402
from types import SimpleNamespace as NS  # noqa: E402

from kickoff import rankings  # noqa: E402
from kickoff import settings as app_settings  # noqa: E402


class Fake:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.beta = NS(messages=NS(create=self._create))
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def reply(groups):
    return NS(stop_reason="end_turn", usage=NS(input_tokens=900, output_tokens=150),
              content=[NS(type="text", text=_json.dumps({"groups": [{"group": k, "lines": v} for k, v in groups.items()]}))])


S1 = {"group": "Group X", "league": "A", "matchdays_left": 1, "remaining": ["Spain v England"], "teams": [
    {"team": "Spain", "points": 12, "played": 5, "position_now": 1, "best_finish": 1, "worst_finish": 1, "settled": "the quarter-finals", "nothing_at_stake": False, "tiebreak_decides_zone": False},
    {"team": "England", "points": 9, "played": 5, "position_now": 2, "best_finish": 2, "worst_finish": 3, "settled": None, "nothing_at_stake": False, "tiebreak_decides_zone": True},
    {"team": "Croatia", "points": 3, "played": 5, "position_now": 3, "best_finish": 3, "worst_finish": 4, "settled": None, "nothing_at_stake": False, "tiebreak_decides_zone": False}]}
CL = ["1 matchday left. Spain has secured the quarter-finals.", "Still open: England (2nd to 3rd); Croatia (3rd to 4th).", "Some places could be decided by goal difference or head-to-head, not by points alone."]
good = ["Spain have secured a quarter-final place with one match left.", "England can finish 2nd or 3rd, while Croatia are fighting for 3rd or 4th.",
        "Some places could be decided by goal difference or head-to-head, not points alone."]
check("good lines pass the checks", nl.check_lines(good, S1, CL) == [], nl.check_lines(good, S1, CL))
check("'England are through' is rejected: the calculation leaves England open",
      any("England is certain" in p for p in nl.check_lines(["England are through to the quarter-finals.", good[1], good[2]], S1, CL)))
check("'Spain have secured' is accepted because Spain's zone is settled", nl.check_lines([good[0], good[2]], S1, CL) == [])
check("missing tie-break warning is rejected when a tie could decide a zone", any("tie-break" in p for p in nl.check_lines(good[:2], S1, CL)))
check("four lines are rejected", any("lines instead" in p for p in nl.check_lines(good + ["Extra."], S1, CL)))
check("an invented name is rejected", any("Mourinho" in p for p in nl.check_lines([good[0], "Jose Mourinho will watch England.", good[2]], S1, CL)))
check("a prediction number that is not in the facts is rejected", any("number 7" in p for p in nl.check_lines([good[0], "England need 7 points.", good[2]], S1, CL)))
c = Fake([reply({"Group X": good})])
out, usage = nl.phrase(c, {"Group X": S1}, {"Group X": CL})
check("good phrasing is used, on the news model, with the facts and the plain lines sent",
      out["Group X"] == good and c.calls[0]["model"] == app_settings.NEWS_MODEL and "code_lines" in c.calls[0]["messages"][0]["content"], c.calls[0]["model"])
bad = ["England are through to the quarter-finals.", good[1], good[2]]
c = Fake([reply({"Group X": bad}), reply({"Group X": good})])
out, _ = nl.phrase(c, {"Group X": S1}, {"Group X": CL})
check("a rejected phrasing is retried once with the problem named, and the fixed version is used",
      len(c.calls) == 2 and "England is certain" in c.calls[1]["messages"][0]["content"] and out["Group X"] == good, out)
out, _ = nl.phrase(Fake([reply({"Group X": bad}), reply({"Group X": bad})]), {"Group X": S1}, {"Group X": CL})
check("still wrong after the retry: the code-written lines are used", out["Group X"] == CL)
out, _ = nl.phrase(Fake([RuntimeError("down"), RuntimeError("down")]), {"Group X": S1}, {"Group X": CL})
check("an API failure also falls back to the code-written lines", out["Group X"] == CL)

# ---- The whole block on the real data ----
TOP = {"source": "test list", "teams": ["Spain", "Argentina", "England", "France", "Portugal", "Netherlands", "Belgium", "Italy", "Norway", "Germany", "Denmark",
                                      "Croatia", "Austria", "Greece", "Sweden", "Turkey", "Switzerland", "Poland", "Serbia", "Ukraine", "Scotland", "Wales"]}
window = espn.recent_results("uefa.nations", date(2026, 10, 5))
remaining_all = [m for m in matches if not m["completed"]]
html, use, facts = nl.build(G, TOP, window, remaining_all)
check("with a ranking: all four League A groups, and the League B groups with a top-30 side", all(f"Group A{i} · League A" in html for i in (1, 2, 3, 4)) and "League B" in html, html.count("<table"))
check("League C groups without a top-30 side are not shown", "League C" not in html or html.count("League C") <= 1)
html_a, _, facts_a = nl.build(G, None, window, remaining_all)
check("without any ranking only League A is shown", html_a.count("<table") == 4 and "League B" not in html_a)
check("the block says how far the league phase is, and names the ranking used", "Matchday 4 of 6 played" in html and "ranking: test list" in html)
ids = {x["id"] for g in nl.groups_to_show(G, TOP) for x in g["rows"]}
check("the scoreboard has one line for each of the window's results in the shown groups", html.count('<li><span class="h">') == sum(1 for m in window if m["home"]["id"] in ids), html.count('<li><span class="h">'))
check("every shown group has plain stake lines when Claude is not used", all(len(v) >= 1 for v in [nl.stake_lines(f) for f in facts.values()]) and "left" in html)
check("an empty ranking and no League A would show nothing", nl.build([g for g in G if g["league"] != "A"], None, [], remaining_all)[0] == "")
no_fx_html, _, _ = nl.build(G, TOP, window, [])
check("with no fixtures found the block still builds, says so, and never claims a group is finished", "could not be confirmed" in no_fx_html and "finished" not in no_fx_html)
calls = Fake([])
nl.build(G, TOP, window, [], calls)
check("and Claude is not asked to phrase groups whose fixtures are unconfirmed", calls.calls == [])

# ---- The ranking helpers ----
check("names match across spellings and accents (Turkey, Türkiye)", rankings.normalise("Türkiye") == rankings.normalise("Turkey") == "turkiye")
check("a group is 'in the top 30' when any team is", rankings.in_top(["Albania", "Denmark"], TOP) and not rankings.in_top(["Albania", "Cyprus"], TOP))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
