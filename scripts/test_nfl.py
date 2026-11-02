"""Offline tests for the NFL block, on saved real ESPN data (week 8 of the 2026 season, taken on Monday 2 November with the Sunday-night game
live and Monday night still to play). Run: python3 scripts/test_nfl.py"""
import copy
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import nfl  # noqa: E402
from kickoff.sources import espn_nfl  # noqa: E402

FX = ROOT / "tests" / "fixtures"
L = lambda n: json.loads((FX / n).read_text())  # noqa: E731
SB, BOXES, POS, STAND = L("nfl_w8_scoreboard.json"), L("nfl_w8_boxes.json"), L("nfl_w8_positions.json"), L("nfl_w8_standings.json")
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
MON, TUE, WED, SAT = date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 7)
NOW2 = datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc)  # after Sunday night and Monday night kicked off
GAMES = [nfl.parse_game(e) for e in SB["events"]]
FINAL = [g for g in GAMES if g["status"] == "final"]
PLAYERS = {gid: nfl.players_of(b, POS, gid) for gid, b in BOXES.items()}
ALL = [p for ps in PLAYERS.values() for p in ps]
BYID = {g["id"]: g for g in GAMES}

# ---- Games ----
check("14 games: 12 final, 1 live (Sunday night), 1 scheduled (Monday night)", [g["status"] for g in GAMES].count("final") == 12 and [g["status"] for g in GAMES].count("live") == 1
      and [g["status"] for g in GAMES].count("scheduled") == 1, [g["status"] for g in GAMES])
teams = [g[s]["abbr"] for g in GAMES for s in ("home", "away")] + [t["abbreviation"] for t in SB["teamsOnBye"]]
check("independent: every one of the 32 teams appears exactly once across the 14 games and the 4 byes", len(teams) == 32 and len(set(teams)) == 32, len(set(teams)))
gb = next(g for g in GAMES if g["home"]["abbr"] == "GB")
check("a game reads home, away, score, record and broadcaster (Thursday night: Panthers at Packers 19-27 on Prime Video)", gb["away"]["abbr"] == "CAR" and gb["home"]["score"] == 27 and gb["away"]["score"] == 19
      and gb["broadcast"] == "Prime Video" and gb["home"]["record"] and nfl.winner(gb) == "home", gb)
ot_raw = [e["id"] for e in SB["events"] if (e["status"].get("period") or 0) > 4 and e["status"]["type"]["name"] == "STATUS_FINAL"]
check("overtime games are flagged: the two found by a second reading of the raw period (Titans-Bengals, Cardinals-Cowboys)", sorted(g["id"] for g in FINAL if g["ot"]) == sorted(ot_raw) and len(ot_raw) == 2, ot_raw)
check("a live game has a score but is not final; a scheduled game has none", next(g for g in GAMES if g["status"] == "live")["home"]["score"] is not None and next(g for g in GAMES if g["status"] == "scheduled")["home"]["score"] is None)


def bucket(g):  # a second way to find kickoff groups, from the raw ISO time
    h = (g["date"].hour + g["date"].minute / 60 - 5) % 24  # Eastern Standard Time on 1 November (daylight time ended that morning)
    return (g["date"].date().isoformat() if g["date"].hour >= 5 else "prev", "morning" if h < 11 else "early" if h < 14.5 else "late" if h < 18 else "night")


groups = {nfl.slot(g) for g in FINAL}
check("kickoff groups among the finished games: Thursday night, Sunday early and Sunday late (three), and the late slot has the three 4 pm games", len(groups) == 3
      and sum(1 for g in FINAL if nfl.slot(g)[1] == "late") == 3, groups)
check("week names: regular season, playoff rounds, Super Bowl", nfl.week_name(8, 2) == "Week 8" and nfl.week_name(1, 3) == "Wild Card Round" and nfl.week_name(5, 3) == "Super Bowl")

# ---- Box scores, cross-checked against ESPN's own totals ----
bad, seen = [], 0
for gid, b in BOXES.items():
    for side in b["players"]:
        for cat in side["statistics"]:
            if cat["name"] == "passing":
                for a in cat["athletes"]:
                    c, att = nfl.pair(a["stats"][0])
                    if att >= 10:
                        seen += 1
                        mine = nfl.passer_rating(c, att, nfl.num(a["stats"][1]), nfl.num(a["stats"][3]), nfl.num(a["stats"][4]))
                        if abs(mine - nfl.num(a["stats"][7])) > 0.06:
                            bad.append((a["athlete"]["displayName"], round(mine, 2), a["stats"][7]))
