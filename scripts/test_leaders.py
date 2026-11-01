"""Offline tests for leaders and clean sheets. Run: python3 scripts/test_leaders.py"""
import copy
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import leaders, tables  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


# ---- ESPN readers ----
espn.get_json = lambda url, params=None, **kw: json.loads((FIX / "espn_core_leaders.json").read_text())
lead = espn.get_leaders("eng.1", 2026)
check("scorer and assist leaders parsed, best first", lead["goals"][0]["value"] >= 1 and lead["assists"][0]["value"] >= 1, lead)
check("ids come out as plain numbers", all(x["athlete_id"].isdigit() and x["team_id"].isdigit() for x in lead["goals"]), lead["goals"])
check("season year: Nov 2026 and Mar 2027 are both 2026-27", (espn.season_year(date(2026, 11, 2)), espn.season_year(date(2027, 3, 1))) == (2026, 2026))

espn.get_json = lambda url, params=None, **kw: json.loads((FIX / "espn_summary_rosters.json").read_text())
gks = espn.get_starting_keepers("eng.1", "1")
check("one starting keeper found per team", len(gks) == 2 and all(isinstance(v, tuple) for v in gks.values()), gks)

# ---- Clean-sheet counting ----
def match(mid, hs, as_, done=True):
    return {"id": mid, "completed": done, "home": {"id": "1"}, "away": {"id": "2"}, "home_score": hs, "away_score": as_}


KEEPERS = {"1": ("11", "Keeper One"), "2": ("22", "Keeper Two")}
kf = lambda m: KEEPERS  # noqa: E731

st = leaders.count_clean_sheets({}, "eng.1", [match("a", 2, 0), match("b", 1, 1), match("c", 0, 0), match("d", 0, 3)], kf)
k = st["eng.1"]["keepers"]
check("clean sheets: 2-0 gives the home keeper one", k["11"]["cs"] == 2, k)  # a (2-0) and c (0-0)
check("clean sheets: 0-0 gives both keepers one, 0-3 gives the away keeper one", k["22"]["cs"] == 2, k)  # c and d
check("1-1 gives nobody a clean sheet", st["eng.1"]["matches"].count("b") == 1 and k["11"]["cs"] + k["22"]["cs"] == 4)
st2 = leaders.count_clean_sheets(st, "eng.1", [match("a", 2, 0), match("e", 1, 0)], kf)
check("a match seen twice is counted once", st2["eng.1"]["keepers"]["11"]["cs"] == 3, st2["eng.1"]["keepers"]["11"])
check("the input state is not changed", st["eng.1"]["keepers"]["11"]["cs"] == 2)
check("unfinished matches are ignored", "z" not in leaders.count_clean_sheets({}, "eng.1", [match("z", 1, 0, done=False)], kf).get("eng.1", {}).get("matches", []))


def broken(m):
    raise RuntimeError("lineup down")


st3 = leaders.count_clean_sheets({}, "eng.1", [match("f", 1, 0)], broken)
check("a failed lineup lookup leaves the match for the next run", "f" not in st3["eng.1"]["matches"])
tops = leaders.top_clean_sheets({"eng.1": {"keepers": {"1": {"name": "B", "team": "1", "cs": 3}, "2": {"name": "A", "team": "2", "cs": 3},
                                                       "3": {"name": "C", "team": "3", "cs": 1}}}}, "eng.1")
check("ties at the top are all returned, alphabetically", [t["name"] for t in tops] == ["A", "B"], tops)
check("no data gives an empty list", leaders.top_clean_sheets({}, "eng.1") == [])

# ---- Display ----
one = lambda n, c, v: [{"name": n, "club": c, "value": v}]  # noqa: E731
html = leaders.leaders_html(one("Erling Haaland", "MCI", 9), one("Florian Wirtz", "LIV", 6), one("Bart Verbruggen", "BHA", 6))
check("three labelled lines in order, with Top CS", html.index("Top Scorer") < html.index("Top Assists") < html.index("Top CS"))
check("single leader: number first, then full name and club code",
      '<span class="n">09</span><span class="who"><span class="p">Erling Haaland (MCI)</span></span>' in html, html)
check("every club shows as a code, never a full club name", "Manchester" not in html and "(BHA)" in html)
tied = leaders.leaders_html([], [{"name": "Pascal Gross", "club": "BHA", "value": 4}, {"name": "Evanilson", "club": "BOU", "value": 4},
                                {"name": "Declan Rice", "club": "ARS", "value": 4}, {"name": "Dan Ndoye", "club": "BOU", "value": 4}], [])
check("a tie: number first, then surnames with codes, each player kept together",
      '<span class="n">04</span><span class="who"><span class="p">Gross (BHA)</span>, <span class="p">Evanilson (BOU)</span>, '
      '<span class="p">Rice (ARS)</span>, <span class="p">Ndoye (BOU)</span></span>' in tied, tied)
check("numbers are zero-padded to two digits, so 9 and 15 line up",
      '<span class="n">09</span>' in html and '<span class="n">15</span>' in leaders.leaders_html(one("A B", "X", 15), [], []))
check("no 'Tied' wording", "Tied" not in tied)
check("empty stats are left out", "Top Scorer" not in tied and "Top CS" not in tied)
check("surnames", [leaders.surname(n) for n in ("Erling Haaland", "Kevin De Bruyne", "Virgil van Dijk", "Ederson", "Vinícius Júnior",
      "Trent Alexander-Arnold", "Marc-André ter Stegen", "Yvon Mvogo")] ==
      ["Haaland", "De Bruyne", "van Dijk", "Ederson", "Vinícius Júnior", "Alexander-Arnold", "ter Stegen", "Mvogo"])
check("escapes odd characters", "A&amp;B" in leaders.leaders_html(one("Ann Lee", "A&B", 1), [], []))

# ---- In the tables ----
espn.get_json = lambda url, params=None, **kw: json.loads((FIX / "espn_pl_table.json").read_text())
PL = espn.get_table("eng.1")
L = {"eng.1": "<ul class='leaders'>LEADERS</ul>"}
names = {"eng.1": "Premier League"}
h_full, st_t = tables.tables_html({"eng.1": PL}, {}, date(2026, 11, 3), names, leaders=L)
check("leaders sit under a full table", h_full.index("</table>") < h_full.index("LEADERS"))
moved = copy.deepcopy(PL); moved[10]["points"] += 3
h_ch, _ = tables.tables_html({"eng.1": moved}, st_t, date(2026, 11, 5), names, leaders=L)
check("leaders also appear under a changed (top 6) table", "LEADERS" in h_ch)
h_un, _ = tables.tables_html({"eng.1": PL}, st_t, date(2026, 11, 5), names, leaders=L)
check("no leaders when the table is unchanged", "LEADERS" not in h_un)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
