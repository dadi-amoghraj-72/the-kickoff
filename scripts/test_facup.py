"""Offline tests for the FA Cup block on real ESPN data: the third-round Saturday of 10 January 2026 (18 ties) and the first-round Saturday of 7 November 2026
(33 ties, not yet played). Run: .venv/bin/python scripts/test_facup.py"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import facup  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FX = json.loads((ROOT / "tests" / "fixtures" / "espn_facup.json").read_text())
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


text = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()  # noqa: E731
third = [espn.parse_match(e, "eng.fa") for e in FX["20260110"]["events"]]
first = [espn.parse_match(e, "eng.fa") for e in FX["20261107"]["events"]]
done3 = [m for m in third if m["completed"]]
raw_done = [e for e in FX["20260110"]["events"] if e["status"]["type"]["completed"]]

check("the third-round Saturday: ESPN lists 18 ties and the round comes from its season slug ('third-round')", len(third) == 18 and {m["stage"] for m in third} == {"third-round"}, {m["stage"] for m in third})
check("round names read well: third-round, quarterfinals, semifinals, final, and nothing gives nothing", [facup.round_name(x) for x in ("third-round", "quarterfinals", "semifinals", "final", "", None)] == ["Third Round", "Quarterfinals", "Semifinals", "Final", "", ""])

# ---- A small day shows every tie ----
h = facup.html(third, set())
check("18 ties are more than the limit of 12, so 12 are shown and the block says '6 other ties played'", h.count("<li>") == facup.LIMIT == 12 and "6 other ties played." in h and len(done3) == 18 == len(raw_done), (h.count("<li>"), len(done3)))
small = facup.html(third[:7], set())
check("a day with 12 ties or fewer shows every one, with no 'other ties' line", small.count("<li>") == 7 and "other tie" not in small)
check("the heading names the round: 'FA Cup · Third Round'", h.startswith("<h3>FA Cup · Third Round</h3>"), h[:60])

# ---- Which ties are chosen ----
big = {m["home"]["id"] for m in third if m["home"]["short"] in ("Sunderland", "Everton", "Leicester City")} | {m["away"]["id"] for m in third if m["away"]["short"] in ("Sunderland", "Everton", "Leicester City")}
chosen, left = facup.pick(done3, big)
names = {m["id"] for m in chosen}
check("ties with a top-tier club come first: Sunderland v Everton and Leicester's tie are in the 12 shown whatever their scores", all(m["id"] in names for m in done3 if m["home"]["id"] in big or m["away"]["id"] in big) and left == 6, (len(chosen), left))
rest_goals = sorted((m["home_score"] + m["away_score"] for m in done3 if m["id"] not in names), reverse=True)
shown_non_top = sorted((m["home_score"] + m["away_score"] for m in chosen if not (m["home"]["id"] in big or m["away"]["id"] in big)), reverse=True)
check("after the top-tier ties the highest-scoring of the rest are kept: nothing left out scored more than the lowest-scoring non-top tie that is shown", not rest_goals or not shown_non_top or max(rest_goals) <= min(shown_non_top))
check("the ties shown are in kick-off order", [m["kickoff"] for m in chosen] == sorted(m["kickoff"] for m in chosen))
h_raw_ok = all(any(f"{int(next(c['score'] for c in e['competitions'][0]['competitors'] if c['homeAway'] == 'home'))}–{int(next(c['score'] for c in e['competitions'][0]['competitors'] if c['homeAway'] == 'away'))}" in text(facup.html(third[i:i + 1], set())) for e in [FX['20260110']['events'][i]]) for i in range(5))
check("independent: for the first five ties the printed score equals the raw competitor scores from the saved ESPN response", h_raw_ok)

# ---- Quiet and unplayed ----
check("the first-round Saturday is 33 ties not yet played: nothing is shown (an unfinished tie never appears)", len(first) == 33 and not any(m["completed"] for m in first) and facup.html(first, set()) == "")
check("no matches means no block", facup.html([], set()) == "")

# ---- only the ties that matter (D, 2026-11-08) ----
_rows = lambda prefix, n: [{"id": f"{prefix}{k}"} for k in range(1, n + 1)]  # noqa: E731
_tables = {"eng.1": _rows("p", 20), "eng.2": _rows("c", 24), "eng.3": _rows("o", 24), "eng.4": _rows("t", 24), "eng.5": _rows("n", 24)}
_pyr = facup.pyramid(lambda lg: _tables[lg])
check("the pyramid: Premier League 1-20, Championship 21-44, League One 45-68, League Two 69-92, National League 93-116", (_pyr["p1"], _pyr["c1"], _pyr["o1"], _pyr["t24"], _pyr["n24"]) == (1, 21, 45, 92, 116))
_m = lambda h, a, hs, as_, w=None: {"home": {"id": h}, "away": {"id": a}, "home_score": hs, "away_score": as_, "winner": w}  # noqa: E731
check("a Premier League club playing always counts, win or lose", facup.matters(_m("p5", "n3", 4, 0, "home"), _pyr) and facup.matters(_m("o3", "p18", 1, 0, "home"), _pyr))
check("a Championship club beaten by a lower club counts (League One's 10th beats the Championship's 12th)", facup.matters(_m("o10", "c12", 2, 1, "home"), _pyr))
check("a Championship club winning, against anyone below, does not", not facup.matters(_m("c12", "o10", 2, 1, "home"), _pyr))
check("a giant-killing of 20 places or more counts (National League 5th beats League One 20th: 97 v 64, 33 places)", facup.matters(_m("n5", "o20", 1, 0, "home"), _pyr))
check("an ordinary early-round tie does not (League Two 3rd beats National League 10th; a club below the National League beats another)", not facup.matters(_m("t3", "n10", 3, 0, "home"), _pyr) and not facup.matters(_m("x1", "x2", 2, 0, "home"), _pyr))
check("a tie settled on penalties uses the winner ESPN names (League Two 20th beats League One 2nd on penalties: 88 v 46, 42 places)", facup.matters(_m("t20", "o2", 1, 1, "home"), _pyr))
check("a club below the National League beating a League Two side counts (117 v 70)", facup.matters(_m("x9", "t2", 1, 0, "home"), _pyr))
print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