check(f"independent: the passer rating we compute equals ESPN's own RTG for every quarterback with 10+ attempts ({seen} of them)", seen >= 20 and not bad, bad[:3])
bad, checked = [], 0
for gid, b in BOXES.items():
    for side in b["players"]:
        tid = side["team"]["id"]
        rush = sum(nfl.num(a["stats"][1]) for cat in side["statistics"] if cat["name"] == "rushing" for a in cat["athletes"])
        passing = sum(nfl.num(a["stats"][1]) for cat in side["statistics"] if cat["name"] == "passing" for a in cat["athletes"])
        sacked = sum(nfl.pair(a["stats"][5])[1] for cat in side["statistics"] if cat["name"] == "passing" for a in cat["athletes"])
        ts = b["teamStats"][tid]
        checked += 1
        if rush != nfl.num(ts["rushingYards"]) or passing - sacked != nfl.num(ts["netPassingYards"]):
            bad.append((gid, side["team"]["abbreviation"], rush, ts["rushingYards"], passing - sacked, ts["netPassingYards"]))
check(f"independent: player rushing yards add up to each team's rushing yards, and passing yards less sack yards to its net passing yards ({checked} teams)", checked == 24 and not bad, bad[:3])
check("every player in the 12 box scores has a known position", all(p["pos"] for p in ALL) and len(ALL) > 600, (sum(1 for p in ALL if not p["pos"]), len(ALL)))
check("short names are initial and surname, suffixes kept", {p["short"] for p in ALL if "Fannin" in p["name"]} == {"H. Fannin Jr."} and nfl.utc("2026-11-01T18:00Z").hour == 18)

# ---- Weekly leaders, each found a second way from the raw box scores ----
raw = {}  # athlete id -> raw per-category label dicts, read straight from the saved JSON
for gid, b in BOXES.items():
    for side in b["players"]:
        for cat in side["statistics"]:
            for a in cat["athletes"]:
                raw.setdefault(a["athlete"]["id"], {"name": a["athlete"]["displayName"], "team": side["team"]["abbreviation"], "cats": {}})["cats"][cat["name"]] = dict(zip(cat["labels"], a["stats"]))
lead = nfl.leaders(ALL)
byname = lambda ps: [p["name"] for p in ps]  # noqa: E731
want_qb = sorted([(nfl.num(v["cats"]["passing"]["RTG"]), v["name"]) for i, v in raw.items() if POS.get(i) == "QB" and "passing" in v["cats"] and nfl.pair(v["cats"]["passing"]["C/ATT"])[1] >= 10], reverse=True)[:3]
check("top 3 QBs by passer rating (10+ attempts) equal the top 3 by ESPN's own RTG", byname(lead["qb"]) == [w[1] for w in want_qb] and len(want_qb) == 3, (byname(lead["qb"]), want_qb))
check("QB list: ratings descend, and a 2-attempt cameo cannot appear", [nfl._rating(p) for p in lead["qb"]] == sorted([nfl._rating(p) for p in lead["qb"]], reverse=True) and all(nfl.pair(nfl.stat(p, "passing", "C/ATT"))[1] >= 10 for p in lead["qb"]))
for key, pool, cat, label in (("rb", ("RB", "FB"), "rushing", "YDS"), ("wr", ("WR",), "receiving", "YDS"), ("te", ("TE",), "receiving", "YDS")):
    want = sorted([(nfl.num(v["cats"][cat][label]), v["name"]) for i, v in raw.items() if POS.get(i) in pool and cat in v["cats"]], reverse=True)[:3]
    check(f"top 3 {key.upper()}s by yards equal the top 3 found from the raw box scores", [nfl.n(p, cat, label) for p in lead[key]] == [w[0] for w in want] and len(lead[key]) == 3, ([nfl.n(p, cat, label) for p in lead[key]], want))
check("wide receivers and tight ends are kept apart (no TE in the WR list, no WR in the TE list)", all(p["pos"] == "WR" for p in lead["wr"]) and all(p["pos"] == "TE" for p in lead["te"]))
want = sorted([nfl.num(v["cats"]["defensive"]["SACKS"]) for i, v in raw.items() if POS.get(i) in nfl.RUSH_POS and "defensive" in v["cats"]], reverse=True)[:3]
check("top pass rushers: the sack counts equal the three highest found from the raw data", [nfl.n(p, "defensive", "SACKS") for p in lead["rush"]] == want and want[0] > 0, (want, [nfl.n(p, "defensive", "SACKS") for p in lead["rush"]]))
want = sorted([nfl.num(v["cats"]["interceptions"]["INT"]) for i, v in raw.items() if POS.get(i) in nfl.BACK_POS and "interceptions" in v["cats"]], reverse=True)[:3]
check("top secondary: the interception counts equal the three highest found from the raw data", [nfl.n(p, "interceptions", "INT") for p in lead["back"]] == want and want[0] >= 1, want)
want = sorted([nfl.pair(v["cats"]["kicking"]["FG"])[0] for i, v in raw.items() if POS.get(i) in ("K", "PK") and "kicking" in v["cats"]], reverse=True)[:3]
check("top kickers: the field goals made equal the three highest found from the raw data", [nfl.pair(nfl.stat(p, "kicking", "FG"))[0] for p in lead["kick"]] == want and want[0] >= 3, want)
rawret = sorted([(nfl.num((v["cats"].get("kickReturns") or {}).get("TD", 0)) + nfl.num((v["cats"].get("puntReturns") or {}).get("TD", 0)),
                  nfl.num((v["cats"].get("kickReturns") or {}).get("YDS", 0)) + nfl.num((v["cats"].get("puntReturns") or {}).get("YDS", 0)), v["name"]) for v in raw.values()], reverse=True)
