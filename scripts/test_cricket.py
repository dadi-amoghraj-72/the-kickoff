"""Offline tests for cricket (the match list part). Run: python3 scripts/test_cricket.py"""
import json
import re
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
first = M[[i for i, m in enumerate(M) if m["id"] == picked[0]["id"]][0]]
check("a match the data says is still being played (matchEnded false) is left out of the results", picked[0]["id"] not in {m["id"] for m in ck.pick([{**x, "matchEnded": False} if x["id"] == picked[0]["id"] else x for x in M], NOW, START)})
dls = {"id": "dls1", "name": "New Zealand vs India, 1st ODI, India tour of New Zealand 2026", "matchType": "odi", "teams": ["New Zealand", "India"], "dateTimeGMT": "2026-11-04T02:00:00", "matchStarted": True, "matchEnded": True, "score": [], "status": "India won by 5 wkts (DLS)"}
start0, two_hours_in = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc), datetime(2026, 11, 4, 4, 0, tzinfo=timezone.utc)
check("a match that ended early (rain, DLS) is picked even when 'now' is before our nine-hour estimate of an ODI's end: the data says it ended, so it ended (the 4 November New Zealand v India ODI)", [m["id"] for m in ck.pick([dls], two_hours_in, start0)] == ["dls1"])
check("but one the data says is still on is not picked, and one that ended before the window opened is not picked", ck.pick([{**dls, "matchEnded": False}], two_hours_in, start0) == [] and ck.pick([dls], two_hours_in, datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)) == [])
odi_nt = {"id": "n1", "name": "New Zealand vs India, 1st ODI, India tour of New Zealand 2026", "dateTimeGMT": "2026-11-04T02:00:00", "teams": ["New Zealand", "India"], "matchStarted": True, "matchEnded": True, "score": []}
check("a listed match with no matchType (the 4 November New Zealand v India ODI) gets it from its name: ODI, T20I and Test", [ck.match_type(x) for x in (odi_nt, {"name": "A vs B, 5th T20I"}, {"name": "A vs B, 1st Test, tour"}, {"name": "Indian Premier League, 3rd Match"}, {"matchType": "odi", "name": "x"})] == ["odi", "t20", "test", "", "odi"])
fixed = ck.normalise([odi_nt])
check("normalised, that ODI is an international in scope and is picked for the edition; before, with no matchType, it was silently dropped (the original dict is not changed)", ck.classify(fixed[0])["kind"] == "international" and [m["id"] for m in ck.pick(fixed, datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc), datetime(2026, 11, 2, 23, 15, tzinfo=timezone.utc))] == ["n1"] and "matchType" not in odi_nt and ck.classify(odi_nt)["kind"] is None)
run_nt = ck.run(datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc), datetime(2026, 11, 2, 23, 15, tzinfo=timezone.utc), {}, lambda: ([odi_nt], 5), lambda mid: (_ for _ in ()).throw(RuntimeError("no card")), src.scorecards_affordable)
check("end to end: a match with no matchType in the list is in the block (a result line, 'New Zealand v India') and is remembered as reported", run_nt["stats"]["picked"] == 1 and "New Zealand v India" in re.sub(r"<[^>]+>", "", run_nt["html"]) and "n1" in run_nt["state"]["seen"], run_nt["html"][:200])

# ---- D's cricket round of 4 November: heading, big result, scores, Tests, series ----
ck_text = lambda h: re.sub(r"<[^>]+>", "", h.replace('</span><span class="sl">', " · "))  # noqa: E731
check("the scores line puts each score in bold: the winner's in gold (class w), the other in white (class n), the team names plain; a drawn or live match has every score in white", '<b class="w">' in ck.scores_html({**{"teams": ["A", "B"], "score": [{"inning": "A Inning 1", "r": 100, "w": 3}, {"inning": "B Inning 1", "r": 90, "w": 10}]}, "status": "A won by 10 runs"}) and '<b class="w">' not in ck.scores_html({"teams": ["A", "B"], "score": [{"inning": "A Inning 1", "r": 100, "w": 3}], "status": "Match drawn"}) and ck.scores_html({"teams": ["A", "B"], "score": [{"inning": "A Inning 1", "r": 100, "w": 3}], "status": "Match drawn"}).count('class="n"') == 1)
check("short_result: 'India won by 5 wkts - 2nd inns reduced to 32 overs - DLS Target 143' reads 'India won by 5 wickets (DLS)'; the balls-remaining bracket goes; a plain result is unchanged; a Test's day line reads on one line",
      [ck.short_result(x) for x in ("India won by 5 wkts  -  2nd inns reduced to 32 overs - DLS Target 143", "India won by 5 wkts (56b rem) (DLS)", "South Africa won by 176 runs", "Day 3: Stumps - Australia lead by 100 runs", "1 wkt", "")]
      == ["India won by 5 wickets (DLS)", "India won by 5 wickets (DLS)", "South Africa won by 176 runs", "Day 3: Stumps, Australia lead by 100 runs", "1 wicket", ""])
dls_m = {"name": "New Zealand vs India, 1st ODI, India tour of New Zealand 2026", "matchType": "odi", "teams": ["New Zealand", "India"], "matchEnded": True, "status": "India won by 5 wkts  -  2nd inns reduced to 32 overs - DLS Target 143",
         "score": [{"inning": "New Zealand Inning 1", "r": 185, "w": 10, "o": 40.2}, {"inning": "India Inning 1", "r": 143, "w": 5, "o": 22.4}]}
dh = ck.result_html(dls_m)
check("the ODI header: 'New Zealand v India · 1st ODI' once (no tour name, no repeated series line), the result as the main line, then the scores, in that order", "New Zealand v <strong>India</strong> · 1st ODI" in dh and "India tour of New Zealand" not in dh and "India won by 5 wickets (DLS)" in dh and "DLS Target" not in dh
      and dh.index('class="cm"') < dh.index('class="cr"') < dh.index('class="cs"') and "New Zealand 185 (40.2) · India 143/5 (22.4)" in ck_text(dh) and '<span class="sl">New Zealand <b class="n">185 (40.2)</b></span><span class="sl">India <b class="w">143/5 (22.4)</b></span>' in dh and " · India" not in dh.split('class="cs"')[1], dh)
test_m = {"name": "South Africa vs Australia, 3rd Test, Australia tour of South Africa 2026", "matchType": "test", "teams": ["South Africa", "Australia"], "matchEnded": True, "status": "South Africa won by 176 runs",
          "score": [{"inning": "South Africa Inning 1", "r": 329, "w": 10}, {"inning": "Australia Inning 1", "r": 429, "w": 10}, {"inning": "South Africa Inning 2", "r": 387, "w": 10}, {"inning": "Australia Inning 2", "r": 111, "w": 10}]}
