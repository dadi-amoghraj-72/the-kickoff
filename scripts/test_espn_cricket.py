"""Offline tests for the ESPN cricket source, on saved real pages (NZ v India 5th T20I, and the day's scores page).
Run: python3 scripts/test_espn_cricket.py"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket as ck  # noqa: E402
from kickoff.sources import cricket as src  # noqa: E402
from kickoff.sources import espn_cricket as ec  # noqa: E402

FX = ROOT / "tests" / "fixtures"
SCORES = (FX / "espn_cricket_scores.html").read_text()
PAGE = (FX / "espn_cricket_scorecard_nz_ind.html").read_text()
M = json.loads((FX / "cricket_current.json").read_text())
real_card_consistent = ck.card_consistent
ck.card_consistent = lambda card, match: True   # the older tests below feed saved cards to matches they do not belong to; the real check is switched back on for the cache tests
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# ---- The scores page ----
idx = ec.parse_index(SCORES)
check("the scores page lists 27 games, 19 of them with a scorecard page", len(idx) == 27 and sum(1 for g in idx.values() if g["scorecard"]) == 19,
      (len(idx), sum(1 for g in idx.values() if g["scorecard"])))
nzind = next(m for m in M if "5th T20I" in m["name"])
url = ec.find_scorecard_url(idx, nzind["teams"], nzind["name"])
check("NZ v India finds its scorecard page, whichever order the teams come in", url == "https://www.espn.com/cricket/series/24469/scorecard/1539436/new-zealand-vs-india-5th-t20i-24469"
      and ec.find_scorecard_url(idx, nzind["teams"][::-1]) == url, url)
check("a match with only a game page (New Zealand A v India A), unknown teams, or one team gives None",
      ec.find_scorecard_url(idx, ["New Zealand A", "India A"]) is None and ec.find_scorecard_url(idx, ["Nowhere", "Atlantis"]) is None and ec.find_scorecard_url(idx, ["India"]) is None)
twice = {"1": {"slug": "india-vs-australia-1st-t20i-9", "scorecard": "u1"}, "2": {"slug": "india-vs-australia-2nd-t20i-9", "scorecard": "u2"}}
check("two games between the same sides are told apart by their ordinal, and skipped when that cannot decide",
      ec.find_scorecard_url(twice, ["India", "Australia"], "India vs Australia, 2nd T20I") == "u2" and ec.find_scorecard_url(twice, ["India", "Australia"], "India vs Australia") is None)

# ---- The scorecard page, against the Cricinfo screenshots D supplied ----
inn = ec.parse_scorecard(PAGE)
check("two innings, India then New Zealand", [i["inning"] for i in inn] == ["India Innings", "New Zealand Innings"], [i["inning"] for i in inn])
ind, nz = inn
check("India: 191/8 in 20 overs, run rate 9.55; extras 7 (b 1, lb 1, nb 1, w 4)", ind["espn"]["total"] == {"r": 191, "w": 8, "o": 20.0, "rr": 9.55}
      and ind["espn"]["extras"] == {"total": 7, "b": 1, "lb": 1, "nb": 1, "w": 4}, ind["espn"])
check("New Zealand: 195/3 in 18 overs, run rate 10.83; extras 5 (lb 2, w 3)", nz["espn"]["total"] == {"r": 195, "w": 3, "o": 18.0, "rr": 10.83}
      and nz["espn"]["extras"] == {"total": 5, "lb": 2, "w": 3}, nz["espn"])
check("India did not bat: Varun. New Zealand did not bat: six names, captain marked, no stray commas", ind["espn"]["dnb"] == ["Varun"]
      and nz["espn"]["dnb"] == ["Bracewell", "Santner (c)", "Smith", "Milne", "Duffy", "Tickner"], (ind["espn"]["dnb"], nz["espn"]["dnb"]))
check("fall of wickets: India 8 of them, as surnames; New Zealand 3", ind["espn"]["fow"].startswith("1-2 (Sharma, 1.1), 2-19 (Samson, 3.1)") and ind["espn"]["fow"].endswith("8-190 (Kumar, 19.5)")
      and nz["espn"]["fow"] == "1-9 (Allen, 1.3), 2-82 (Mitchell, 8.3), 3-168 (Seifert, 15.3)", (ind["espn"]["fow"], nz["espn"]["fow"]))
s = ind["batting"][0]
check("Samson: full name, wicketkeeper mark, c Bracewell b Milne, 4 off 10, 16 minutes, SR 40", s["batsman"]["name"] == "Sanju Samson" and s["mark"] == "†" and s["dismissal-text"] == "c Bracewell b Milne"
      and (s["r"], s["b"], s["m"], s["4s"], s["6s"], s["sr"]) == (4, 10, 16, 0, 0, 40.0), s)
check("Iyer is marked captain", next(b for b in ind["batting"] if b["batsman"]["name"] == "Shreyas Iyer")["mark"] == "(c)")
seifert = nz["batting"][0]
check("Seifert: 93 off 50, 11 fours, 5 sixes, SR 186", (seifert["r"], seifert["b"], seifert["4s"], seifert["6s"], seifert["sr"]) == (93, 50, 11, 5, 186.0), seifert)
milne = next(b for b in ind["bowling"] if b["bowler"]["name"] == "Adam Milne")
check("Milne: 4-0-19-4, economy 4.75, 16 dots, 1 wide", (milne["o"], milne["m"], milne["r"], milne["w"], milne["eco"], milne["0s"], milne["wd"], milne["nb"]) == (4.0, 0, 19, 4, 4.75, 16, 1, 0), milne)
check("India batted 10 players and NZ's bowlers are 6; NZ batted 5 players and India's bowlers are 6", (len(ind["batting"]), len(ind["bowling"]), len(nz["batting"]), len(nz["bowling"])) == (10, 6, 5, 6),
      (len(ind["batting"]), len(ind["bowling"]), len(nz["batting"]), len(nz["bowling"])))
# Independent cross-checks that catch a misaligned column anywhere
for i in inn:
    t, ex = i["espn"]["total"], i["espn"]["extras"]
    check(f"{i['inning']}: batters' runs + extras = total", sum(b["r"] for b in i["batting"]) + ex["total"] == t["r"], (sum(b["r"] for b in i["batting"]), ex, t))
    check(f"{i['inning']}: bowlers' runs = total - byes - leg-byes", sum(b["r"] for b in i["bowling"]) == t["r"] - ex.get("b", 0) - ex.get("lb", 0))
    check(f"{i['inning']}: bowlers' wides and no-balls match the extras", sum(b["wd"] for b in i["bowling"]) == ex.get("w", 0) and sum(b["nb"] for b in i["bowling"]) == ex.get("nb", 0))
    check(f"{i['inning']}: the fall-of-wickets list is as long as the wickets", len(re.findall(r"\d+-\d+ \(", i["espn"]["fow"])) == t["w"])
    check(f"{i['inning']}: run rate agrees with runs over overs", abs(t["r"] / ck.overs_decimal(t["o"]) - t["rr"]) < 0.01)
    check(f"{i['inning']}: each bowler's economy agrees with runs over overs", all(abs(b["r"] / ck.overs_decimal(b["o"]) - b["eco"]) < 0.01 for b in i["bowling"]))
check("a page that is not a scorecard parses to nothing, not an error", ec.parse_scorecard("<html>maintenance</html>") == [] and ec.parse_scorecard("") == [])

# ---- Into the digest's own shape ----
slim = ck.slim_card({"scorecard": inn}, nzind)
check("slim card: totals and extras come from the page, not worked out", slim[0]["runs"] == 191 and slim[0]["wickets"] == 8 and slim[0]["overs"] == 20.0
      and slim[0]["extras"] == {"total": 7, "b": 1, "lb": 1, "nb": 1, "w": 4}, slim[0])
check("slim card: teams are matched to the real names", [i["team"] for i in slim] == ["India", "New Zealand"] and slim[0]["bowling_team"] == "New Zealand", [i["team"] for i in slim])
check("slim card: a full-name dismissal is shortened ('b Nitish Kumar Reddy' -> 'b Reddy')", next(b for b in slim[1]["batting"] if b["name"] == "Tim Seifert")["out"] == "b Reddy", slim[1]["batting"][0])
html = ck.full_scorecard_html(slim)
check("the page shows the captain and keeper marks, the real extras split, did-not-bat and fall of wickets",
      "Shreyas Iyer (c)" in html and "Sanju Samson †" in html and "w 4, nb 1, b 1, lb 1" in html and "Did not bat:</strong> Varun" in html and "Fall of wickets:</strong> 1-2 (Sharma, 1.1)" in html, html[:400])
check("the old CricketData-style card still renders, without did-not-bat or fall of wickets", "Did not bat" not in ck.full_scorecard_html(ck.slim_card(
      json.loads((FX / "cricket_scorecard_nz_ind.json").read_text()), nzind)))
standing = ck.standouts({"scorecard": inn}, nzind)
check("standouts work from the page: Seifert's 93 is no century, Milne's 4-19 is a T20 four-for", [o["kind"] for o in standing if o["name"] in ("Tim Seifert", "Adam Milne")] == ["four-for"]
      or [o["kind"] for o in standing if o["name"] == "Adam Milne"] == ["four-for"], [(o["name"], o["kind"]) for o in standing])

# ---- Fetching ----
pages = []


def fake_fetch(url):
    pages.append(url)
    if url == ec.SCORES_URL:
        return SCORES
    if "1539436" in url:
        return PAGE
    raise OSError("not found")


get = ec.card_getter(fake_fetch, pause=0)
card = get(nzind)
check("the getter returns the card for a match, reading the scores page once", card and len(card["scorecard"]) == 2 and pages.count(ec.SCORES_URL) == 1, pages)
get(nzind)
check("the scores page is not read again for a second match", pages.count(ec.SCORES_URL) == 1)
check("a match with no page gives None without any scorecard fetch", get({"name": "X vs Y", "teams": ["X", "Y"]}) is None and len(pages) == 3, pages)
check("a failing fetch gives None, never an error", ec.card_getter(lambda u: (_ for _ in ()).throw(OSError("down")), pause=0)(nzind) is None)
check("a changed page (no scorecard found) gives None", ec.card_getter(lambda u: SCORES if u == ec.SCORES_URL else "<html></html>", pause=0)(nzind) is None)

# ---- In the run: free, and the budget is untouched ----
NOW = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
START = NOW - timedelta(hours=26)
bought = []


def paid(mid):
    bought.append(mid)
    return {"scorecard": []}, 17 + 10 * len(bought)


only_nz = lambda m: {"scorecard": inn} if m["id"] == nzind["id"] else None  # noqa: E731
out = ck.run(NOW, START, {}, lambda: (M, 17), paid, src.scorecards_affordable, espn_card=only_nz)
check("only NZ v India has an ESPN card: it is not bought, the other four are, and calls used = 17 + 4 x 10",
      nzind["id"] not in bought and len(bought) == out["stats"]["picked"] - 1 == 4 and out["used"] == 57, (bought, out["stats"], out["used"]))
out2 = ck.run(NOW, START, {}, lambda: (M, 17), paid, src.scorecards_affordable, espn_card=lambda m: {"scorecard": inn})
check("with ESPN for every match, nothing is bought and no budget is used", out2["used"] == 17 and out2["stats"]["skipped"] == 0 and out2["stats"]["checked"] == out2["stats"]["picked"], out2["stats"])
check("the finished matches' cards are saved for next time", all("innings" in v for v in out2["state"]["cards"].values()) and len(out2["state"]["cards"]) == out2["stats"]["picked"])
live = {"id": "live1", "name": "England vs Pakistan, 1st Test, Pakistan tour of England 2027", "matchType": "test", "status": "Day 2: Stumps - England lead by 40 runs",
        "dateTimeGMT": "2026-11-01T10:00:00", "teams": ["England", "Pakistan"], "score": [], "matchStarted": True, "matchEnded": False}
out3 = ck.run(NOW, START, {}, lambda: ([live], 17), paid, src.scorecards_affordable, espn_card=lambda m: {"scorecard": inn})
check("a match still in progress is shown but its scorecard is not saved", out3["stats"]["checked"] == 1 and "live1" not in out3["state"]["cards"], out3["state"]["cards"].keys())

# ---- Old-format cache entries are a fallback, not the answer ----
old = {"innings": [{k: v for k, v in i.items() if k not in ("dnb", "fow")} for i in slim], "standouts": []}  # what was saved before ESPN
fresh_card = lambda m: {"scorecard": inn}  # noqa: E731
r1 = ck.run(NOW, START, {"cards": {nzind["id"]: old}}, lambda: ([nzind], 17), paid, src.scorecards_affordable, espn_card=fresh_card)
check("a card saved in the old format is replaced by ESPN's richer one", "dnb" in r1["state"]["cards"][nzind["id"]]["innings"][0] and r1["used"] == 17, r1["state"]["cards"])
r2 = ck.run(NOW, START, {"cards": {nzind["id"]: old}}, lambda: ([nzind], 17), paid, src.scorecards_affordable, espn_card=lambda m: None)
check("when ESPN has nothing, the old card is used and nothing is bought", r2["state"]["cards"][nzind["id"]] is old and r2["used"] == 17 and r2["stats"]["checked"] == 1, r2["stats"])
r3 = ck.run(NOW, START, {"cards": {nzind["id"]: r1["state"]["cards"][nzind["id"]]}}, lambda: ([nzind], 17), paid, src.scorecards_affordable, espn_card=lambda m: 1 / 0)
check("a card already saved in the new format is not fetched again", r3["stats"]["checked"] == 1)

# ---- League points tables ----
TABLE = (FX / "espn_cricket_table_wbbl.html").read_text()
rows = ec.parse_table(TABLE)
check("the WBBL table has all 8 teams in order 1..8, led by Sydney Sixers on 4 points and NRR 2.25",
      rows and [x["pos"] for x in rows] == list(range(1, 9)) and rows[0]["name"] == "Sydney Sixers Women" and (rows[0]["p"], rows[0]["w"], rows[0]["pts"], rows[0]["nrr"]) == (2, 2, 4, 2.25), rows and rows[0])
check("the row after the finals cut-off line (Melbourne Stars, 5th) is not lost", rows[4]["name"] == "Melbourne Stars Women" and rows[4]["team"] == "MS-W" and rows[4]["nrr"] == -0.075, rows[4])
check("every team's played = won + lost + tied + no result, and the points are 2 a win", all(x["p"] == x["w"] + x["l"] + x["t"] + x["nr"] and x["pts"] == 2 * x["w"] for x in rows), rows)
check("abbreviations are the official ones, with the '-W' kept (D, 2026-11-04: IND-W, AUS-W)", [x["team"] for x in rows] == ["SS-W", "ST-W", "PS-W", "AS-W", "MS-W", "BH-W", "MR-W", "HH-W"], [x["team"] for x in rows])
th = ck.table_html("WBBL", rows)
check("the table block: caption, numbers right-aligned, signed three-place NRR, no Ties column when nobody has tied",
      "<caption>WBBL table</caption>" in th and "+2.250" in th and "-2.625" in th and "<th class=\"n\">T</th>" not in th and th.count("<tr>") == 8 + 1, th[:300])
tied = [dict(x) for x in rows]
tied[0].update(t=1, p=3, pts=5)
check("a Ties column appears when a team has tied", "<th class=\"n\">T</th>" in ck.table_html("WBBL", tied))
check("no game colours in a league table: all white", "gc" not in ck.table_html("WBBL", rows) and "<span" not in ck.table_html("WBBL", rows))
broken = [dict(x) for x in rows]
broken[2]["w"] = 5
check("a table whose rows do not add up, is out of order, or is empty is left out, not shown wrong",
      ck.table_html("WBBL", broken) == "" and ck.table_html("WBBL", rows[::-1]) == "" and ck.table_html("WBBL", []) == "" and ck.table_html("WBBL", None) == "")
check("a page with no table, or several (a group stage), gives None", ec.parse_table("<html></html>") is None and ec.parse_table(TABLE + TABLE) is None)

wbbl = next(m for m in M if "Women's Big Bash" in m["name"] or "Big Bash" in m["name"])
src_ = ec.Source(lambda u: SCORES if u == ec.SCORES_URL else (TABLE if "/cricket/table/series/21284" in u else (_ for _ in ()).throw(OSError(u))), pause=0)
tbl = src_.table(wbbl)
check("the Source finds a league's table from the scores page's series id", tbl and len(tbl) == 8, wbbl["name"])
check("the table is read once per series", (src_.table(wbbl), src_.fetched)[1] == 2, src_.fetched)
out_t = ck.run(NOW, START, {}, lambda: (M, 17), paid, src.scorecards_affordable, espn_card=fresh_card, espn_table=src_.table)
check("in the block the WBBL table follows the WBBL results and the International section has none",
      out_t["html"].index("<h3>WBBL</h3>") < out_t["html"].index("WBBL table") < out_t["html"].index("<h3>Standouts</h3>") and out_t["html"].count("<caption>") == 1, out_t["html"].count("<caption>"))
check("without a table source nothing changes", "<caption>" not in ck.run(NOW, START, {}, lambda: (M, 17), paid, src.scorecards_affordable, espn_card=fresh_card)["html"])
check("a failing table fetch leaves the results and no table", "<caption>" not in ck.run(NOW, START, {}, lambda: (M, 17), paid, src.scorecards_affordable, espn_card=fresh_card,
                                                                                          espn_table=ec.Source(lambda u: (_ for _ in ()).throw(OSError("down")), pause=0).table)["html"])

# ---- Player of the match, standouts under the scorecard, Tests every day, World Cups ----
META = (FX / "espn_cricket_scorecard_meta.html").read_text()
meta = ec.parse_meta(META)
check("the page gives the result line and the Player of the Match with his team", meta == {"status": "New Zealand won by 7 wkts (12b rem)", "potm": [{"name": "Adam Milne", "team": "New Zealand"}]}, meta)
check("no Player of the Match section (not awarded yet) gives an empty list, not an error", ec.parse_meta("<html></html>") == {"status": "", "potm": []})
MULTI = (FX / "espn_cricket_scorecard_multiday.html").read_text()
mm = ec.parse_meta(MULTI)
check("a first-class match's page: result line with '&' unescaped, Jake Doran of Tasmania is Player of the Match", mm["status"] == "Tasmania won by an inns & 81 runs" and mm["potm"] == [{"name": "Jake Doran", "team": "Tasmania"}], mm)
multi = ec.parse_scorecard(MULTI)
check("three innings parse, 427 all out, 202 all out, 144 all out, each passing the cross-checks", [i["espn"]["total"]["r"] for i in multi] == [427, 202, 144]
      and all(sum(b["r"] for b in i["batting"]) + i["espn"]["extras"]["total"] == i["espn"]["total"]["r"] for i in multi))
tas = {"id": "x", "name": "Tasmania vs New South Wales, 8th Match, Sheffield Shield 2026", "matchType": "test", "teams": ["Tasmania", "New South Wales"], "score": [],
       "status": "Day 3: Stumps - Tasmania lead", "matchStarted": True, "matchEnded": False}
sl = ck.slim_card({"scorecard": multi}, tas)
check("in a Test each innings is labelled: Tasmania 1st innings, New South Wales 1st innings, New South Wales 2nd innings",
      [(i["team"], i["label"]) for i in sl] == [("Tasmania", "1st innings"), ("New South Wales", "1st innings"), ("New South Wales", "2nd innings")], [(i["team"], i["label"]) for i in sl])
check("the label shows on the page; a T20 has none", "New South Wales</strong> 2nd innings 144" in ck.full_scorecard_html(sl) and all(not i["label"] for i in ck.slim_card({"scorecard": inn}, nzind)))
live_test = {"id": "t9", "name": "England vs Pakistan, 2nd Test, Pakistan tour of England 2027", "matchType": "test", "status": "Day 3: Stumps - England lead by 40 runs",
             "dateTimeGMT": "2026-11-01T10:00:00", "teams": ["England", "Pakistan"], "score": [], "matchStarted": True, "matchEnded": False}
check("every men's Test gets a full scorecard, even between two non-big-six sides (Sri Lanka v Bangladesh)", ck.scorecard_tier(live_test) == 1
      and ck.scorecard_tier({"name": "Sri Lanka vs Bangladesh, 1st Test, 2027", "matchType": "test", "teams": ["Sri Lanka", "Bangladesh"]}) == 1)
check("a women's Test is not a full-scorecard match", ck.scorecard_tier({"name": "India Women vs England Women, Only Test, 2027", "matchType": "test", "teams": ["India Women", "England Women"]}) == 3)
wc = {"name": "Nepal vs Namibia, 12th Match, Group C, ICC Men's T20 World Cup 2026", "matchType": "t20", "teams": ["Nepal", "Namibia"]}
check("a men's World Cup match is recognised and gets a full scorecard whoever plays", ck.classify(wc)["kind"] == "international" and ck.scorecard_tier(wc) == 1, ck.classify(wc))
check("a women's World Cup match is recognised but gets the result line only", ck.classify({**wc, "name": wc["name"].replace("Men's", "Women's"), "teams": ["Nepal Women", "Namibia Women"]})["kind"] == "international"
      and ck.scorecard_tier({**wc, "name": wc["name"].replace("Men's", "Women's"), "teams": ["Nepal Women", "Namibia Women"]}) == 3)
check("World Cup qualifiers, pathway events and ICC 'League Two' games are not the World Cup", all(ck.classify({**wc, "name": n})["kind"] is None for n in (
    "Nepal vs Namibia, 3rd Match, ICC Men's T20 World Cup Qualifier 2026", "Nepal vs Namibia, 4th Match, ICC Cricket World Cup League Two 2023-27",
    "Nepal vs Namibia, 5th Match, ICC T20 World Cup Africa Sub Regional Qualifier 2026")))

eng_pak = [dict(i, inning=i["inning"].replace("Tasmania", "England").replace("New South Wales", "Pakistan")) for i in multi]
everyday = ck.run(NOW, START, {"status": {"t9": live_test["status"]}}, lambda: ([live_test], 17), paid, src.scorecards_affordable,
                  espn_card=lambda m: {"scorecard": eng_pak, "status": "Day 3: Stumps", "potm": []})
check("a Test in progress: the 'Test · in progress' pill above the teams, the match number, and where it stands said once ('Stumps, Day 3 · England lead by 40 runs', D 2026-11-08)", everyday["html"].index("Test · in progress") < everyday["html"].index("England v Pakistan") and "England v Pakistan · 2nd Test</span>" in everyday["html"]
      and '<strong class="state">Stumps, Day 3</strong> \u00b7 England lead by 40 runs' in everyday["html"] and everyday["html"].count("Day 3") == 1, everyday["html"][:400])
check("the Test's scorecard is shown but not saved (it changes every day)", "Pakistan</strong> 2nd innings" in everyday["html"] and "t9" not in everyday["state"]["cards"])
check("with no day in the status, ESPN's line gives it; with neither it says 'in progress'",
      ck.day_of({"status": ""}, {"status": "Day 4: Lunch"}) == 4 and ck.day_of({"status": "Stumps"}, {}) is None and "Test · in progress" in ck.result_html({**live_test, "status": "Stumps"}))

# Standouts go under the scorecard they belong to; matches without a scorecard feed the closing list
hundred = {"scorecard": [{"inning": "India Innings", "batting": [{"batsman": {"name": "Star Batter"}, "dismissal-text": "not out", "r": 120, "b": 60, "4s": 10, "6s": 5, "sr": 200.0}], "bowling": [], "espn": {}}]}
with_potm = {**{"scorecard": inn}, "potm": [{"name": "Adam Milne", "team": "New Zealand"}], "status": "New Zealand won by 7 wkts"}
noor = {"scorecard": [{"inning": "Zimbabwe Innings", "batting": [], "bowling": [{"bowler": {"name": "Noor Ahmad"}, "o": 3.3, "m": 0, "r": 13, "w": 5, "eco": 3.71, "wd": 0, "nb": 0}], "espn": {}}],
        "potm": [{"name": "Noor Ahmad", "team": "Afghanistan"}], "status": ""}
nam = {"scorecard": [{"inning": "Ireland Innings", "batting": [], "bowling": [], "espn": {}}], "potm": [{"name": "Jan Frylinck", "team": "Namibia"}], "status": ""}
per_match = lambda m: with_potm if "India" in m["teams"] and "New Zealand" in m["teams"] else noor if "Afghanistan" in m["teams"] else nam if "Namibia" in m["teams"] else None  # noqa: E731
blk = ck.run(NOW, START, {}, lambda: (M, 17), paid, src.scorecards_affordable, espn_card=per_match)
h = blk["html"]
i_nz = h.index("New Zealand v <strong>India</strong>")
i_next = h.index("Namibia v Ireland")
check("NZ v India: result, then Player of the match, then the scorecard, then its own standouts, all before the next match",
      i_nz < h.index("Player of the match: <strong>Adam Milne</strong> (New Zealand)", i_nz) < h.index("<table class=\"sc\">", i_nz) < h.index("<strong>Standouts</strong>", i_nz) < i_next, h[i_nz:i_nz + 200])
check("the standouts under NZ v India are about that match and do not repeat the series and result", 'Adam Milne</strong> (New Zealand): <span class="n">4/19</span> (4 ov, 4.8 econ) v India</li>' in h[i_nz:i_next])
check("matches with only a result line still show Player of the match when we have it (Namibia v Ireland)", h.index("Player of the match", i_next) < h.index("Afghanistan v Zimbabwe"), h[i_next:i_next + 400])
check("their standouts (Noor Ahmad's five-for) are in the closing list, as clean bullets", h.index("<h3>Standouts</h3>") > h.index("Afghanistan v Zimbabwe") and "Noor Ahmad" in h[h.index("<h3>Standouts</h3>"):], h[-600:])
check("the closing list holds only the no-scorecard matches' standouts, not NZ v India's", "Adam Milne" not in h[h.index("<h3>Standouts</h3>"):] and "Shreyas Iyer" not in h[h.index("<h3>Standouts</h3>"):])
no_potm = ck.run(NOW, START, {}, lambda: ([nzind], 17), paid, src.scorecards_affordable, espn_card=lambda m: {"scorecard": inn})["html"]
check("when no Player of the match is known yet (a finished match with a scorecard), a quiet line says so (D, 2026-11-06)", "Player of the match: not available at time of print" in no_potm and "<strong>" not in no_potm.split("Player of the match")[1][:40])

# ---- Series pages and series tables (the real NZ v India series page: five T20Is played, five ODIs still to come) ----
import copy as _cp  # noqa: E402
import re as _re3  # noqa: E402
SER = (FX / "espn_cricket_series_nz_ind.html").read_text()
srows = ec.parse_series(SER)
txt3 = lambda h: _re3.sub(r"\s+", " ", _re3.sub(r"<[^>]+>", " ", h)).strip()  # noqa: E731
raw_results = _re3.findall(r'"note":"((?:India|New Zealand) won by [^"]+)"', SER)
check("independent: the page's own embedded data lists five finished results (3 India, 2 New Zealand), and the parser finds exactly those five, in order, plus five ODIs and the first Test (a date range, 'Nov 19-23 2026') with no result",
      len(srows) == 11 and [g["result"] for g in srows if g["result"]] == list(dict.fromkeys(raw_results))[:5] and sum(g["result"] is not None for g in srows) == 5
      and [g["format"] for g in srows] == ["T20I"] * 5 + ["ODI"] * 5 + ["Test"], [(g["n"], g["format"], g["result"]) for g in srows])
check("the parser reads each match's teams, abbreviations and scores (1st T20I: New Zealand 225/4, India 230/6) and its venue and date; the 5th T20I lists India first",
      (srows[0]["teams"][0]["name"], srows[0]["teams"][0]["abbr"], srows[0]["teams"][0]["score"], srows[0]["teams"][1]["score"], srows[0]["venue"], srows[0]["date"]) == ("New Zealand", "NZ", "225/4", "230/6", "Christchurch", "Oct 22 2026") and srows[4]["teams"][0]["name"] == "India")
check("a match still to come has no scores and carries its start line", srows[5]["teams"][0]["score"] == "" and srows[5]["starts"] == "Starts at 15:00 local time" and srows[5]["result"] is None and srows[5]["venue"] == "Auckland")
check("a page with no series list gives an empty list, never an error", ec.parse_series("<html>nothing</html>") == [] and ec.parse_series("") == [])
t20 = ck.series_html(srows, "t20")
tt3 = txt3(t20)
wins = {"India": sum(1 for g in srows if g["result"] and g["result"].startswith("India won")), "New Zealand": sum(1 for g in srows if g["result"] and g["result"].startswith("New Zealand won"))}
check("independent: counting the raw result lines, India won 3 and New Zealand 2 of the T20Is; the table header shows 'New Zealand v India · T20I series', New Zealand 2 on the left, India 3 on the right, the word 'series' between",
      wins == {"India": 3, "New Zealand": 2} and "New Zealand v India · T20I series" in tt3 and "2 series 3" in tt3, tt3[:200])
check("five rows made from the page (the 5th T20I's scores are put in the right columns although India is listed first): 1st T20I 225/4 v 230/6, 5th T20I New Zealand 195/3 on the left and India 191/8 on the right", t20.count('<tr class="one') == 5 and "225/4 1st T20I · 22 Oct 230/6" in tt3 and "195/3 5th T20I · 1 Nov 191/8" in tt3, tt3)
check("each played match shows its result line under it and the winning side in bold: 3 matches won by India (right), 2 by New Zealand (left)", t20.count('class="hm w"') == 3 and t20.count('class="aw w"') == 2 and tt3.count("won by") == 5)
odi = ck.series_html(srows, "odi")
ot = txt3(odi)
check("the ODI series, not started: 0 series 0, five rows made in advance each with its date and 'Starts at 15:00 local time', no scores", "0 series 0" in ot and odi.count('class="one end pre"') == 5 and ot.count("Starts at 15:00 local time") == 5 and "1st ODI · 4 Nov" in ot and "5th ODI · 15 Nov" in ot)
check("a format with no matches in the page gives nothing", ck.series_html([g for g in srows if g["format"] != "Test"], "test") == "" and ck.series_html([], "odi") == "" and ck.series_html(None, "odi") == "")
tied_rows = _cp.deepcopy(srows[:5])
tied_rows[0]["result"] = "Match tied"
tsv = ck.series_html(tied_rows, "t20")
check("a tied match counts for neither side and has no bold side: 4 bold sides in the five rows, and the series stands 2-2 (the tied match was one of India's three wins)", tsv.count('class="aw w"') + tsv.count('class="hm w"') == 4 and "2 series 2" in txt3(tsv), txt3(tsv)[:120])
odi_match = _cp.deepcopy(nzind)
odi_match["matchType"] = "odi"
odi_match["name"] = odi_match["name"].replace("5th T20I", "1st ODI")
fed = []
r_odi = ck.run(NOW, START, {}, lambda: ([odi_match], 17), paid, src.scorecards_affordable, espn_card=lambda m: None, espn_series=lambda m: (fed.append(m["id"]) or srows))
check("run(): a Test or ODI result gets its series table under it (once), built from the series feed", r_odi["html"].count('class="nflsb nbaone ser sm"') == 1 and "5th ODI · 15 Nov" in txt3(r_odi["html"]) and fed == [odi_match["id"]])
r_t20 = ck.run(NOW, START, {}, lambda: ([nzind], 17), paid, src.scorecards_affordable, espn_card=lambda m: None, espn_series=lambda m: srows)
check("a T20I series gets no series table (D asked for Tests and ODIs), and neither does a run without a series feed", 'class="nflsb' not in r_t20["html"] and 'class="nflsb' not in ck.run(NOW, START, {}, lambda: ([odi_match], 17), paid, src.scorecards_affordable, espn_card=lambda m: None)["html"])
two = [_cp.deepcopy(odi_match), _cp.deepcopy(odi_match)]
two[1]["id"] = "second-odi"
two[1]["name"] = odi_match["name"].replace("1st ODI", "2nd ODI")
calls = []
r_two = ck.run(NOW, START, {}, lambda: (two, 17), paid, src.scorecards_affordable, espn_card=lambda m: None, espn_series=lambda m: (calls.append(1) or srows))
check("two matches of the same series on one day get one series table, and the feed is asked once", r_two["html"].count('class="nflsb nbaone ser sm"') == 1 and len(calls) == 1, (r_two["html"].count("ser sm"), len(calls)))
r_fail = ck.run(NOW, START, {}, lambda: ([odi_match], 17), paid, src.scorecards_affordable, espn_card=lambda m: None, espn_series=lambda m: None)
check("when the series feed has nothing the result still shows without a table", "nbaone" not in r_fail["html"] and "India" in r_fail["html"])
page_calls = []
fsrc = ec.Source(lambda url: (page_calls.append(url) or (SER if "scores/series" in url else SCORES)), pause=0)
sr = fsrc.series(nzind)
check("the live source finds the series id from the day's scores page, fetches that series' page once, and returns its 11 matches (five T20Is, five ODIs, a Test); a second call uses the cache", sr is not None and len(sr) == 11 and any(u.endswith("/cricket/scores/series/24469") for u in page_calls) and (fsrc.series(nzind) is not None) and sum("scores/series" in u for u in page_calls) == 1, page_calls)
check("a source that fails returns None, not an error", ec.Source(lambda url: 1 / 0, pause=0).series(nzind) is None)

# ---- ESPN's cricket JSON feed: matches the free CricketData list does not have (New Zealand v India, 1st ODI, 4 November 2026) ----
FEED = json.loads((FX / "espn_cricket_feed.json").read_text())


feed_urls = []


def feed_get(url):
    feed_urls.append(url)
    if "scoreboard/header" in url:
        return FEED["header"]
    return FEED["series"][url.split("/cricket/")[1].split("/")[0]]


feed = ec.Feed(feed_get, pause=0)
got = ck.espn_matches(feed)
odi = next((m for m in got if m["event"] == "1539437"), None)
raw_ev = next(e for e in FEED["series"]["24469"]["events"] if e["id"] == "1539437")
check("ESPN's feed gives the finished New Zealand v India 1st ODI: named like CricketData's own, a finished ODI that started at 02:00 UTC on 4 November",
      odi and odi["name"] == "New Zealand vs India, 1st ODI, India tour of New Zealand 2026/27" and odi["matchType"] == "odi" and odi["matchEnded"] and odi["dateTimeGMT"] == "2026-11-04T02:00:00" and odi["teams"] == ["New Zealand", "India"], odi and odi["name"])
check("the result line and the player of the match are ESPN's own words: 'India won by 5 wkts (56b rem) (DLS)' and Anshul Kamboj (compared with the raw series scoreboard)", odi["status"] == raw_ev["status"]["summary"] == "India won by 5 wkts (56b rem) (DLS)" and odi["_card"]["potm"][0]["name"] == "Anshul Kamboj", odi["_card"])
check("the scores come from the line scores in batting order: New Zealand 185 all out in 40.2 overs, then India 143/5 in 22.4, matching the raw competitor scores ('185 (40.2 ov)', '143/5 ...')",
      [(x["inning"], x["r"], x["w"], x["o"]) for x in odi["score"]] == [("New Zealand Inning 1", 185, 10, 40.2), ("India Inning 1", 143, 5, 22.4)]
      and {c["team"]["displayName"]: c["score"] for c in raw_ev["competitions"][0]["competitors"]}["New Zealand"].startswith("185 (40.2") and ck.innings_line(odi["score"][1], odi["teams"]) == "India 143/5 (22.4)", odi["score"])
wbbl = next((m for m in got if m["event"] and "Big Bash" in m["name"]), None)
check("the Women's Big Bash game on now is recognised as a league match but is not finished, so the picker will not report it yet", wbbl and ck.classify(wbbl)["label"] == "WBBL" and not wbbl["matchEnded"] and "require" in wbbl["status"], wbbl and (wbbl["name"], wbbl["status"]))
_series_read = sorted({u.split("/cricket/")[1].split("/")[0] for u in feed_urls if "scoreboard/header" not in u})
check("series that are not in scope (Ranji Trophy, Ford Trophy, Quaid-e-Azam, an A-team tour) are never read: only the series with a wanted match cost a call (the header is read live and for yesterday and today by date)",
      len(_series_read) == 2 and sum(1 for u in feed_urls if "scoreboard/header" in u) == 3 and all(ck.classify(m)["kind"] for m in got), (_series_read, [m["name"] for m in got]))
check("same_match: the same two teams and the same number are one match, whatever the order or the Women suffix; another number or other teams are not", ck.same_match({"teams": ["New Zealand", "India"], "name": "New Zealand vs India, 1st ODI, tour"}, {"teams": ["India", "New Zealand"], "name": "India v New Zealand, 1st ODI"})
      and not ck.same_match({"teams": ["New Zealand", "India"], "name": "x, 1st ODI"}, {"teams": ["New Zealand", "India"], "name": "x, 2nd ODI"}) and ck.same_match({"teams": ["Sydney Sixers Women", "Perth Scorchers Women"], "name": "a, 3rd Match"}, {"teams": ["Sydney Sixers", "Perth Scorchers"], "name": "b, 3rd Match"}))
down = ec.Feed(lambda url: feed_get(url) if "header" in url else (_ for _ in ()).throw(OSError("down")), pause=0)
check("if a series' own scoreboard fails that series is skipped and nothing raises", ck.espn_matches(down) == [])
try:
    ec.Feed(lambda url: (_ for _ in ()).throw(OSError("down")), pause=0).matches()
    header_raised = False
except OSError:
    header_raised = True
check("if the header itself fails the feed raises, and cricket.run (tested below) catches it and carries on with the main list", header_raised)
NOW_ODI = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)
run_odi = ck.run(NOW_ODI, datetime(2026, 11, 2, 23, 15, tzinfo=timezone.utc), {}, lambda: ([], 5), lambda mid: (_ for _ in ()).throw(AssertionError("no CricketData scorecard should be bought")), lambda used: 5,
                 espn_extra=lambda ms: ck.espn_matches(ec.Feed(feed_get, pause=0)))
ph = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", run_odi["html"]))
check("the whole block for an ESPN-only match: 'New Zealand v India', '1st ODI', both scores, India's win and the player of the match, with no CricketData scorecard bought", run_odi["stats"]["picked"] == 1 and "New Zealand v India" in ph and "1st ODI" in ph and "185" in ph and "143/5" in ph and "Anshul Kamboj" in ph, ph[:400])
check("the match is remembered as reported, so tomorrow's edition does not repeat it", "espn-1539437" in run_odi["state"]["seen"], run_odi["state"]["seen"])
cd_odi = {"id": "c547eb46", "name": "New Zealand vs India, 1st ODI, India tour of New Zealand 2026", "teams": ["New Zealand", "India"], "dateTimeGMT": "2026-11-04T02:00:00", "matchStarted": True, "matchEnded": True,
          "status": "India won by 5 wkts  -  2nd inns reduced to 32 overs - DLS Target 143", "score": [{"inning": "New Zealand Inning 1", "r": 185, "w": 10, "o": 40.2}, {"inning": "India Inning 1", "r": 143, "w": 5, "o": 22.4}]}
cd_old = {"id": "wbbl8", "name": "Melbourne Stars Women vs Perth Scorchers Women, 8th Match, Womens Big Bash League 2026", "teams": ["Melbourne Stars Women", "Perth Scorchers Women"], "matchType": "t20", "dateTimeGMT": "2026-11-04T01:00:00",
          "matchStarted": True, "matchEnded": True, "status": "Perth Scorchers Women won by 3 wkts", "score": [{"inning": "Melbourne Stars Women Inning 1", "r": 150, "w": 8, "o": 20}, {"inning": "Perth Scorchers Women Inning 1", "r": 151, "w": 7, "o": 19.2}]}
both = ck.run(NOW_ODI, datetime(2026, 11, 2, 23, 15, tzinfo=timezone.utc), {}, lambda: ([cd_odi, cd_old], 5), lambda mid: (_ for _ in ()).throw(AssertionError("no")), lambda used: 5, espn_extra=lambda ms: ck.espn_matches(ec.Feed(feed_get, pause=0)))
bh = re.sub(r"<[^>]+>", "", both["html"])
check("ESPN first: CricketData lists the 1st ODI too (without a matchType) and ESPN's version replaces it (one New Zealand v India block, ESPN's id and result line), while a WBBL match only CricketData has is still reported (the backup)", both["html"].count("New Zealand v") == 1 and "espn-1539437" in both["state"]["seen"] and "c547eb46" not in both["state"]["seen"]
      and "India won by 5 wickets (DLS)" in bh and "Perth Scorchers W won by 3 wickets" in bh and "Women won" not in bh and "wbbl8" in both["state"]["seen"], (both["state"]["seen"], bh[:300]))
no_cd = ck.run(NOW_ODI, datetime(2026, 11, 2, 23, 15, tzinfo=timezone.utc), {}, lambda: (_ for _ in ()).throw(RuntimeError("no key")), lambda mid: None, lambda used: 0, espn_extra=lambda ms: ck.espn_matches(ec.Feed(feed_get, pause=0)))
check("without CricketData at all (no key, call limit reached, the list down) cricket still builds from ESPN's feed: the ODI with its result, scores and player of the match", no_cd["stats"]["picked"] == 1 and "New Zealand v" in re.sub(r"<[^>]+>", "", no_cd["html"]) and "Anshul Kamboj" in no_cd["html"] and no_cd["used"] == 0, no_cd["stats"])
run_boom = ck.run(NOW_ODI, datetime(2026, 11, 2, 23, 15, tzinfo=timezone.utc), {}, lambda: ([], 5), lambda mid: None, lambda used: 5, espn_extra=lambda ms: 1 / 0)
check("if ESPN's extra lookup blows up the cricket block still builds from the main list (here an empty one)", run_boom["html"] == "" and run_boom["stats"]["picked"] == 0)

# ---- The cricket cache: collected on the Mac, read by the daily run on GitHub ----
ck.card_consistent = real_card_consistent
import tempfile  # noqa: E402
from kickoff import cricketcache as cc  # noqa: E402

CARD_PAGE = (FX / "espn_cricket_scorecard_nz_ind.html").read_text()
NOW_C = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)


def mac_fetch(u):
    if u == ec.SCORES_URL:
        return SCORES
    if "scorecard/1539436" in u:
        return CARD_PAGE
    if "/cricket/table/series/21284" in u:
        return TABLE
    if "scores/series" in u or "/series/24469" in u and "scorecard" not in u:
        return SER
    raise OSError(u)


mac = ec.Source(mac_fetch, pause=0)
picked_c = ck.pick(ck.normalise(M), NOW_C, START)
cache = cc.collect(picked_c, mac, NOW_C)
raw_card = ec.parse_scorecard(CARD_PAGE)
check("collect on the Mac: the New Zealand v India T20I's scorecard from the saved ESPN page is in the cache, with its player of the match, once per match, and agrees with the match (the consistency check)",
      nzind["id"] in cache["cards"] and cache["cards"][nzind["id"]]["scorecard"] == raw_card and cache["cards"][nzind["id"]]["built"] == "2026-11-02T08:00:00Z" and len(cache["cards"]) == 1, list(cache["cards"]))
check("the WBBL points table is collected once for the league (one table, not one per WBBL match), as rows", list(cache["tables"]) == ["WBBL"] and len(cache["tables"]["WBBL"]["rows"]) >= 6, {k: len(v["rows"]) for k, v in cache["tables"].items()})
check("an ODI or Test series gets its series table keyed by match id (the T20I's series is left out, as the rules say), and nothing is collected for a match whose page cannot be read", all(k in {m["id"] for m in picked_c} for k in cache["series"]) and nzind["id"] not in cache["series"])
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "cache.json"
    cc.save(cache, path)
    back = cc.load(path)
    path.write_text("{bad")
    broken = cc.load(path)
    empty = {"cards": {}, "tables": {}, "series": {}}
    check("the cache survives a save and a load, and a missing or broken file loads as an empty cache", back == cache and cc.load(Path(td) / "none.json") == empty and broken == empty, (back == cache, broken))
stale_page = [dict(inn, espn=dict(inn["espn"], total={"r": 54, "w": 1, "o": 10.5, "rr": 4.98})) if i == 1 else inn for i, inn in enumerate(ec.parse_scorecard((FX / "espn_cricket_scorecard_nz_ind.html").read_text()))]
nz_m = dict(nzind, score=[{"inning": "New Zealand Inning 1", "r": ec.parse_scorecard((FX / "espn_cricket_scorecard_nz_ind.html").read_text())[0]["espn"]["total"]["r"], "w": ec.parse_scorecard((FX / "espn_cricket_scorecard_nz_ind.html").read_text())[0]["espn"]["total"]["w"], "o": 20}])
good_page = ec.parse_scorecard((FX / "espn_cricket_scorecard_nz_ind.html").read_text())
sc_both = [{"inning": f"X Inning {i + 1}", "r": inn["espn"]["total"]["r"], "w": inn["espn"]["total"]["w"], "o": inn["espn"]["total"]["o"]} for i, inn in enumerate(good_page)]
check("an ESPN page card is checked against the match's score line too: the real New Zealand v India T20I page passes against its own totals, and the 54/1 copy that a stale ESPN cache once gave the Mac (India's 143/5 final) is refused",
      ck.card_consistent({"scorecard": good_page}, {"score": sc_both}) and not ck.card_consistent({"scorecard": [good_page[0], dict(good_page[1], espn=dict(good_page[1]["espn"], total={"r": 54, "w": 1, "o": 10.5}))]}, {"score": sc_both}), sc_both)
stale_cache = {"cards": {nzind["id"]: {"built": "2026-11-02T07:00:00Z", "scorecard": stale_page}}, "tables": {}, "series": {}}
stale_src = type("S", (), {"card": lambda self, m: {"scorecard": stale_page, "status": "", "potm": []}, "table": lambda self, m: None, "series": lambda self, m: None})()
after = cc.collect([dict(nzind, score=sc_both, **{"class": ck.classify(nzind)})], stale_src, NOW_C, stale_cache)
check("collect refuses a stale page and also removes an older cached card for that match, so the wrong card cannot survive on the Mac or be read on GitHub", nzind["id"] not in after["cards"])
STALE = (FX / "espn_cricket_scorecard_multiday.html").read_text()
link, plain = "scorecard/1539436/new-zealand-vs-india-5th-t20i-24469", "series/24469/scorecard/1539436"


def fetcher(first, plain_page, log):
    def f(u):
        log.append(u)
        if u == ec.SCORES_URL:
            return SCORES
        return first if u.endswith(link) and "espn.in" not in u else plain_page if (u.endswith(plain) or "?t=" in u or "espn.in" in u) else (_ for _ in ()).throw(OSError(u))
    return f


log1, log2, log3 = [], [], []
c_fresh = ec.Source(fetcher(CARD_PAGE, STALE, log1), pause=0).card(nzind)
check("when the scores page's own link gives a card that agrees with the match, that is the one used and no other address is read", c_fresh and c_fresh["scorecard"] == raw_card and len(log1) == 2, log1)
c_retry = ec.Source(fetcher(STALE, CARD_PAGE, log2), pause=0).card(nzind)
check("ESPN served a stale page on the link (a card that contradicts the match, as India's 54/1 on 4 November): the plain /scorecard/<id> address is tried next and its card, which agrees, is used", c_retry and c_retry["scorecard"] == raw_card and len(log2) == 3 and log2[2].endswith(plain), log2)
c_none = ec.Source(fetcher(STALE, STALE, log3), pause=0).card(nzind)
check("when every address gives a card that contradicts the match there is no card at all, rather than a wrong one (the link, the plain address, a cache-busting query and ESPN's India host were all tried)", c_none is None and len(log3) == 5 and "?t=" in log3[3] and "espn.in" in log3[4], log3)
potm_feed = ck.espn_matches(ec.Feed(feed_get, pause=0))
odi_p = next(m for m in potm_feed if m["event"] == "1539437")["_card"]["potm"]
check("the player of the match carries his team from the feed (Anshul Kamboj, India), so the page never shows empty brackets; a person with no team shows just his name", odi_p == [{"name": "Anshul Kamboj", "team": "India"}] and "()" not in ck.potm_html({"potm": [{"name": "X Y", "team": ""}]}) and "(India)" in ck.potm_html({"potm": odi_p}))
old = {"cards": {"a": {"built": "2026-10-20T00:00:00Z", "scorecard": []}, "b": {"built": "2026-11-01T00:00:00Z", "scorecard": []}, "c": {"scorecard": []}}, "tables": {}, "series": {}}
check("entries older than four days, and entries with no valid stamp, are ignored: only 'b' (a day old) survives", list(cc.fresh(old, NOW_C)["cards"]) == ["b"])
card_f, table_f, series_f = cc.getters(cache, None)
check("the daily run's getters answer from the cache without touching ESPN: the card by match id, the league table by label, and None for anything not cached", card_f(nzind)["scorecard"] == raw_card and table_f({"class": {"label": "WBBL"}})[0]["team"] and table_f({"class": {"label": "IPL"}}) is None and card_f({"id": "zzz"}) is None and series_f({"id": "zzz"}) is None)
down = ec.Source(lambda u: (_ for _ in ()).throw(OSError("blocked")), pause=0)
card_g, _, _ = cc.getters(cache, down)
check("on GitHub the live source fails quietly: a cached card is still found, an uncached one is simply None (no error)", card_g(nzind) is not None and card_g({"id": "zzz", "teams": ["A", "B"], "name": "A vs B"}) is None)
run_c = ck.run(NOW_C, START, {}, lambda: (M, 17), lambda mid: (_ for _ in ()).throw(AssertionError("no CricketData scorecard should be bought for the cached match")) if mid == nzind["id"] else ({"scorecard": []}, 30), src.scorecards_affordable,
               espn_card=card_f, espn_table=table_f, espn_series=series_f)
sur = lambda n: n.split()[-1]  # noqa: E731
bat0, bowl0 = raw_card[0]["batting"][0]["batsman"]["name"], raw_card[0]["bowling"][0]["bowler"]["name"]
nz_block = run_c["html"].split("New Zealand v")[1].split("</li>")[0] if "New Zealand v" in run_c["html"] else ""
check("the whole run on GitHub with the Mac's cache: the New Zealand v India block has the full ESPN scorecard from the cache (the first batter and first bowler of the saved page, by surname), no CricketData scorecard bought, and the WBBL points table is there",
      sur(bat0) in nz_block and sur(bowl0) in nz_block and "WBBL table" in run_c["html"], (bat0, bowl0, nz_block[:200]))

# ---- a live match the scores page does not list: its own series and event ids make the address (the two Tests of 6 November)
_hid = {**nzind, "name": "Hidden v Match, 1st Test", "teams": ["Hidden", "Match"], "series": "24756", "event": "1553296"}
_seen = []
def _fetch_hidden(u):
    _seen.append(u)
    if u == ec.SCORES_URL:
        return SCORES                                 # the scores page, without this match
    if "/series/24756/scorecard/1553296" in u:
        return CARD_PAGE
    raise OSError(u)
_idx_miss = ec.Source(_fetch_hidden, pause=0)
_idx_miss.index = {}                                  # nothing on the scores page
_got = _idx_miss.card({**nzind, "series": "24756", "event": "1553296"})
check("a match missing from ESPN's scores page is still read from its own series and event ids (the address is built, then the card must still agree with the match)", _got is not None and any("/series/24756/scorecard/1553296" in u for u in _seen), _seen)
check("with no ids and no index entry there is no card, not an error", ec.Source(_fetch_hidden, pause=0).card({**nzind, "series": None, "event": None, "teams": ["Nobody", "Else"], "name": "Nobody vs Else"}) is None)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