want_ret = [x for x in rawret if x[0] >= 1 or x[1] >= 100][:3]
check("returners: anyone with a return touchdown or 100+ return yards, touchdowns first then yards, top three, equal to a second reading of the raw data (D. Laube first)",
      [(nfl.returns(p)[1], nfl.returns(p)[0], p["name"]) for p in lead["ret"]] == want_ret and len(want_ret) == 3 and lead["ret"][0]["short"] == "D. Laube", (want_ret, [p["name"] for p in lead["ret"]]))
want_pt = sorted([(nfl.num(v["cats"]["punting"]["AVG"]), v["name"]) for i, v in raw.items() if POS.get(i) == "P" and "punting" in v["cats"] and nfl.num(v["cats"]["punting"]["NO"]) >= 3], reverse=True)[:3]
check("punters: the top three by average with 3+ punts equal a second reading of the raw data", [nfl.n(p, "punting", "AVG") for p in lead["punt"]] == [w[0] for w in want_pt] and len(want_pt) == 3, want_pt)
lh = nfl.leaders_html(lead, ALL)
check("special teams is one table with three sub-heading rows in order Kickers, Punters, Returners (9 player rows), and the old one-line returner and punter lines are gone", lh.count("Top Special Teams") == 1
      and lh.index(">Kickers<") < lh.index(">Punters<") < lh.index(">Returners<") and lh.count('<tr class="sub">') == 3 and "Returner:" not in lh and "Punter:" not in lh, lh.count('<tr class="sub">'))
check("every leader group has its three rows and no group mixes positions", all(len(lead[g]) == 3 for g in nfl.GROUPS) and all(p["pos"] in nfl.RUSH_POS for p in lead["rush"]) and all(p["pos"] in nfl.BACK_POS for p in lead["back"]))

# ---- D's quarterbacks under the top three ----
rated = sorted([(nfl.num(v["cats"]["passing"]["RTG"]), i) for i, v in raw.items() if POS.get(i) == "QB" and "passing" in v["cats"] and nfl.pair(v["cats"]["passing"]["C/ATT"])[1] >= 10], reverse=True)
rank_raw = {i: k + 1 for k, (_, i) in enumerate(rated)}
mine = lead["mine"]
lawrence = next(i for i, v in raw.items() if v["name"] == "Trevor Lawrence" and v["team"] == "JAX")
rodgers = next(i for i, v in raw.items() if v["name"] == "Aaron Rodgers" and v["team"] == "PIT")
check("Lawrence threw 14 passes for a 153.3 rating in the 42-7 win: with a 10-attempt minimum he is ranked first of the week, so he is in the top three and not added again", rank_raw[lawrence] == 1 and lawrence in {p["id"] for p in lead["qb"]} and all(p["id"] != lawrence for _, p in mine))
check("Rodgers (Steelers) is not in the top three, so he is added under it with his rank among all rated quarterbacks, equal to a second reading of ESPN's own ratings", [(r_, p["id"]) for r_, p in mine] == [(rank_raw[rodgers], rodgers)] and rank_raw[rodgers] > 3, (mine and [(r_, p["name"]) for r_, p in mine], rank_raw.get(rodgers)))
qh = re.search(r"<table>.*?</table>", nfl.leaders_html(lead, ALL), re.S).group(0)
check("the quarterback table has 4 player rows here (top three, a line, then Rodgers) and Lawrence appears once", qh.count("<tr") == 2 + 4 and qh.count('class="cut"') == 1 and qh.count("T. Lawrence") == 1 and qh.count("A. Rodgers") == 1 and "Top QBs" in qh, (qh.count("<tr"), qh.count("T. Lawrence")))
weak = [{**p, "stats": {**p["stats"], "passing": {**p["stats"]["passing"], "C/ATT": "10/20", "YDS": "100", "TD": "0", "INT": "2"}}} if p["id"] == lawrence else p for p in ALL]
wm = nfl.leaders(weak)["mine"]
check("if Lawrence has a poor day he is added under the top three with his rank, and Rodgers too: both listed, in D's order, no duplicates", [p["id"] for _, p in wm] == [lawrence, rodgers] and all(isinstance(r_, int) and r_ > 3 for r_, _ in wm), [(r_, p["name"]) for r_, p in wm])
few = [{**p, "stats": {**p["stats"], "passing": {**p["stats"]["passing"], "C/ATT": "4/8"}}} if p["id"] == rodgers else p for p in ALL]
check("a quarterback who threw fewer than 10 passes is still shown but with a dash for the rank", [r_ for r_, p in nfl.leaders(few)["mine"] if p["id"] == rodgers] == ["–"])
check("a quarterback who did not play is simply not listed", [p["id"] for _, p in nfl.my_qbs([p for p in ALL if p["id"] != rodgers], lead["qb"])] == [] and nfl.my_qbs([p for p in ALL if p["id"] not in (lawrence, rodgers)], lead["qb"]) == [])