live_test = dict(test_m, matchEnded=False, status="Day 4: Stumps - South Africa lead by 100 runs", score=test_m["score"][:2] + [{"inning": "South Africa Inning 2", "r": 187, "w": 4}])
check("a Test's scores read 'South Africa 329 & 387 · Australia 429 & 111'; mid-Test an innings still going shows its wickets ('187/4'), with the other side's one innings", ck.scores_line(test_m) == "South Africa 329 & 387 · Australia 429 & 111" and ck.scores_line(live_test) == "South Africa 329 & 187/4 · Australia 429", ck.scores_line(live_test))
check("series_day: a single date and a Test's date range", [ck.series_day(x) for x in ("Nov 4 2026", "Oct 27-31 2026", "Nov 10 2026", "")] == ["4 Nov", "27–31 Oct", "10 Nov", ""])
test_end = {"id": "te", "name": "South Africa vs Australia, 3rd Test, tour", "matchType": "test", "teams": ["South Africa", "Australia"], "dateTimeGMT": "2026-10-27T08:30:00", "matchStarted": True, "matchEnded": True, "score": [], "status": "South Africa won by 176 runs"}
check("a Test that finished on its fifth day is picked for the next edition (before, its estimated end was ten hours after the start, long past, so a finished Test was never reported); one that finished before the window opened, or was already reported, is not",
      [m["id"] for m in ck.pick([test_end], datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc), datetime(2026, 10, 30, 23, 15, tzinfo=timezone.utc))] == ["te"]
      and ck.pick([test_end], datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc), datetime(2026, 11, 7, 23, 15, tzinfo=timezone.utc)) == []
      and ck.pick([test_end], datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc), datetime(2026, 10, 30, 23, 15, tzinfo=timezone.utc), seen={"te"}) == [])

# the real South Africa v Australia series page and the real 3rd Test scorecard
from kickoff.sources import espn_cricket as _ec  # noqa: E402
SA_ROWS = _ec.parse_series((ROOT / "tests" / "fixtures" / "espn_cricket_series_sa_aus.html").read_text())
SA_PAGE = (ROOT / "tests" / "fixtures" / "espn_cricket_scorecard_sa_aus_test.html").read_text()
sa_card = _ec.parse_scorecard(SA_PAGE)
check("the series page reads all six matches of the tour: three ODIs and three Tests with their date ranges ('Oct 27-31 2026'), the second Test's 'inns & 31 runs' with a real ampersand", [(g["n"], g["format"]) for g in SA_ROWS] == [("1st", "ODI"), ("2nd", "ODI"), ("3rd", "ODI"), ("1st", "Test"), ("2nd", "Test"), ("3rd", "Test")]
      and SA_ROWS[5]["date"] == "Oct 27-31 2026" and SA_ROWS[4]["result"] == "South Africa won by an inns & 31 runs", [(g["n"], g["format"], g["date"]) for g in SA_ROWS])
sa_m = dict(test_m, score=[{"inning": i["inning"].replace(" 1st Innings", " Inning 1").replace(" 2nd Innings", " Inning 2"), "r": i["espn"]["total"]["r"], "w": i["espn"]["total"]["w"], "o": i["espn"]["total"]["o"]} for i in sa_card])
raw_totals = [i["espn"]["total"]["r"] for i in sa_card]
check("independent: the real Test's four innings totals from the page (329, 429, 387, 111) give the scores line 'South Africa 329 & 387 (134.4) · Australia 429 & 111 (57.1)': both innings of each side, the overs of the last one", raw_totals == [329, 429, 387, 111] and ck.scores_line(sa_m) == "South Africa 329 & 387 (134.4) · Australia 429 & 111 (57.1)", raw_totals)
st = ck.series_html(SA_ROWS, "test", current=sa_m)
raw_wins = {"Australia": sum(1 for g in SA_ROWS if g["format"] == "Test" and g["result"].startswith("Australia won")), "South Africa": sum(1 for g in SA_ROWS if g["format"] == "Test" and g["result"].startswith("South Africa won"))}
check("the Test series table: 'Australia v South Africa · Test series', the series stands Australia 1, South Africa 2 (counted from the raw results), the dates are ranges ('27–31 Oct'), the second Test's ampersand is clean, and only Tests are in it (no ODI row)",
      raw_wins == {"Australia": 1, "South Africa": 2} and "Test series" in st and '<span class="ws">1</span>' in st and '<span class="ws">2</span>' in st and st.index('<span class="ws">1</span>') < st.index('<span class="ws">2</span>')
      and "27–31 Oct" in st and "&amp;amp;" not in st and "inns &amp; 31 runs" in st and "ODI" not in st, st[:300])
stale_rows = [dict(g) for g in SA_ROWS]
stale_rows[5] = dict(stale_rows[5], result="South Africa require 90 runs", teams=[dict(t, score="1/0") for t in stale_rows[5]["teams"]])
fixed = ck.patch_series(stale_rows, sa_m)
check("a stale series row for the match being reported (ESPN's page caught mid-match) is put right from our own data: the result line, the scores ('329 & 387', '429 & 111'), and the series is recounted from it", fixed[5]["result"] == "South Africa won by 176 runs" and [t["score"] for t in fixed[5]["teams"]] == ["329 & 387", "429 & 111"]
      and stale_rows[5]["result"] == "South Africa require 90 runs" and ck.series_html(stale_rows, "test", current=sa_m).count("South Africa require") == 0, fixed[5])
nz_rows = [{"n": "1st", "format": "ODI", "venue": "Auckland", "date": "Nov 4 2026", "teams": [{"name": "New Zealand", "abbr": "NZ", "score": "185"}, {"name": "India", "abbr": "IND", "score": "103/1"}], "result": "India require 40 runs", "starts": None},
           {"n": "2nd", "format": "ODI", "venue": "Hamilton", "date": "Nov 7 2026", "teams": [{"name": "New Zealand", "abbr": "NZ", "score": ""}, {"name": "India", "abbr": "IND", "score": ""}], "result": None, "starts": "Starts at 15:00 local time"}]
odi_html = ck.series_html(nz_rows, "odi", current=dls_m)
check("D's 4 November series table: the stale 1st-ODI row ('185 v 103/1*, India require 40 runs', series 0-0) is replaced by our result, so India lead 1-0 with 'India won by 5 wickets (DLS)' and 143/5 against 185; the 2nd ODI is still to come",
      "India require" not in odi_html and "India won by 5 wickets (DLS)" in odi_html and "143/5" in odi_html and '<span class="ws">1</span>' in odi_html and "Starts at 15:00" in odi_html, odi_html[:300])
