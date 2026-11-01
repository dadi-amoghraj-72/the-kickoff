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
check("a live Test's status is remembered so an unchanged day is skipped", block(17, matches=M + [live])["state"]["status"].get("t1") == live["status"]
      and block(17, st={"status": {"t1": live["status"]}}, matches=[live])["html"] == "")

# ---- The scorecard shown under a result ----
sm = ck.summary(CARD, CARD)
ind, nz_inn = sm[0], sm[1]
check("India's top three batters, best first: Kishan 61 (32), Iyer 50 (23), Dhir 33 (23)", [(n, r, b) for n, r, b, _ in ind["batting"]] == [("Ishan Kishan", 61, 32), ("Shreyas Iyer", 50, 23), ("Naman Dhir", 33, 23)], ind["batting"])
check("New Zealand's bowlers against India: Milne 4-19, then Smith 2-28 and Tickner 2-38 (fewer runs first on equal wickets)", ind["bowling"] == [("Adam Milne", 4, 19), ("Nathan Smith", 2, 28), ("Blair Tickner", 2, 38)], ind["bowling"])
check("the bowling side is the other team", (ind["team"], ind["bowling_team"], nz_inn["team"], nz_inn["bowling_team"]) == ("India", "New Zealand", "New Zealand", "India"))
check("New Zealand's batters: Seifert 93 (50), Phillips 65 not out (38), Mitchell 29 (16)", nz_inn["batting"] == [("Tim Seifert", 93, 50, False), ("Glenn Phillips", 65, 38, True), ("Daryl Mitchell", 29, 16, False)], nz_inn["batting"])
check("only bowlers who took a wicket are listed", all(w >= 1 for _, w, _ in ind["bowling"] + nz_inn["bowling"]))
check("short names: initial and surname, one-word names unchanged, particles kept", [ck.short_name(n) for n in ("Ishan Kishan", "Rashid", "Marc-André ter Stegen", "Nitish Kumar Reddy")] == ["I Kishan", "Rashid", "M ter Stegen", "N Reddy"], [ck.short_name(n) for n in ("Ishan Kishan", "Rashid", "Marc-André ter Stegen", "Nitish Kumar Reddy")])
sh = ck.scorecard_html(sm)
check("the scorecard reads: team batting, then the other team bowling, for each innings (four lines)",
      sh.count('class="cd"') == 4 and "<strong>India</strong> batting: I Kishan 61 (32), S Iyer 50 (23), N Dhir 33 (23)" in sh
      and "<strong>New Zealand</strong> bowling: A Milne 4-19, N Smith 2-28, B Tickner 2-38" in sh and "G Phillips 65* (38)" in sh, sh)
check("a result with a scorecard shows it between the result and the series line", ck.result_html(nz, sm).index("New Zealand won by 7 wkts") < ck.result_html(nz, sm).index("batting:") < ck.result_html(nz, sm).index("5th T20I, India tour"))
check("a result without a scorecard shows none (no empty lines)", 'class="cd"' not in ck.result_html(nz))
check("an innings with no batters or no wicket-takers adds no empty line", ck.scorecard_html([{"team": "A", "bowling_team": "B", "batting": [], "bowling": []}]) == "")
check("names in the scorecard are escaped", "&lt;" in ck.scorecard_html([{"team": "A", "bowling_team": "B", "batting": [("<b> Name", 1, 1, False)], "bowling": []}]))
bb = block(17)
check("in the whole block, every match with a scorecard shows its batting and bowling lines", bb["html"].count('class="cd"') == 5 * 4, bb["html"].count('class="cd"'))
tt = block(80)
check("when only one scorecard fits, only that match has the scorecard lines; the other four show just their results", tt["html"].count('class="cd"') == 4, tt["html"].count('class="cd"'))

# ---- Scorecards are paid for once ----
first = block(17)
check("the first run stores each scorecard's summary and standouts", len(first["state"]["cards"]) == 5 and all({"summary", "standouts"} <= set(c) for c in first["state"]["cards"].values()))
state_no_seen = {"cards": first["state"]["cards"]}
second = block(95, state_no_seen)
check("a second run of the same matches buys nothing, even with only 5 calls left, and shows the same scorecards", len(cards) == 0 and second["stats"]["checked"] == 5
      and second["html"].count('class="cd"') == 5 * 4 and second["used"] == 95, (len(cards), second["stats"]))
check("the cached standouts are used too (the test feeds one card to five matches, so the top five are all Iyer)", second["html"].count("Shreyas Iyer") >= 5 and "<h3>Standouts</h3>" in second["html"])
mixed = block(80, {"cards": {nz["id"]: first["state"]["cards"][nz["id"]]}})
check("one cached match plus one new purchase fits the budget: 2 of 5 checked, calls = 80 + 10", mixed["stats"]["checked"] == 2 and mixed["used"] == 90 and len(cards) == 1, mixed["stats"])
many = {"cards": {f"m{i}": {"summary": [], "standouts": []} for i in range(80)}}
check("the cache keeps only the 60 most recent scorecards", len(block(17, many)["state"]["cards"]) == 60)
check("the cache survives being saved as JSON and read back", block(95, json.loads(json.dumps(state_no_seen)))["html"].count('class="cd"') == 5 * 4)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