# ---- Highlights and Player of the Week ----
def raw_kinds(v, pos):
    c = v["cats"]
    g = lambda cat, lab: nfl.num((c.get(cat) or {}).get(lab, 0))  # noqa: E731
    k = set()
    if pos == "QB" and (g("passing", "YDS") >= 350 or g("passing", "TD") >= 4 or (g("passing", "YDS") >= 300 and g("passing", "TD") >= 3 and g("passing", "INT") == 0) or g("rushing", "YDS") >= 100):
        k.add("x")
    if pos in ("RB", "FB") and (g("rushing", "YDS") >= 150 or g("rushing", "TD") + g("receiving", "TD") >= 3):
        k.add("x")
    if pos in ("WR", "TE") and (g("receiving", "YDS") >= 150 or g("receiving", "TD") >= 3):
        k.add("x")
    if pos in nfl.RUSH_POS + nfl.BACK_POS and (g("defensive", "SACKS") >= 3 or g("interceptions", "INT") >= 2 or g("defensive", "TD") + g("interceptions", "TD") >= 1):
        k.add("x")
    if g("kickReturns", "TD") + g("puntReturns", "TD") >= 1 or (pos in ("K", "PK") and g("kicking", "LONG") >= 55 and nfl.pair((c.get("kicking") or {}).get("FG", "0/0"))[0]):
        k.add("x")
    return k


expected = sorted(v["name"] for i, v in raw.items() if raw_kinds(v, POS.get(i)))
found = sorted(p["name"] for p in ALL if nfl.kinds_of(p))
check("independent: the players meeting a spec threshold (350+ yards, 150+ rushing, 3+ sacks, return touchdowns and so on) are the same ones found from the raw data", found == expected and len(found) >= 8, (found, expected))
hl = nfl.highlights(ALL, BYID)
check("highlights: at most five, best first, each one line naming the player, the team, the score and the opponent", 0 < len(hl) <= 5 and [t[0] for t in hl] == sorted([t[0] for t in hl], reverse=True)
      and all(re.search(r"\([A-Z]{2,3}\): .+ in the \d+-\d+ (win over|loss to|tie with) [A-Z]{2,3}\.$", t) for _, t in hl), [t for _, t in hl])
check("the best highlight is the Bengals' quarterback (462 yards, 5 touchdowns, 3 interceptions in the 43-36 win over TEN)", "J. Burrow (CIN): 38/48 for 462 yards, 5 touchdowns and 3 interceptions in the 43-36 win over TEN." == hl[0][1], hl[0][1])
mk = lambda **cats: {"id": "x", "short": "A. Test", "name": "A Test", "team": "AAA", "pos": cats.pop("pos", "QB"), "game": "g", "stats": {k: dict(zip(("C/ATT", "YDS", "AVG", "TD", "INT", "SACKS", "QBR", "RTG"), v)) if k == "passing" else v for k, v in cats.items()}}  # noqa: E731
check("points formula: QB 300 yds 3 TD 1 INT = 22; RB 100+20 yds, 1 TD, 3 catches = 19.5; defender 2 sacks + 1 INT = 16; kicker 3 FG with a 52-yarder = 11; return TD = 8",
      nfl.points(mk(passing=("20/30", "300", "10", "3", "1", "0-0", "0", "0"))) == 22.0
      and nfl.points(mk(pos="RB", rushing={"CAR": "20", "YDS": "100", "TD": "1"}, receiving={"REC": "3", "YDS": "20", "TD": "0"})) == 19.5
      and nfl.points(mk(pos="DE", defensive={"SACKS": "2", "TFL": "0", "PD": "0", "QB HTS": "0", "TD": "0"}, interceptions={"INT": "1", "TD": "0"})) == 16.0
      and nfl.points(mk(pos="K", kicking={"FG": "3/3", "LONG": "52", "PTS": "9"})) == 11.0
      and nfl.points(mk(pos="WR", kickReturns={"NO": "1", "YDS": "99", "TD": "1"})) == 8.0)
potw = nfl.player_of_the_week(ALL, BYID)
check("Player of the Week: three players, the highest points first, and it is the maximum over every player in the week", len(potw) == 3 and potw[0][0] == max(nfl.points(p) for p in ALL) and potw[0][0] >= potw[1][0] >= potw[2][0], [(a, p["short"]) for a, p, _ in potw])
check("its line carries the stat line and the result", "(CIN)" in potw[0][2] and potw[0][2].endswith("."), potw[0][2])