inn_html = ck.full_scorecard_html(ck.slim_card({"scorecard": sa_card[:1]}, sa_m))
check("the 4s and 6s headings are lower-case 4s and 6s (a class switches off the capitals), and the strike rate heading is SR", '<th class="n lc">4s</th><th class="n lc">6s</th><th class="n">SR</th>' in inn_html)
rows_last = inn_html.split("<tbody>")[1].split("</tbody>")[0].split("<tr")[-2:]
check("extras and total are the last two rows of the SAME batting table (one table for the batting, no separate block), the total row marked bold ('sum total') with the overs and run rate", inn_html.count('<table class="sc">') == 2 and 'class="sum"><td class="name">Extras' in rows_last[0] and 'class="sum total"><td class="name">Total' in rows_last[1] and "run rate" in rows_last[1], rows_last)
css = (ROOT / "kickoff" / "static" / "style.css").read_text()
check("the stylesheet gives the cricket tables room on the right, makes the total bold and keeps '4s' lower-case", "table.sc th:last-child" in css and "padding-right: 12px" in css and "tr.sum.total td { font-weight: 700; }" in css and "th.lc { text-transform: none; }" in css)
full4 = ck.full_scorecard_html(ck.slim_card({"scorecard": sa_card}, sa_m))
last2 = ck.full_scorecard_html(ck.slim_card({"scorecard": sa_card}, sa_m), from_index=2)
check("a Test's earlier innings are not repeated: with from_index 2 only the third and fourth innings have tables (2 batting + 2 bowling) and nothing is printed for the first two (the scores line carries their totals); with 0 all four have tables",
      full4.count('<table class="sc">') == 8 and last2.count('<table class="sc">') == 4 and last2.count('class="inn"') == 2 and "1st innings" not in last2 and "82.3" not in last2, last2[:300])
live_sa = dict(sa_m, id="sa3", matchEnded=False, status="Day 4: Stumps - South Africa lead by 100 runs", matchStarted=True, dateTimeGMT="2026-10-27T08:30:00", score=sa_m["score"][:3])
done_sa = dict(sa_m, id="sa3", matchEnded=True, status="South Africa won by 176 runs", matchStarted=True, dateTimeGMT="2026-10-27T08:30:00")
sa_card_cd = {"scorecard": sa_card, "status": "", "potm": [{"name": "Simon Harmer", "team": "South Africa"}]}
NOW_T, START_T = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc), datetime(2026, 10, 30, 23, 15, tzinfo=timezone.utc)
mid_run = ck.run(NOW_T, START_T, {}, lambda: ([live_sa], 5), lambda mid: (_ for _ in ()).throw(AssertionError("no")), src.scorecards_affordable, espn_card=lambda m: {"scorecard": sa_card[:3], "status": "", "potm": []}, espn_series=lambda m: SA_ROWS)
check("a Test in progress has no series table (no other matches of the series on days 1 to 4), shows its day, and the state remembers that two innings were complete (the third is still going)", 'ser sm tst' not in mid_run["html"] and "Test · Day 4" in mid_run["html"] and mid_run["state"]["test_done"]["sa3"] == 2, (mid_run["state"].get("test_done"), mid_run["html"][:200]))
day4 = ck.run(NOW_T, START_T, {"test_done": {"sa3": 2}}, lambda: ([dict(live_sa, status="Day 4: Stumps - Australia need 200 runs", score=sa_m["score"])], 5), lambda mid: (_ for _ in ()).throw(AssertionError("no")), src.scorecards_affordable, espn_card=lambda m: sa_card_cd, espn_series=lambda m: SA_ROWS)
check("end of day 4 (South Africa's second innings done, Australia's second in progress): innings 3 and 4 move (2 complete before), and the state records 3 complete", day4["html"].count('class="inn"') == 2 and day4["state"]["test_done"]["sa3"] == 3, (day4["state"].get("test_done"), day4["html"].count('class="inn"')))
end_run = ck.run(NOW_T, START_T, day4["state"], lambda: ([done_sa], 5), lambda mid: (_ for _ in ()).throw(AssertionError("no")), src.scorecards_affordable, espn_card=lambda m: sa_card_cd, espn_series=lambda m: SA_ROWS)
check("D's day-5 rule: South Africa's second innings was complete at the end of day 4, so day 5 shows only Australia's second innings in full (one innings table pair), the result, the match summary and the series table, and the state records all four", 'ser sm tst' in end_run["html"] and end_run["html"].count('class="inn"') == 1 and "Australia</strong> 2nd innings" in end_run["html"] and "South Africa won by 176 runs" in end_run["html"] and 'class="sc ms"' in end_run["html"] and end_run["state"]["test_done"]["sa3"] == 4, (end_run["state"].get("test_done"), end_run["html"].count('class="inn"')))
rain = ck.run(NOW_T, START_T, day4["state"], lambda: ([dict(live_sa, status="Day 5: No play - rain", score=sa_m["score"])], 5), lambda mid: (_ for _ in ()).throw(AssertionError("no")), src.scorecards_affordable, espn_card=lambda m: sa_card_cd, espn_series=lambda m: SA_ROWS)
check("a day with no play (the scores are the same as at the last edition): the day flag, the status and the scores, and no scorecard repeated", "Test · Day 5" in rain["html"] and "No play" in rain["html"] and '<table class="sc">' not in rain["html"] and "sc ms" not in rain["html"] and "ser sm tst" not in rain["html"], rain["html"][:300])
ms = ck.match_summary_html(ck.slim_card({"scorecard": sa_card}, sa_m))
raw_inns = [(i["inning"], max(i["batting"], key=lambda b: b["r"]), max(i["bowling"], key=lambda b: (b["w"], -b["r"]))) for i in sa_card]
check("the match summary of the real Test: four innings, each a shaded row with the batting team and score ('South Africa 329') and its label, then the top batter with his runs and the best bowler with figures, all from the raw scorecard (the highest score and most wickets of each innings are found separately)",
      ms.count('class="sum"') == 4 and ms.startswith('<div class="table-wrap"><table class="sc ms">') and "Match summary" in ms
      and all(f"<td class=\"n\"><strong>{b['r']}" in ms for _, b, _ in raw_inns) and all(f"{w['bowler']['name']}</td>" in ms or w["bowler"]["name"] in ms for _, _, w in raw_inns) and ms.count("<tr>") == 5, ms[:400])
check("the match summary marks a not-out top batter with * and leaves an innings with no wicket for the bowler blank, and gives nothing without innings", "*" in ck.match_summary_html([{"team": "A", "label": "1st innings", "runs": 50, "wickets": 0, "batting": [{"name": "X", "r": 30, "b": 20, "out": "not out"}], "bowling": []}]) and ck.match_summary_html([]) == "")
live = {"id": "t1", "name": "England vs Pakistan, 1st Test, Pakistan tour of England 2027", "matchType": "test", "status": "Day 2: Stumps - England lead by 40 runs",
        "dateTimeGMT": "2026-11-01T10:00:00", "teams": ["England", "Pakistan"], "score": [], "matchStarted": True, "matchEnded": False}
