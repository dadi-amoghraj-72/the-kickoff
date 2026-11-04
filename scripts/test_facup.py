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

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