# ---- Scoreboard page ----
sb = nfl.scoreboard_html(FINAL, "Week 8", 12, 14, ["Saints", "Giants"])
rows_of = lambda html, k: re.findall(rf'<tr class="{k}[^"]*">.*?</tr>', html)  # noqa: E731
check("scoreboard: two rows per game (24), a white house icon on each home row only (12), the winner row marked (12)", len(rows_of(sb, "a")) == 12 and len(rows_of(sb, "h")) == 12 and sb.count('<svg class="home"') == 12
      and all('class="home"' in row for row in rows_of(sb, "h")) and not any('class="home"' in row for row in rows_of(sb, "a")) and len(re.findall(r'<tr class="[ah] w">', sb)) == 12, sb.count('class="home"'))
check("scoreboard: no emoji, full team names, a thick line between kickoff groups (2 for the finished games), overtime tags, the bye line", "🏠" not in sb and "Green Bay Packers" in sb and 'class="tm">Packers' not in sb and sb.count('<tr class="gap">') == 2
      and "12/14 games played" in sb and sb.count(">OT<") == 2 and "On bye: Saints, Giants." in sb, sb[:200])
check("scoreboard: nobody is highlighted for being D's team (no gold, no mine class)", "mine" not in sb and "Jacksonville Jaguars" in sb and "Pittsburgh Steelers" in sb)
full = nfl.scoreboard_html(GAMES, "Week 8", 12, 14, ["Saints"])
check("the whole week: all 14 games (28 rows), YTP once in the middle of the Monday-night game with no scores, LIVE on the Sunday-night game with its score, 4 group lines",
      len(rows_of(full, "a")) == 14 and len(rows_of(full, "h")) == 14 and full.count("YTP") == 1 and 'class="sc ytp" rowspan="2">YTP<' in full and full.count(">LIVE<") == 1 and full.count('<tr class="gap">') == 4, (full.count("YTP"), full.count("LIVE")))
live = next(g for g in GAMES if g["status"] == "live")
check("the live game shows its current score (WSH 16, PHI 10 when saved) and is not bold; the unplayed game shows no number at all", ">16<" in full and ">10<" in full and " w" not in "".join(re.findall(r'<tr class="[ah]([^"]*)">', "".join(r_ for r_ in rows_of(full, "a") + rows_of(full, "h") if "Commanders" in r_ or "Eagles" in r_ or "Seahawks" in r_ or "Bears" in r_))))
neutral = copy.deepcopy(FINAL[0])
neutral["neutral"] = True
check("a neutral-site game has no house for either team", 'class="home"' not in nfl.scoreboard_html([neutral], "Week 1", 1, 1))
tie = copy.deepcopy(FINAL[0])
tie["home"]["score"] = tie["away"]["score"]
tie_html = nfl.scoreboard_html([tie], "W", 1, 1)
check("a tie has no bold winner", nfl.winner(tie) is None and not any("w" in cls.split() for cls in re.findall(r'<tr class="([^"]*)"', tie_html)), re.findall(r'<tr class="([^"]*)"', tie_html))
evil = copy.deepcopy(FINAL[0])
evil["home"]["short"] = "<script>x</script>"
check("team names are escaped", "<script>" not in nfl.scoreboard_html([evil], "W", 1, 1))
check("nothing to show gives nothing", nfl.scoreboard_html([], "W", 0, 0) == "")

# ---- Standings ----
divs = [d for c in STAND["children"] for d in c["children"]]
check("standings: 8 divisions of 4 teams, 16 per conference", len(divs) == 8 and all(len(d["standings"]["entries"]) == 4 for d in divs) and [len(c["children"]) for c in STAND["children"]] == [4, 4])
pf = sum(nfl.num(nfl._stat(e, "pointsFor", "value")) for d in divs for e in d["standings"]["entries"])
pa = sum(nfl.num(nfl._stat(e, "pointsAgainst", "value")) for d in divs for e in d["standings"]["entries"])
check("independent: the league's points scored equal its points allowed (every point is scored by one team and allowed by another)", pf == pa and pf > 3000, (pf, pa))
check("record_of equals ESPN's own overall record string for all 32 teams", all(nfl.record_of(e) == nfl._stat(e, "overall") for d in divs for e in d["standings"]["entries"]), [(nfl.record_of(e), nfl._stat(e, "overall")) for d in divs for e in d["standings"]["entries"] if nfl.record_of(e) != nfl._stat(e, "overall")][:3])
dh = nfl.division_html(STAND)
check("division tables: eight, each titled with its division, each with four teams as 3-letter codes, nobody highlighted", dh.count('<th class="tt"') == 8 and all(d["name"] in dh for d in divs) and dh.count("<tr") == 8 * 6 and "mine" not in dh and ">BUF<" in dh and "Buffalo" not in dh, dh.count("<tr"))
check("division order: wins never rise down a division", all([nfl.num(nfl._stat(e, "wins", "value")) for e in d["standings"]["entries"]] == sorted([nfl.num(nfl._stat(e, "wins", "value")) for e in d["standings"]["entries"]], reverse=True) for d in divs))
for conf in STAND["children"]:
    seeds = sorted(int(nfl._stat(e, "playoffSeed", "value")) for d in conf["children"] for e in d["standings"]["entries"] if nfl._stat(e, "playoffSeed"))
    check(f"{conf['name']}: ESPN gives every team a distinct playoff seed from 1 to 16", seeds == list(range(1, 17)), seeds)