check("a live Test is reported when its status has changed", any(m["id"] == "t1" for m in ck.pick(M + [live], NOW, START, last_status={"t1": "Day 1: Stumps"})))
check("and again the next day even when nothing changed: a Test in progress is shown every day", any(m["id"] == "t1" for m in ck.pick(M + [live], NOW, START, last_status={"t1": live["status"]})))
check("live matches that are not Test-nation Tests (Sheffield Shield, an A-team Test) are never reported", not any("Shield" in m["name"] or "Unofficial" in m["name"] for m in picked))

# ---- How a result reads ----
nz = by("5th T20I")
h = ck.result_html(nz)
check("a result shows the teams (India in bold), both innings, the result and the series", "New Zealand v <strong>India</strong> · 5th T20I" in h and "India 191/8 (20) · New Zealand 195/3 (18)" in ck_text(h) and '<b class="w">195/3 (18)</b>' in h and '<b class="n">191/8 (20)</b>' in h
      and "New Zealand won by 7 wickets" in h and "India tour of New Zealand" not in h and h.index('class="cr"') < h.index('class="cs"'), h)
check("an all-out innings has no '/10' and overs keep their decimal", ck.innings_line({"r": 109, "w": 10, "o": 17.4, "inning": "Hobart Hurricanes Women Inning 1"}) == "Hobart Hurricanes Women 109 (17.4)")
live_t20 = {**live, "matchType": "t20", "name": "England vs Pakistan, 1st T20I, tour"}
check("a live limited-overs match carries an In progress tag; a live Test carries its day flag instead (no second tag)", '<span class="tag">In progress</span>' in ck.result_html(live_t20) and '<span class="tag">In progress</span>' not in ck.result_html(live) and "Test · Day 2" in ck.result_html(live))
grouped = ck.results_html(picked)
check("results are grouped under International and then WBBL, each with its matches", grouped.index("<h3>International</h3>") < grouped.index("<h3>WBBL</h3>") and grouped.count("<li>") == 5, grouped[:200])
check("no matches, no block", ck.results_html([]) == "")
check("text from the data is escaped", "&lt;" in ck.result_html({**nz, "status": "<b>won</b>"}) and "<b>won" not in ck.result_html({**nz, "status": "<b>won</b>"}))

# ---- The source's budget maths ----
check("with 17 calls used, 7 scorecards fit (100 minus a 10 reserve, minus 17, over 10)", src.scorecards_affordable(17) == 7)
check("near the limit none fit, and an unknown count assumes none used", src.scorecards_affordable(95) == 0 and src.scorecards_affordable(None) == 9)

# ---- The data's messy innings labels ----
tn = ["Namibia", "Ireland"]
check("an upper-case-less label is matched to the real team name", ck.team_of("ireland Inning 1", tn) == "Ireland")
check("a joined label ('Namibia,Ireland Inning 1') gives the first team", ck.team_of("Namibia,Ireland Inning 1", tn) == "Namibia")
check("a label for a team not in the list is returned cleaned, not lost", ck.team_of("Mystery XI Inning 2", tn) == "Mystery XI")
check("innings lines use the proper team name", ck.innings_line({"r": 129, "w": 10, "o": 33.1, "inning": "ireland Inning 1"}, tn) == "Ireland 129 (33.1)"
      and ck.innings_line({"r": 131, "w": 5, "o": 21.2, "inning": "Namibia,Ireland Inning 1"}, tn) == "Namibia 131/5 (21.2)")
nam = by("Namibia vs Ireland, 5th ODI")
check("the real Namibia v Ireland result now reads cleanly", "Ireland 129 (33.1) · Namibia 131/5 (21.2)" in ck_text(ck.result_html(nam)) and "Namibia won by 5 wickets" in ck.result_html(nam), ck.result_html(nam))
wb = by("Sydney Thunder Women vs Brisbane Heat Women")
check("and so does the real WBBL result", "Brisbane Heat W 178/5 (20) · Sydney Thunder W 180/4 (16.4)" in ck_text(ck.result_html(wb)) and "6th Match" in ck.result_html(wb) and "Big Bash" not in ck.result_html(wb), ck.result_html(wb))
def bat(name, r, b, out="b X"):
    return {"batsman": {"name": name}, "r": r, "b": b, "4s": 1, "6s": 1, "sr": 100, "dismissal-text": out}


def bowl(name, w, r=30, o=4):
    return {"bowler": {"name": name}, "o": o, "m": 0, "r": r, "w": w}


messy = {"matchType": "odi", "teams": ["Namibia", "Ireland"], "name": "Namibia vs Ireland, 5th ODI, tour", "status": "x",
         "scorecard": [{"inning": "Namibia,Ireland Inning 1", "batting": [bat("N Batter", 104, 90)], "bowling": [bowl("I Bowler", 5)]}]}
so2 = ck.standouts(messy, messy)
check("with a garbled label the bowler is still credited to the right side (Ireland bowled to Namibia's batters)",
      {(o["name"], o["team"], o["against"]) for o in so2} == {("N Batter", "Namibia", "Ireland"), ("I Bowler", "Ireland", "Namibia")}, so2)

