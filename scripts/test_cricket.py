"""Offline tests for cricket (the match list part). Run: python3 scripts/test_cricket.py"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket as ck  # noqa: E402
from kickoff.sources import cricket as src  # noqa: E402

M = json.loads((ROOT / "tests" / "fixtures" / "cricket_current.json").read_text())
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


by = lambda text: next(m for m in M if text in m["name"])  # noqa: E731
kinds = [(m["name"], ck.classify(m)) for m in M]
intl = [n for n, c in kinds if c["kind"] == "international"]
league = [n for n, c in kinds if c["kind"] == "league"]
check("8 of the 51 are Test-nation internationals (NZ v India x2, Afghanistan v Zimbabwe x2, Namibia v Ireland x2, the Pakistan tri-series x2)", len(intl) == 8, intl)
check("all 7 Women's Big Bash League matches are leagues, marked women's", len(league) == 7 and all(c["women"] and c["label"] == "WBBL" for n, c in kinds if c["kind"] == "league"), league)
none = [n for n, c in kinds if c["kind"] is None]
check("the other 36 are left out", len(none) == 36, len(none))
check("Hong Kong Sixes is excluded even though Test nations play in it", all(ck.classify(m)["kind"] is None for m in M if "Sixes" in m["name"]))
check("an 'unofficial Test' between A teams is excluded", ck.classify(by("Unofficial Test"))["kind"] is None)
check("Sheffield Shield and the Ford Trophy (no Test nation) are excluded", ck.classify(by("Sheffield Shield 2026-27 ".strip()))["kind"] is None and ck.classify(by("Ford Trophy"))["kind"] is None)
check("an ICC league game with no Test nation (UAE v Netherlands) is excluded", ck.classify(by("United Arab Emirates vs Netherlands"))["kind"] is None)
check("Namibia v Ireland counts because Ireland is a Test nation", ck.classify(by("Namibia vs Ireland, 5th ODI"))["kind"] == "international")
check("a Test is the top priority; men's internationals beat women's; leagues rank below internationals",
      ck.classify({"name": "England vs Pakistan, 1st Test, x", "matchType": "test", "teams": ["England", "Pakistan"]})["priority"] == 100
      and ck.classify(by("5th T20I"))["priority"] > ck.classify(by("Womens Big Bash"))["priority"])
check("a women's international (India Women v England Women) is recognised", ck.classify({"name": "India Women vs England Women, 1st ODI, England Women tour of India", "matchType": "odi", "teams": ["India Women", "England Women"]})
      == {"kind": "international", "women": True, "label": "Women's international", "priority": 70})
check("the IPL, the BBL, the men's and women's Hundred and the WPL are recognised",
      [ck.classify({"name": f"A vs B, 1st Match, {n}", "matchType": "t20", "teams": ["A", "B"]}).get("label") for n in
       ("Indian Premier League 2027", "Big Bash League 2026-27", "The Hundred Men's Competition 2026", "The Hundred Women's Competition 2026", "Women's Premier League 2027")]
      == ["IPL", "BBL", "The Hundred", "Women's Hundred", "WPL"])
check("the men's BBL is not mistaken for the women's (and the reverse)", ck.classify({"name": "A vs B, Womens Big Bash League 2026", "matchType": "t20", "teams": ["A Women", "B Women"]})["label"] == "WBBL")

# ---- Which matches for the morning edition of 2 Nov (window starts 31 Oct 23:15 UTC) ----
NOW, START = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc), datetime(2026, 10, 31, 23, 15, tzinfo=timezone.utc)
picked = ck.pick(M, NOW, START)
names = [m["name"].split(",")[0] for m in picked]
check("five matches ended since the last edition: the NZ-India T20I, Afghanistan-Zimbabwe, Namibia-Ireland and two WBBL games", len(picked) == 5 and "New Zealand vs India" in names and "Afghanistan vs Zimbabwe" in names and "Namibia vs Ireland" in names, names)
check("internationals come before the league games", [m["class"]["kind"] for m in picked] == ["international"] * 3 + ["league"] * 2, [m["class"]["kind"] for m in picked])
check("the Pakistan tri-series final (finished the evening before) is not repeated", "Pakistan vs Sri Lanka" not in names)
seen = {picked[0]["id"]}
check("a match already reported is not reported again", picked[0]["id"] not in {m["id"] for m in ck.pick(M, NOW, START, seen=seen)})
check("a match that has not finished by now is left out (an early 'now')", len(ck.pick(M, datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc), START)) < 5)
live = {"id": "t1", "name": "England vs Pakistan, 1st Test, Pakistan tour of England 2027", "matchType": "test", "status": "Day 2: Stumps - England lead by 40 runs",
        "dateTimeGMT": "2026-11-01T10:00:00", "teams": ["England", "Pakistan"], "score": [], "matchStarted": True, "matchEnded": False}
check("a live Test is reported when its status has changed", any(m["id"] == "t1" for m in ck.pick(M + [live], NOW, START, last_status={"t1": "Day 1: Stumps"})))
check("and not again when the status is the same as last time", not any(m["id"] == "t1" for m in ck.pick(M + [live], NOW, START, last_status={"t1": live["status"]})))
check("live matches that are not Test-nation Tests (Sheffield Shield, an A-team Test) are never reported", not any("Shield" in m["name"] or "Unofficial" in m["name"] for m in picked))

# ---- How a result reads ----
nz = by("5th T20I")
h = ck.result_html(nz)
check("a result shows the teams (India in bold), both innings, the result and the series", "New Zealand v <strong>India</strong>" in h and "India 191/8 (20) · New Zealand 195/3 (18)" in h
      and "New Zealand won by 7 wkts" in h and "5th T20I, India tour of New Zealand 2026" in h, h)
check("an all-out innings has no '/10' and overs keep their decimal", ck.innings_line({"r": 109, "w": 10, "o": 17.4, "inning": "Hobart Hurricanes Women Inning 1"}) == "Hobart Hurricanes Women 109 (17.4)")
check("a live match carries a Live tag", '<span class="tag">Live</span>' in ck.result_html(live))
grouped = ck.results_html(picked)
check("results are grouped under International and then WBBL, each with its matches", grouped.index("<h3>International</h3>") < grouped.index("<h3>WBBL</h3>") and grouped.count("<li>") == 5, grouped[:200])
check("no matches, no block", ck.results_html([]) == "")
check("text from the data is escaped", "&lt;" in ck.result_html({**nz, "status": "<b>won</b>"}) and "<b>won" not in ck.result_html({**nz, "status": "<b>won</b>"}))

# ---- The source's budget maths ----
check("with 17 calls used, 7 scorecards fit (100 minus a 10 reserve, minus 17, over 10)", src.scorecards_affordable(17) == 7)
check("near the limit none fit, and an unknown count assumes none used", src.scorecards_affordable(95) == 0 and src.scorecards_affordable(None) == 9)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