ph = nfl.playoff_html(STAND)
check("playoff picture: a table per conference, seeds 1 to 10 in order, a line after the seventh, seed 1 marked BYE, seeds 2-4 DIV and 5-7 WC", ph.count('<th class="tt"') == 2 and "AFC Playoff Picture" in ph and "NFC Playoff Picture" in ph and ph.count('class="cut"') == 2
      and ph.count(">DIV<") == 6 and ph.count(">WC<") == 6 and ph.count(">BYE<") == 2 and ph.count("<tr") == 2 * 12, (ph.count(">DIV<"), ph.count(">WC<"), ph.count("<tr")))
bye_rows = re.findall(r'<tr class="bye[^"]*">.*?</tr>', ph)
check("only the 1 seed of each conference is the gold bye row (2 in all), it says BYE, and it is the first row of its table", len(bye_rows) == 2 and all(">1<" in x and ">BYE<" in x for x in bye_rows) and all(ph.index(x) < ph.index(">2<", ph.index(x)) for x in bye_rows), bye_rows[:1])


# ---- The whole block, with a fake source ----
def synth_box(abbr_a, abbr_b, qb_name="Late QB", stars=(True, False)):
    """A small invented box score for a game that had not finished when the real data was saved: one star quarterback."""
    def side(abbr, tid, star):
        stats = [{"name": "passing", "labels": ["C/ATT", "YDS", "AVG", "TD", "INT", "SACKS", "QBR", "RTG"], "athletes": [
            {"athlete": {"id": f"{abbr}-qb", "displayName": f"{qb_name} {abbr}", "firstName": "Late", "lastName": f"QB{abbr}"}, "stats": (["30/35", "400", "11.4", "4", "0", "0-0", "90", "158.3"] if star else ["20/30", "150", "5", "0", "2", "2-10", "20", "30.0"])}]}]
        return {"team": {"id": tid, "abbreviation": abbr, "displayName": abbr, "shortDisplayName": abbr}, "statistics": stats}
    return {"teamStats": {}, "players": [side(abbr_a, "901", stars[0]), side(abbr_b, "902", stars[1])]}


def late_scoreboard(snf=True, mnf=True):
    sb = copy.deepcopy(SB)
    for e in sb["events"]:
        abbrs = [c["team"]["abbreviation"] for c in e["competitions"][0]["competitors"]]
        if (snf and "WSH" in abbrs) or (mnf and "SEA" in abbrs):
            e["status"] = {"period": 4, "type": {"name": "STATUS_FINAL", "state": "post", "completed": True, "detail": "Final", "shortDetail": "Final"}}
            for c in e["competitions"][0]["competitors"]:
                c["score"] = "27" if c["homeAway"] == "home" else "17"
    return sb


class Fake:
    def __init__(self, sb=None, late=(), week=None, season_type=None, broken=(), prev=None, boxes=None):
        self.sb = copy.deepcopy(sb or SB)
        if week:
            self.sb["week"]["number"] = week
        if season_type:
            self.sb["season"]["type"] = season_type
        self.boxes = copy.deepcopy(boxes or BOXES)
        for gid, box in late:
            self.boxes[gid] = box
        self.broken, self.prev, self.calls, self.log = set(broken), prev, 0, []

    def _hit(self, what, arg=None):
        self.calls += 1
        self.log.append((what, arg))
        if (what, arg) in self.broken or (what, None) in self.broken:
            raise RuntimeError("down")

    def scoreboard(self, week=None, season_type=None):
        self._hit("scoreboard", week)
        return self.prev if week and self.prev else self.sb

    def box(self, event_id):
        self._hit("box", event_id)
        return self.boxes[event_id]

    def roster(self, team_id):
        self._hit("roster", team_id)
        return {}

    def standings(self):
        self._hit("standings")
        return STAND


SB_LATE = late_scoreboard()
snf_id = next(e["id"] for e in SB["events"] if "WSH" in [c["team"]["abbreviation"] for c in e["competitions"][0]["competitors"]])
mnf_id = next(e["id"] for e in SB["events"] if "SEA" in [c["team"]["abbreviation"] for c in e["competitions"][0]["competitors"]])
POS_LATE = {**POS, "WSH-qb": "QB", "PHI-qb": "QB", "SEA-qb": "QB", "CHI-qb": "QB"}
LATE_SNF = [(snf_id, synth_box("WSH", "PHI"))]
LATE_BOTH = LATE_SNF + [(mnf_id, synth_box("SEA", "CHI"))]
st0 = {"positions": POS_LATE}
f = Fake()
mon = nfl.run(NOW, MON, copy.deepcopy(st0), f)
h = mon["html"]
check("Monday: scoreboard of the 12 finished games, the bye line, weekly leaders and highlights; no Player of the Week, divisions or playoff picture",
      "Week 8" in h and "12/14 games played" in h and "On bye:" in h and "Weekly Leaders" in h and "Highlights" in h and "Player of the Week" not in h and "Division" not in h and "AFC East" not in h and "Playoff" not in h, mon["stats"])