# ---- Standouts from a real scorecard ----
CARD = json.loads((ROOT / "tests" / "fixtures" / "cricket_scorecard_nz_ind.json").read_text())
nzind_m = next(m for m in M if m["name"].startswith("New Zealand vs India"))
check("a good scorecard passes: the real New Zealand v India T20I card agrees with the match's totals (runs and wickets)", ck.card_consistent(CARD, nzind_m), nzind_m["score"])
bat = lambda name, out, r, b: {"batsman": {"name": name}, "dismissal-text": out, "r": r, "b": b}  # noqa: E731
stale = {"scorecard": [{"inning": "India Inning 1", "batting": [bat("Rohit Sharma", "c Santner b Jamieson", 0, 6), bat("Shubman Gill", "batting", 36, 51), bat("Virat Kohli", "batting", 59, 43)], "bowling": []}], "potm": []}
stale_m = {"teams": ["New Zealand", "India"], "score": [{"inning": "New Zealand Inning 1", "r": 185, "w": 10, "o": 40.2}, {"inning": "India Inning 1", "r": 143, "w": 5, "o": 22.4}]}
stale_m2 = dict(stale_m, score=[stale_m["score"][1]])
check("D's 4 November example is refused: the mid-innings card shows India's Gill and Kohli still 'batting' (one batter out) against a final total of 143/5, so it contradicts the match and is not shown", not ck.card_consistent(stale, stale_m2))
full = {"scorecard": [{"inning": "India Inning 1", "batting": [bat("A", "c X b Y", 0, 6), bat("B", "c X b Y", 37, 56), bat("C", "c X b Y", 74, 51), bat("D", "c X b Y", 15, 13), bat("E", "c X b Y", 0, 2), bat("F", "not out", 3, 5), bat("G", "not out", 5, 3)], "bowling": []}]}
check("the same innings with five batters out and two not out (143/5, 134 off the bats) is consistent", ck.card_consistent(full, stale_m2))
check("more runs off the bats than the total is refused, and a card with no innings or no score to compare is not refused", not ck.card_consistent({"scorecard": [{"inning": "x", "batting": [bat("A", "not out", 200, 100)]}]}, {"score": [{"r": 150, "w": 0}]}) and ck.card_consistent({"scorecard": []}, stale_m) and ck.card_consistent(stale, {"score": []}))
check("a retired batter (one fewer out than wickets, or one more) is tolerated", ck.card_consistent({"scorecard": [{"inning": "x", "batting": [bat("A", "retired hurt", 10, 10), bat("B", "c X b Y", 20, 20), bat("C", "not out", 5, 5)]}]}, {"score": [{"r": 60, "w": 2}]}))
run_stale = ck.run(datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc), datetime(2026, 11, 2, 23, 15, tzinfo=timezone.utc), {}, lambda: ([{**odi_nt, "matchType": "odi", "score": stale_m["score"]}], 5), lambda mid: (stale, 15), src.scorecards_affordable)
check("end to end: the stale card is not shown and not saved (no 'Gill batting'), but the match and its result are still in the block", run_stale["stats"]["picked"] == 1 and "batting" not in re.sub(r"<[^>]+>", " ", run_stale["html"]).lower().replace("batting order", "") and "n1" in run_stale["state"]["seen"] and "n1" not in run_stale["state"]["cards"] and "New Zealand v" in re.sub(r"<[^>]+>", "", run_stale["html"]), run_stale["html"][:300])
real_card_consistent = ck.card_consistent
ck.card_consistent = lambda card, match: True   # the older tests below hand ONE saved card to every match; the real check would rightly refuse it for the others
so = ck.standouts(CARD, CARD)
check("the real NZ v India T20 scorecard: Iyer's fast fifty, Milne's four-for and three ordinary fifties (Kishan, Seifert, Phillips)", sorted((o["name"], o["kind"]) for o in so) ==
      [("Adam Milne", "four-for"), ("Glenn Phillips", "fifty"), ("Ishan Kishan", "fifty"), ("Shreyas Iyer", "fast fifty"), ("Tim Seifert", "fifty")], [(o["name"], o["kind"]) for o in so])
iyer = next(o for o in so if o["name"] == "Shreyas Iyer")
milne = next(o for o in so if o["name"] == "Adam Milne")
check("Iyer: 50 off 23 balls for India, against New Zealand", (iyer["runs"], iyer["balls"], iyer["team"], iyer["against"]) == (50, 23, "India", "New Zealand"), iyer)
check("Milne: 4 for 19 for New Zealand (the bowling side is the other team), against India", (milne["wickets"], milne["runs_conceded"], milne["team"], milne["against"]) == (4, 19, "New Zealand", "India"), milne)
check("Seifert's 93 off 50, Kishan's 61 off 32 and Phillips' 65 off 38 are ordinary T20 fifties: standouts, but not fast fifties", all(o["kind"] == "fifty" for o in so if o["name"] in ("Tim Seifert", "Ishan Kishan", "Glenn Phillips")) and sum(1 for o in so if o["kind"] == "fifty") == 3)

# ---- The thresholds, exactly ----
def bat(name, r, b, out="b X"):
    return {"batsman": {"name": name}, "r": r, "b": b, "4s": 1, "6s": 1, "sr": 100, "dismissal-text": out}


def bowl(name, w, r=30, o=4):
    return {"bowler": {"name": name}, "o": o, "m": 0, "r": r, "w": w}


def card_of(batting=(), bowling=(), fmt="t20"):
    c = {"matchType": fmt, "name": "A vs B, 1st T20I, Series 2026", "status": "A won", "teams": ["A", "B"],
         "scorecard": [{"inning": "A Inning 1", "batting": list(batting), "bowling": list(bowling)}]}
    return c, c


kinds = lambda batting=(), bowling=(), fmt="t20": [(o["name"], o["kind"]) for o in ck.standouts(*card_of(batting, bowling, fmt))]  # noqa: E731
check("100 is a century; 99 in a T20 is a fifty (any T20 fifty is a standout, D 2026-11-05)", kinds([bat("P", 100, 60)]) == [("P", "century")] and kinds([bat("P", 99, 60)]) == [("P", "fifty")])
check("a century that is also fast is a century, not a fast fifty", kinds([bat("P", 104, 22)]) == [("P", "century")])
check("50 off 25 balls is a fast fifty (the Star Of The Night one), 50 off 26 is an ordinary fifty, 49 off 20 is nothing", kinds([bat("P", 50, 25)]) == [("P", "fast fifty")] and kinds([bat("P", 50, 26)]) == [("P", "fifty")] and kinds([bat("P", 49, 20)]) == [])
check("a missing ball count (0) never counts as a fast fifty (it is an ordinary fifty)", kinds([bat("P", 60, 0)]) == [("P", "fifty")])
check("five wickets is a five-wicket haul in any format; four is not in an ODI", kinds(bowling=[bowl("Q", 5)], fmt="odi") == [("Q", "five-for")] and kinds(bowling=[bowl("Q", 4)], fmt="odi") == [])
check("four wickets is a standout in a T20 only", kinds(bowling=[bowl("Q", 4)], fmt="t20") == [("Q", "four-for")] and kinds(bowling=[bowl("Q", 3)], fmt="t20") == [])
check("a five-wicket haul in a T20 is a five-for, not a four-for", kinds(bowling=[bowl("Q", 5)], fmt="t20") == [("Q", "five-for")])
check("a not-out century is marked", ck.standouts(*card_of([bat("P", 120, 70, "not out")]))[0]["not_out"] is True)

# ---- Ranking ----
pool = [{"kind": "four-for", "wickets": 4, "runs_conceded": 12, "name": "D"}, {"kind": "fast fifty", "balls": 20, "runs": 55, "name": "C"},
        {"kind": "five-for", "wickets": 5, "runs_conceded": 20, "name": "B"}, {"kind": "century", "runs": 101, "balls": 60, "name": "A"},
        {"kind": "century", "runs": 140, "balls": 80, "name": "A2"}, {"kind": "five-for", "wickets": 6, "runs_conceded": 30, "name": "B2"}]
check("ranked: centuries (biggest first), five-fors (most wickets first), fast fifties, then four-fors", [o["name"] for o in ck.rank(pool, 10)] == ["A2", "A", "B2", "B", "C", "D"], [o["name"] for o in ck.rank(pool, 10)])
check("at most five are shown", len(ck.rank(pool * 2)) == 5)
check("fast fifties: fewer balls first, then more runs", [o["name"] for o in ck.rank([{"kind": "fast fifty", "balls": 24, "runs": 51, "name": "X"}, {"kind": "fast fifty", "balls": 24, "runs": 70, "name": "Y"},
      {"kind": "fast fifty", "balls": 18, "runs": 50, "name": "Z"}])] == ["Z", "Y", "X"])

