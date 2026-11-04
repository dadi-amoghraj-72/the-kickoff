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
check("end to end: a match with no matchType in the list is in the block (a result line, 'New Zealand v India') and is remembered as reported", run_nt["stats"]["picked"] == 1 and "New Zealand v India" in re.sub(r"<[^>]+>", " ", run_nt["html"]) and "n1" in run_nt["state"]["seen"], run_nt["html"][:200])
live = {"id": "t1", "name": "England vs Pakistan, 1st Test, Pakistan tour of England 2027", "matchType": "test", "status": "Day 2: Stumps - England lead by 40 runs",
        "dateTimeGMT": "2026-11-01T10:00:00", "teams": ["England", "Pakistan"], "score": [], "matchStarted": True, "matchEnded": False}
check("a live Test is reported when its status has changed", any(m["id"] == "t1" for m in ck.pick(M + [live], NOW, START, last_status={"t1": "Day 1: Stumps"})))
check("and again the next day even when nothing changed: a Test in progress is shown every day", any(m["id"] == "t1" for m in ck.pick(M + [live], NOW, START, last_status={"t1": live["status"]})))
check("live matches that are not Test-nation Tests (Sheffield Shield, an A-team Test) are never reported", not any("Shield" in m["name"] or "Unofficial" in m["name"] for m in picked))

# ---- How a result reads ----
nz = by("5th T20I")
h = ck.result_html(nz)
check("a result shows the teams (India in bold), both innings, the result and the series", "New Zealand v <strong>India</strong>" in h and "India 191/8 (20) · New Zealand 195/3 (18)" in h
      and "New Zealand won by 7 wkts" in h and "5th T20I, India tour of New Zealand 2026" in h, h)
check("an all-out innings has no '/10' and overs keep their decimal", ck.innings_line({"r": 109, "w": 10, "o": 17.4, "inning": "Hobart Hurricanes Women Inning 1"}) == "Hobart Hurricanes Women 109 (17.4)")
check("a live match carries an In progress tag", '<span class="tag">In progress</span>' in ck.result_html(live))
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
check("the real Namibia v Ireland result now reads cleanly", "Ireland 129 (33.1) · Namibia 131/5 (21.2)" in ck.result_html(nam), ck.result_html(nam))
wb = by("Sydney Thunder Women vs Brisbane Heat Women")
check("and so does the real WBBL result", "Brisbane Heat Women 178/5 (20) · Sydney Thunder Women 180/4 (16.4)" in ck.result_html(wb), ck.result_html(wb))
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
so = ck.standouts(CARD, CARD)
check("the real NZ v India scorecard has exactly two standouts: Iyer's fast fifty and Milne's T20 four-for", sorted((o["name"], o["kind"]) for o in so) ==
      [("Adam Milne", "four-for"), ("Shreyas Iyer", "fast fifty")], [(o["name"], o["kind"]) for o in so])
iyer = next(o for o in so if o["name"] == "Shreyas Iyer")
milne = next(o for o in so if o["name"] == "Adam Milne")
check("Iyer: 50 off 23 balls for India, against New Zealand", (iyer["runs"], iyer["balls"], iyer["team"], iyer["against"]) == (50, 23, "India", "New Zealand"), iyer)
check("Milne: 4 for 19 for New Zealand (the bowling side is the other team), against India", (milne["wickets"], milne["runs_conceded"], milne["team"], milne["against"]) == (4, 19, "New Zealand", "India"), milne)
check("Seifert's 93 off 50, Kishan's 61 off 32 and Phillips' 65 off 38 are not standouts", not any(o["name"] in ("Tim Seifert", "Ishan Kishan", "Glenn Phillips") for o in so))

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
check("100 is a century, 99 is not", kinds([bat("P", 100, 60)]) == [("P", "century")] and kinds([bat("P", 99, 60)]) == [])
check("a century that is also fast is a century, not a fast fifty", kinds([bat("P", 104, 22)]) == [("P", "century")])
check("50 off 25 balls is a fast fifty, 50 off 26 is not, 49 off 20 is not", kinds([bat("P", 50, 25)]) == [("P", "fast fifty")] and kinds([bat("P", 50, 26)]) == [] and kinds([bat("P", 49, 20)]) == [])
check("a missing ball count (0) never counts as a fast fifty", kinds([bat("P", 60, 0)]) == [])
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
check("a fast fifty line: name, team, the figures, the opponent, the series and the result", "<strong>Shreyas Iyer</strong> (India) · fifty off 23 balls: 50 off 23 balls, 3 fours and 4 sixes against New Zealand" in hi
      and "5th T20I" in hi and "New Zealand won by 7 wkts" in hi, hi)
check("a bowling line: wickets for runs off overs", "<strong>Adam Milne</strong> (New Zealand) · four-wicket haul: 4 for 19 off 4 overs against India" in hm, hm)
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
check("the page says how many matches had their standouts checked", "checked in 1 of 5 matches" in tight["html"])
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
check("a tier 1 result carries its scorecard, under the series line", ck.result_html(nz, entry).index("5th T20I, India tour") < ck.result_html(nz, entry).index('<table class="sc">'))
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

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