check("Monday: 1 scoreboard call plus 12 box scores and no roster calls (positions were known); all 12 games remembered, leaders snapshot saved", [x[0] for x in f.log].count("scoreboard") == 1 and [x[0] for x in f.log].count("box") == 12
      and "roster" not in [x[0] for x in f.log] and len(mon["state"]["reported"]) == 12 and mon["state"]["leaders"]["week"] == 8 and set(mon["state"]["leaders"]["ids"]) == set(nfl.GROUPS), f.log[:3])
check("Monday's scoreboard lists the whole week: 14 games, the Sunday-night game LIVE, the Monday-night game YTP", mon["html"].count('<tr class="a') == 14 and mon["html"].count("YTP") == 1 and mon["html"].count(">LIVE<") == 1 and "12/14 games played" in mon["html"], mon["stats"])
again = nfl.run(NOW, MON, mon["state"], Fake())
check("running Monday again shows nothing new (no scoreboard, no leaders, no highlights)", again["html"] == "" and again["stats"]["new"] == 0, again["stats"])
nopos = nfl.run(NOW, MON, {}, f3 := Fake())
check("rosters are asked for only when a position is missing: 24 teams, none repeated, and the saved positions then cover everyone", sorted(x[1] for x in f3.log if x[0] == "roster") == sorted(set(x[1] for x in f3.log if x[0] == "roster"))
      and len([x for x in f3.log if x[0] == "roster"]) == 24 and nopos["stats"]["unknown_positions"] > 600, (len([x for x in f3.log if x[0] == "roster"]), nopos["stats"]))

# Tuesday: the Sunday-night game finishes
tue = nfl.run(NOW2, TUE, copy.deepcopy(mon["state"]), Fake(sb=late_scoreboard(mnf=False), late=LATE_SNF))
check("Tuesday: the week's scoreboard with the Sunday-night game now final (13 of 14 played, Monday night still YTP), its highlight (a 400-yard quarterback), and no weekly leaders", tue["stats"]["new"] == 1 and tue["html"].count('<tr class="a') == 14 and tue["html"].count("YTP") == 1 and "13/14 games played" in tue["html"]
      and "Weekly Leaders" not in tue["html"] and "Late QB WSH" not in tue["html"] and "L. QBWSH (WSH): 30/35 for 400 yards, 4 touchdowns and 0 interceptions in the 27-17 win over PHI." in tue["html"].replace("&#x27;", "'"), tue["html"][:200])
# Wednesday: Monday night also done; the wrap
wed = nfl.run(NOW2, WED, copy.deepcopy(mon["state"]), Fake(sb=SB_LATE, late=LATE_BOTH))
hw = wed["html"]
check("Wednesday: the whole week's scoreboard (all 14 games), the leaders again, highlights, Player of the Week and the eight division tables", hw.count('<tr class="a') == 14 and "14/14 games played" in hw and "Weekly Leaders" in hw
      and "Player of the Week" in hw and hw.count("Division Standings") == 1 and "AFC East" in hw and "NFC West" in hw, wed["stats"])
check("Wednesday: the two late-game quarterbacks (158.3 rating) enter the top three and are tagged new, and nobody else is", hw.count('class="new">new</span>') == 2 and "L. QBSEA" in hw and "L. QBWSH" in hw, hw.count('class="new"'))
check("Wednesday: no playoff picture before week 14, and once every game is final no YTP and no LIVE are left", "Playoff Picture" not in hw and "YTP" not in hw and ">LIVE<" not in hw)
wed_quiet = nfl.run(NOW2, WED, copy.deepcopy(mon["state"]), Fake(sb=SB_LATE, late=[(snf_id, synth_box("WSH", "PHI", stars=(False, False))), (mnf_id, synth_box("SEA", "CHI", stars=(False, False)))]))
check("Wednesday with nothing changed in any top three: one line says so instead of repeating the seven tables", "No change in the top three of any group since Monday." in wed_quiet["html"] and "Top QBs" not in wed_quiet["html"], wed_quiet["stats"])
fresh = nfl.run(NOW2, WED, {"positions": POS_LATE}, Fake(sb=SB_LATE, late=LATE_BOTH))
check("Wednesday without a Monday snapshot shows every leader table with no 'new' tags", "Top QBs" in fresh["html"] and 'class="new"' not in fresh["html"])
w13 = nfl.run(NOW2, WED, copy.deepcopy(st0), Fake(sb=SB_LATE, late=LATE_BOTH, week=13))
w14 = nfl.run(NOW2, WED, copy.deepcopy(st0), Fake(sb=SB_LATE, late=LATE_BOTH, week=14))
check("playoff picture: none in week 13; from week 14 a heading plus an AFC and an NFC table", "Playoff Picture" not in w13["html"] and "AFC Playoff Picture" in w14["html"] and "NFC Playoff Picture" in w14["html"] and w14["html"].count("Playoff Picture") == 3, (w13["week"], w14["week"], w14["html"].count("Playoff Picture")))
# Saturday: Thursday night game of the next week
sat_sb = copy.deepcopy(SB)
sat_sb["week"]["number"] = 9
sat = nfl.run(NOW, SAT, copy.deepcopy(st0), Fake(sb=sat_sb))
check("Saturday (and any day): finished games not yet shown appear with a scoreboard only; no leaders on a Saturday", sat["html"].count('<tr class="a') == 14 and "Weekly Leaders" not in sat["html"] and "Week 9" in sat["html"], sat["stats"])
# Scoreboard has moved on to the next week by Wednesday
nxt = copy.deepcopy(SB)
nxt["week"] = {"number": 9, "teamsOnBye": []}
for e in nxt["events"]:
    e["status"] = {"period": 0, "type": {"name": "STATUS_SCHEDULED", "state": "pre", "completed": False, "detail": "", "shortDetail": ""}}
    for c in e["competitions"][0]["competitors"]:
        c["score"] = "0"