# ---- How a standout reads ----
hi, hm = ck.standout_html(iyer), ck.standout_html(milne)
check("a fast fifty line: name (team): runs (balls), fours, sixes v opponent (D, 2026-11-05)", "<strong>Shreyas Iyer</strong> (India): 50 (23), 3 fours, 4 sixes v New Zealand" in hi
      and "5th T20I" not in hi and "won by" not in hi, hi)
check("a bowling line: name (team): wickets/runs (overs ov) v opponent", "<strong>Adam Milne</strong> (New Zealand): 4/19 (4 ov, 4.8 econ) v India" in hm, hm)
check("no standouts, no heading", ck.standouts_html([]) == "" and 'class="standouts"' in ck.standouts_html(so))
check("names are escaped", "&lt;" in ck.standout_html({**iyer, "name": "<b>"}) and "<b>" not in ck.standout_html({**iyer, "name": "<b>"}).replace("<strong>", ""))

# ---- The whole block, within the call budget ----
cards = []


def fake_card(mid, used_ref):
    cards.append(mid)
    used_ref[0] += 10
    return CARD, used_ref[0]


def block(used0, st=None, matches=None, fail=False):
    used = [used0]
    cards.clear()

    def get_card(mid):
        if fail:
            raise RuntimeError("scorecard unavailable")
        return fake_card(mid, used)
    return ck.run(NOW, START, st or {}, lambda: (matches if matches is not None else M, used[0]), get_card, src.scorecards_affordable)


b = block(17)
check("with plenty of budget every picked match is checked: 5 matches, 5 scorecards", b["stats"]["picked"] == 5 and b["stats"]["checked"] == 5 and len(cards) == 5 and b["stats"]["skipped"] == 0, b["stats"])
check("the block has International and WBBL results, then a Standouts list", b["html"].index("<h3>International</h3>") < b["html"].index("<h3>WBBL</h3>") < b["html"].index("<h3>Standouts</h3>"))
check("the calls used are carried back (17 + 5 x 10 = 67)", b["used"] == 67, b["used"])
check("the matches shown are remembered, so tomorrow does not repeat them", len(b["state"]["seen"]) == 5 and block(17, b["state"])["html"] == "")
tight = block(80)
check("with 80 calls used only 1 scorecard fits: the most important match is checked, the rest are skipped but their results still show",
      tight["stats"]["checked"] == 1 and tight["stats"]["skipped"] == 4 and tight["html"].count("<li><span class=\"cm\">") == 5, tight["stats"])
check("the checked count is in the stats, not on the page (developer chatter, D 2026-11-05)", "checked in" not in tight["html"] and tight["stats"]["checked"] == 1 and tight["stats"]["picked"] == 5, tight["stats"])
check("a failing scorecard loses only the standouts for that match: the results are all still shown", block(17, fail=True)["html"].count('<li><span class="cm">') == 5 and block(17, fail=True)["stats"]["checked"] == 0)
check("no matches in the window means no cricket block", block(17, matches=[])["html"] == "")
check("a live Test is in the block every day, even with the same status as yesterday",
      block(17, st={"status": {"t1": live["status"]}}, matches=[live])["html"].count("Test · Day 2") == 1)

# ---- Which matches get a full scorecard ----
T = lambda name, teams, typ="odi": {"name": name, "matchType": typ, "teams": teams}  # noqa: E731
check("men's matches with India, Australia, England, Pakistan, New Zealand or South Africa are tier 1",
      [ck.scorecard_tier(by(n)) for n in ("5th T20I", "Sri Lanka vs England, 6th Match")] == [1, 1]
      and ck.scorecard_tier(T("Pakistan vs Bangladesh, 1st Test, Series 2027", ["Pakistan", "Bangladesh"], "test")) == 1
      and ck.scorecard_tier(T("South Africa vs Zimbabwe, 2nd T20I, tour", ["South Africa", "Zimbabwe"], "t20")) == 1)
check("Namibia v Ireland, Afghanistan v Zimbabwe and Sri Lanka v West Indies are tier 3 (result line only)",
      [ck.scorecard_tier(by("Namibia vs Ireland, 5th ODI")), ck.scorecard_tier(by("Afghanistan vs Zimbabwe, 3rd T20I")),
       ck.scorecard_tier(T("Sri Lanka vs West Indies, 1st ODI, tour", ["Sri Lanka", "West Indies"]))] == [3, 3, 3])
check("every men's IPL match is tier 2, whoever plays", ck.scorecard_tier({"name": "Punjab Kings vs Rajasthan Royals, 5th Match, Indian Premier League 2027", "matchType": "t20", "teams": ["Punjab Kings", "Rajasthan Royals"]}) == 2)
check("women's matches are never tier 1 or 2, even India Women v England Women or the WBBL",
      ck.scorecard_tier(T("India Women vs England Women, 1st ODI, tour", ["India Women", "England Women"])) == 3 and ck.scorecard_tier(by("Womens Big Bash")) == 3)
check("India A and unofficial matches are excluded altogether", ck.classify(by("Unofficial Test"))["kind"] is None)

# ---- The slimmed scorecard, checked against the screenshots of the real match ----
sl = ck.slim_card(CARD, CARD)
ind, nzi = sl
check("two innings: India 191/8 in 20 overs, New Zealand 195/3 in 18", (ind["team"], ind["runs"], ind["wickets"], ind["overs"], nzi["team"], nzi["runs"], nzi["wickets"], nzi["overs"])
      == ("India", 191, 8, 20, "New Zealand", 195, 3, 18), (ind["runs"], nzi["runs"]))
check("India's extras are 7: wides 4, no-balls 1, and 2 byes or leg-byes (the screenshot says b 1, lb 1, nb 1, w 4)", ind["extras"] == {"total": 7, "w": 4, "nb": 1, "b_lb": 2}, ind["extras"])
check("New Zealand's extras are 5: wides 3 and 2 leg-byes (the screenshot says lb 2, w 3)", nzi["extras"] == {"total": 5, "w": 3, "nb": 0, "b_lb": 2}, nzi["extras"])
check("batting: 10 India batters with how each was out; the bowlers belong to the other team", len(ind["batting"]) == 10 and ind["batting"][0]["out"] == "c Bracewell b Milne" and ind["bowling_team"] == "New Zealand")
check("run rates from runs and overs: India 9.55 and New Zealand 10.83, as on the screenshots", f"{ind['runs'] / ck.overs_decimal(ind['overs']):.2f}" == "9.55" and f"{nzi['runs'] / ck.overs_decimal(nzi['overs']):.2f}" == "10.83")
check("dismissals use surnames, as on a real scorecard: 'c Bracewell b Milne', 'c and b Nathan Smith' stays readable, 'not out' is untouched",
      ck.short_dismissal("c Michael Bracewell b Adam Milne", ["Adam Milne", "Michael Bracewell"]) == "c Bracewell b Milne"
      and ck.short_dismissal("not out", [None, None]) == "not out" and ck.short_dismissal("c & b Nathan Smith", ["Nathan Smith", None]) == "c & b Smith"
      and ck.short_dismissal("b Nitish Kumar Reddy", ["Nitish Kumar Reddy"]) == "b Reddy")
