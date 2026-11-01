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
check("the row after the finals cut-off line (Melbourne Stars, 5th) is not lost", rows[4]["name"] == "Melbourne Stars Women" and rows[4]["team"] == "MS" and rows[4]["nrr"] == -0.075, rows[4])
check("every team's played = won + lost + tied + no result, and the points are 2 a win", all(x["p"] == x["w"] + x["l"] + x["t"] + x["nr"] and x["pts"] == 2 * x["w"] for x in rows), rows)
check("abbreviations are the official ones with the '-W' dropped", [x["team"] for x in rows] == ["SS", "ST", "PS", "AS", "MS", "BH", "MR", "HH"], [x["team"] for x in rows])
th = ck.table_html("WBBL", rows)
check("the table block: caption, numbers right-aligned, signed three-place NRR, no Ties column when nobody has tied",
      "<caption>WBBL table</caption>" in th and "+2.250" in th and "-2.625" in th and "<th class=\"n\">T</th>" not in th and th.count("<tr>") == 8 + 1, th[:300])
tied = [dict(x) for x in rows]
tied[0].update(t=1, p=3, pts=5)
check("a Ties column appears when a team has tied", "<th class=\"n\">T</th>" in ck.table_html("WBBL", tied))
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

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