moved = nfl.run(NOW2, WED, copy.deepcopy(st0), fm := Fake(sb=nxt, prev=late_scoreboard(), late=LATE_BOTH))
check("if the scoreboard has already moved to the next week, the finished week is fetched and used for the wrap", ("scoreboard", 8) in fm.log and moved["week"] == 8 and "Week 8" in moved["html"], fm.log[:3])
# Failures
dead = nfl.run(NOW, MON, copy.deepcopy(st0), Fake(broken=[("scoreboard", None)]))
check("scoreboard down: nothing shown, no exception, state kept, failure counted", dead["html"] == "" and dead["stats"]["failed"] == 1 and dead["state"]["positions"] == POS_LATE)
one = nfl.run(NOW, MON, copy.deepcopy(st0), Fake(broken=[("box", next(iter(BOXES)))]))
check("one box score down: that game is still on the scoreboard, leaders use the other eleven, failure counted", one["stats"]["failed"] == 1 and one["html"].count('<tr class="a') == 14 and one["stats"]["boxes"] == 11 and "Top QBs" in one["html"], one["stats"])
stand_down = nfl.run(NOW2, WED, copy.deepcopy(st0), Fake(sb=SB_LATE, late=LATE_BOTH, broken=[("standings", None)]))
check("standings down on Wednesday: the rest of the wrap still shows", "Division Standings" not in stand_down["html"] and "Player of the Week" in stand_down["html"] and stand_down["stats"]["failed"] == 1)
pre = nfl.run(NOW, MON, copy.deepcopy(st0), Fake(season_type=1))
check("preseason is not covered", pre["html"] == "" and pre["week"] is None)
post = nfl.run(NOW2, WED, copy.deepcopy(st0), Fake(sb=SB_LATE, late=LATE_BOTH, season_type=3, week=1))
check("playoff weeks use the round name and have no division tables or playoff picture", "Wild Card Round" in post["html"] and "Division Standings" not in post["html"] and "Playoff Picture" not in post["html"])

# ---- The source ----
CALLS = []


def fake_get(url):
    CALLS.append(url)
    if "scoreboard" in url:
        return SB
    if "summary" in url:
        gid = url.rsplit("=", 1)[1]
        return {"boxscore": {"teams": [{"team": {"id": tid}, "statistics": [{"name": k, "displayValue": v} for k, v in st.items()]} for tid, st in BOXES[gid]["teamStats"].items()], "players": BOXES[gid]["players"]}}
    if "roster" in url:
        return {"athletes": [{"items": [{"id": "1", "position": {"abbreviation": "QB"}}, {"id": "2", "position": {"abbreviation": "WR"}}]}]}
    return STAND


src = espn_nfl.Source(fake_get, pause=0)
gid0 = next(iter(BOXES))
bx = src.box(gid0)
check("source: a box score keeps the players and the two team totals we cross-check with", bx["players"] == BOXES[gid0]["players"] and set(next(iter(bx["teamStats"].values()))) == {"rushingYards", "netPassingYards"})
check("source: rosters give athlete id to position; week asks for the week and season type; standings ask for divisions", src.roster("2") == {"1": "QB", "2": "WR"} and (src.scoreboard(7, 2) and "week=7&seasontype=2" in CALLS[-1]) and (src.standings() and "level=3" in CALLS[-1]) and src.calls == 4)
check("NFL needs no Claude: neither module imports anthropic", "anthropic" not in (ROOT / "kickoff" / "nfl.py").read_text() and "anthropic" not in (ROOT / "kickoff" / "sources" / "espn_nfl.py").read_text())

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