check("17.4 overs is 17 overs and 4 balls: 17.667 for a run rate", abs(ck.overs_decimal(17.4) - 17.6667) < 0.001 and ck.overs_decimal(20) == 20)

# ---- The scorecard as HTML ----
fh = ck.full_scorecard_html(sl)
check("India's innings: heading with total and overs, then each batter's R B 4s 6s SR", "<strong>India</strong> 191/8 (20 ov)" in fh and "Ishan Kishan" in fh and "c Smith b Tickner" in fh
      and '<td class="n"><strong>61</strong></td><td class="n">32</td><td class="n">5</td><td class="n">5</td><td class="n">190.63</td>' in fh, fh[:400])
check("extras and total rows, with the run rate", "Extras" in fh and "w 4, nb 1, b/lb 2" in fh and "Total" in fh and "20 ov, run rate 9.55" in fh and "18 ov, run rate 10.83" in fh)
check("a not-out batter reads 'not out'", ">not out<" in fh)
check("the bowling table has O M R W Econ WD NB: Milne 4-0-19-4, economy 4.75 as on the scorecard (computed exactly, not the API's 4.8)",
      "<th>Bowling</th>" in fh and '<td class="n">4</td><td class="n">0</td><td class="n">19</td><td class="n"><strong>4</strong></td><td class="n">4.75</td><td class="n">1</td><td class="n">0</td>' in fh,
      fh[fh.index("<th>Bowling</th>"):][:700])
check("economy matches the real scorecard for Bhuvneshwar (10.25), Chakravarthy (11.25) and Bracewell (19.00)", all(x in fh for x in ("10.25", "11.25", "19.00")))
check("an all-out innings shows its total without '/10'", "/10" not in ck.full_scorecard_html([{**ind, "wickets": 10, "runs": 150}]))
check("names are escaped", "&lt;" in ck.full_scorecard_html([{**ind, "batting": [{**ind["batting"][0], "name": "<b>"}]}]))
check("no innings, no HTML", ck.full_scorecard_html([]) == "" and ck.full_scorecard_html(None) == "")
check("what the data does not carry is not invented: no fall of wickets, did not bat or minutes", all(w not in fh.lower() for w in ("fall of wickets", "did not bat", "minutes")))
entry = {"innings": sl, "standouts": []}
check("a tier 1 result carries its scorecard under the heading, the result and the scores", ck.result_html(nz, entry).index("won by") < ck.result_html(nz, entry).index('<table class="sc">'))
check("a tier 3 result never shows a scorecard, even if one was bought", '<table class="sc">' not in ck.result_html(by("Namibia vs Ireland, 5th ODI"), entry))
check("with no scorecard bought a tier 1 result shows only the result", '<table class="sc">' not in ck.result_html(nz))

# ---- Scorecards are paid for once ----
first = block(17)
check("the first run stores each scorecard's innings and standouts", len(first["state"]["cards"]) == 5 and all({"innings", "standouts"} <= set(c) for c in first["state"]["cards"].values()))
state_no_seen = {"cards": first["state"]["cards"]}
second = block(95, state_no_seen)
check("a second run of the same matches buys nothing, even with only 5 calls left, and shows the same scorecards", len(cards) == 0 and second["stats"]["checked"] == 5
      and second["html"].count('<table class="sc">') > 0 and second["used"] == 95, (len(cards), second["stats"]))
check("the cached standouts are used too (the test feeds one card to five matches, so the top five are all Iyer)", second["html"].count("Shreyas Iyer") >= 5 and "<h3>Standouts</h3>" in second["html"])
mixed = block(80, {"cards": {nz["id"]: first["state"]["cards"][nz["id"]]}})
check("one cached match plus one new purchase fits the budget: 2 of 5 checked, calls = 80 + 10", mixed["stats"]["checked"] == 2 and mixed["used"] == 90 and len(cards) == 1, mixed["stats"])
many = {"cards": {f"m{i}": {"innings": [], "standouts": []} for i in range(80)}}
check("the cache keeps only the 60 most recent scorecards", len(block(17, many)["state"]["cards"]) == 60)
check("the cache survives being saved as JSON and read back", block(95, json.loads(json.dumps(state_no_seen)))["html"].count('<table class="sc">') == second["html"].count('<table class="sc">'))
old_format = {"cards": {nz["id"]: {"summary": [], "standouts": []}}}
check("an old-format cache entry (from before full scorecards) is ignored and bought again, not shown broken", block(17, old_format)["stats"]["checked"] == 5 and len(cards) == 5)

# ---- D, 2026-11-04: women's sides read with a W; scores on two lines in batting order ----
check("wname: 'India Women' -> 'India W', 'Sydney Sixers Women' -> 'Sydney Sixers W', inside a result line too; 'Women's' (a league) and men's names are left alone",
      ck.wname("India Women") == "India W" and ck.wname("Sydney Sixers Women") == "Sydney Sixers W" and ck.wname("India Women won by 5 wickets") == "India W won by 5 wickets"
      and ck.wname("Women's Big Bash") == "Women's Big Bash" and ck.wname("India") == "India" and ck.wname("") == "")
wm = {"name": "India Women vs Australia Women, 2nd ODI, Australia Women tour of India 2026", "matchType": "odi", "teams": ["India Women", "Australia Women"], "matchEnded": True,
      "status": "Australia Women won by 3 wickets", "score": [{"inning": "India Women Inning 1", "r": 245, "w": 10, "o": 49.2}, {"inning": "Australia Women Inning 1", "r": 246, "w": 7, "o": 48.5}]}
wh = ck.result_html(wm)
check("a women's match shows 'India W v Australia W', 'Australia W won by 3 wickets' and each score line with W - the word 'Women' appears nowhere in the block",
      "India <strong>W</strong>" not in wh and "India W v Australia W" in ck_text(wh) and "Australia W won by 3 wickets" in wh and "Women" not in wh, wh)
check("the scores are two separate lines in batting order, 'India W 245 (49.2)' then 'Australia W 246/7 (48.5)', no dot between them",
      ck_text(wh).count("India W 245 (49.2)") == 1 and wh.index("India W <b") < wh.index("Australia W <b") and wh.count('<span class="sl">') == 2 and "·" not in wh.split('class="cs"')[1], wh)
check("the colours stay: the winner's score gold (w), the other white (n)", 'Australia W <b class="w">246/7 (48.5)</b>' in wh and 'India W <b class="n">245 (49.2)</b>' in wh, wh)
bat2 = dict(wm, teams=["India Women", "Australia Women"], score=[wm["score"][1], wm["score"][0]], status="India Women won by 1 run")
check("batting order follows the innings, not the team order of the listing: Australia W batted first here, so they are the first line", ck.result_html(bat2).index("Australia W <b") < ck.result_html(bat2).index("India W <b"))

# ---- D, 2026-11-04: Sunrisers Hyderabad's row in gold in the IPL's table ----
ipl_rows = [{"pos": 1, "team": "RCB", "name": "Royal Challengers Bengaluru", "p": 14, "w": 9, "l": 5, "t": 0, "nr": 0, "pts": 18, "nrr": 0.4}, {"pos": 2, "team": "SRH", "name": "Sunrisers Hyderabad", "p": 14, "w": 8, "l": 6, "t": 0, "nr": 0, "pts": 16, "nrr": 0.1}]
tbl = ck.table_html("IPL", ipl_rows)
check("the IPL table: only the Sunrisers Hyderabad row carries the gold class; another league's table never does", tbl.count('class="hl"') == 1 and "SRH" in tbl.split('class="hl"')[1].split("</tr>")[0] and ck.table_html("WBBL", ipl_rows).count("hl") == 0, tbl[:300])

check("singular figures: 1 four, 1 six, never '1 sixes'; a zero is left out (D, 2026-11-05)", "1 four, 1 six v" in ck.standout_html({**iyer, "fours": 1, "sixes": 1}) and "2 fours v" in ck.standout_html({**iyer, "fours": 2, "sixes": 0}) and "sixes" not in ck.standout_html({**iyer, "fours": 2, "sixes": 0}))

# ---- the day of a Test from the start date when the status line has none (D, 2026-11-05)
_t = {"matchType": "test", "dateTimeGMT": "2026-11-03T04:00:00", "status": "Stumps"}
_utc = lambda d, h=23: __import__("datetime").datetime(2026, 11, d, h, 15, tzinfo=__import__("datetime").timezone.utc)  # noqa: E731
check("the day is counted from the start date: day 1 on the first day, day 3 on the third, never above 5", ck.day_of(_t, None, _utc(3)) == 1 and ck.day_of(_t, None, _utc(5)) == 3 and ck.day_of(_t, None, _utc(20)) == 5)
check("a status line that names the day wins, and with no clock the day stays unknown", ck.day_of({**_t, "status": "Day 4: Lunch"}, None, _utc(5)) == 4 and ck.day_of(_t) is None)
check("the heading says '2nd Test · Day 3' and the pill stays 'Test · in progress'", "2nd Test · Day 3" in ck.result_html({**_t, "id": "x", "name": "Bangladesh vs West Indies, 2nd Test, WI tour", "teams": ["Bangladesh", "West Indies"], "matchStarted": True, "matchEnded": False}, None, "", 0, _utc(5)))

# ---- fifties and four-wicket hauls only in T20; ODIs and Tests keep hundreds and five-fors (D, 2026-11-05)
_odi = {"matchType": "odi", "name": "A vs B, 1st ODI", "teams": ["A", "B"]}
_t20 = {**_odi, "matchType": "t20"}
_cardb = lambda bat_, w=None: {"scorecard": [{"inning": "A Inning 1", "batting": [{"batsman": {"name": "P"}, "r": bat_[0], "b": bat_[1], "4s": 4, "6s": 2, "dismissal-text": "c x b y"}], "bowling": [{"bowler": {"name": "Q"}, "w": w or 0, "r": 22, "o": 4, "m": 0}]}]}  # noqa: E731
check("a fast fifty counts in a T20 and not in an ODI; a century counts in both", [o["kind"] for o in ck.standouts(_cardb((50, 24)), _t20)] == ["fast fifty"] and ck.standouts(_cardb((50, 24)), _odi) == [] and [o["kind"] for o in ck.standouts(_cardb((104, 61)), _odi)] == ["century"])
check("a four-wicket haul counts in a T20 and not in an ODI; a five-for counts in both", [o["kind"] for o in ck.standouts(_cardb((0, 1), 4), _t20) if o["kind"] != "kohli"] == ["four-for"] and not [o for o in ck.standouts(_cardb((0, 1), 4), _odi) if o["kind"] in ("four-for", "five-for")] and [o["kind"] for o in ck.standouts(_cardb((0, 1), 5), _odi)] == ["five-for"])

# ---- economy, ten in a match (D, 2026-11-05)
_ctest = {"matchType": "test", "name": "A vs B, 1st Test", "teams": ["A", "B"]}
_bowl = lambda inning, name, w, r_, o: {"inning": inning, "batting": [], "bowling": [{"bowler": {"name": name}, "w": w, "r": r_, "o": o, "m": 0}]}  # noqa: E731
check("3 or 4 wickets under 5 an over is a standout in a T20 and an ODI, not in a Test (every Test spell is under 5)",
      [o["kind"] for o in ck.standouts({"scorecard": [_bowl("A Inning 1", "Q", 3, 18, 4)]}, _t20)] == ["economy"] and [o["kind"] for o in ck.standouts({"scorecard": [_bowl("A Inning 1", "Q", 3, 40, 10)]}, _odi)] == ["economy"]
      and ck.standouts({"scorecard": [_bowl("A Inning 1", "Q", 3, 40, 20)]}, _ctest) == [])
check("under 5 means strictly under: 3 for 20 off 4 overs (5.0) is not a standout, 3 for 19 off 4 (4.75) is", ck.standouts({"scorecard": [_bowl("A Inning 1", "Q", 3, 20, 4)]}, _t20) == [] and len(ck.standouts({"scorecard": [_bowl("A Inning 1", "Q", 3, 19, 4)]}, _t20)) == 1)
check("economy is in the bullet: 3/18 (4 ov, 4.5 econ)", "3/18 (4 ov, 4.5 econ)" in ck.standout_html(ck.standouts({"scorecard": [_bowl("A Inning 1", "Q", 3, 18, 4)]}, _t20)[0]))
_two = {"scorecard": [_bowl("A Inning 1", "Taskin Ahmed", 5, 60, 20), _bowl("A Inning 2", "Taskin Ahmed", 5, 61, 18)]}
_ten = ck.standouts(_two, _ctest)
check("ten wickets across both innings of a Test is one 'ten-for' line, replacing the two five-fors", [o["kind"] for o in _ten] == ["ten-for"] and _ten[0]["wickets"] == 10 and _ten[0]["runs_conceded"] == 121, _ten)
check("the ten-for bullet: Taskin Ahmed (B): 10/121 in the match (5/60, 5/61) v A", "10/121 in the match (5/60, 5/61) v A" in ck.standout_html(_ten[0]), ck.standout_html(_ten[0]))
check("nine wickets are not ten, and it can come before the match ends (two innings are enough)", [o["kind"] for o in ck.standouts({"scorecard": [_bowl("A Inning 1", "Q", 5, 60, 20), _bowl("A Inning 2", "Q", 4, 50, 15)]}, _ctest)] == ["five-for"])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
