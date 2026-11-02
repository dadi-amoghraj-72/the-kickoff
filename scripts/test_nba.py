"""Offline tests for the NBA block, on saved real ESPN data (the 11 finished games of Saturday 31 October and Sunday 1 November 2026, their box
scores, the standings and LeBron James's and James Harden's career totals). Run: python3 scripts/test_nba.py"""
import copy
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import nba  # noqa: E402
from kickoff.sources import espn_nba  # noqa: E402

FX = ROOT / "tests" / "fixtures"
L = lambda n: json.loads((FX / n).read_text())  # noqa: E731
SBS, BOXES, STAND, CAR = L("nba_scoreboards.json"), L("nba_boxes.json"), L("nba_standings.json"), L("nba_careers.json")
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


NOW = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)
MON, TUE = date(2026, 11, 2), date(2026, 11, 3)


class Saved:
    def __init__(self, boxes=BOXES, sbs=SBS, fail_box=(), fail_career=False, fail_std=False, fail_sb=False):
        self.boxes, self.sbs, self.fail_box, self.fail_career, self.fail_std, self.fail_sb, self.calls = boxes, sbs, set(fail_box), fail_career, fail_std, fail_sb, 0

    def scoreboard(self, d):
        if self.fail_sb:
            raise RuntimeError("down")
        return self.sbs.get(str(d), {"events": []})

    def box(self, i):
        if i in self.fail_box:
            raise RuntimeError("down")
        return self.boxes[i]

    def career(self, i):
        if self.fail_career:
            raise RuntimeError("down")
        return CAR[i]

    def standings(self):
        if self.fail_std:
            raise RuntimeError("down")
        return STAND


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


EVENTS = [e for sb in SBS.values() for e in sb["events"]]
GAMES = [nba.parse_game(e) for e in EVENTS]
BYID = {g["id"]: g for g in GAMES}

# ---- Games ----
check("11 finished games parsed, none live or scheduled", len(GAMES) == 11 and all(g["status"] == "final" for g in GAMES))
ok = True
for gid, b in BOXES.items():
    last = b["plays"][-1]
    g = BYID[gid]
    ok &= (g["away"]["score"], g["home"]["score"]) == (last["away"], last["home"])
check("independent: every final score equals the last scoring play's running score in its own box score", ok)
check("home and away come from ESPN's homeAway field, not the list order (Orlando listed first but Boston is away)", BYID["401909903"]["home"]["abbr"] == "ORL" and BYID["401909903"]["away"]["abbr"] == "BOS")
check("a game is dated by its US Eastern day: tip-off 00:30 UTC on 1 November is 31 October", nba.day_of({"date": datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc)}) == date(2026, 10, 31))
ev = copy.deepcopy(EVENTS[0])
ev["status"]["period"] = 5
check("a game that went to a fifth period is overtime; a four-period one is not", nba.parse_game(ev)["ot"] and not BYID[EVENTS[0]["id"]]["ot"])
check("winner: ties give None, otherwise the higher score", nba.winner({"away": {"score": 5}, "home": {"score": 5}}) is None and nba.winner(BYID["401909903"]) == "away")
check("clock text: '47.6' is 47.6 seconds and '1:07' is 67", nba.seconds("47.6") == 47.6 and nba.seconds("1:07") == 67)

# ---- Players, standouts ----
PL = {gid: nba.players_of(b, BYID[gid]) for gid, b in BOXES.items()}
ALL = [p for ps in PL.values() for p in ps]
wem = next(p for p in ALL if p["id"] == "5104157")
check("Wembanyama's line matches the raw box score (43 pts, 7 reb, 4 ast, 6 blk, 17-34 FG)", (wem["PTS"], wem["REB"], wem["AST"], wem["BLK"], wem["fg"]) == (43, 7, 4, 6, "17-34"), wem)
bradley = next(p for p in ALL if p["id"] == "4065673")
check("a player with no stats (Tony Bradley) is marked dnp and gets no standout, even with big numbers forced in", bradley["dnp"] and not nba.kinds_of(dict(bradley, PTS=50)))
check("Paul George has a did-not-play-style reason but 33 minutes: he played, so he is not dnp", not next(p for p in ALL if p["id"] == "4251")["dnp"])
raw_hits = set()
for gid, b in BOXES.items():
    for t in b["players"]:
        d = None
        for a in t["athletes"]:
            if a["dnp"] or not a["stats"]:
                continue
            v = dict(zip(t["labels"], a["stats"]))
            pts, reb, ast, stl, blk = (int(v[k]) for k in ("PTS", "REB", "AST", "STL", "BLK"))
            if pts >= 40 or sum(x >= 10 for x in (pts, reb, ast, stl, blk)) >= 3 or (pts >= 20 and reb >= 20) or blk >= 5 or stl >= 5:
                raw_hits.add((a["id"], gid))
texts, hits = nba.standouts(ALL, BYID, BOXES)
check("independent: the standout hits equal a separate scan of the raw box scores (40 pts, triple-double, 20-20, 5 blocks, 5 steals, game-winner)", set(hits) >= raw_hits and len(set(hits) - raw_hits) <= 1, (set(hits) ^ raw_hits))
check("the real standouts are Doncic (45), Wembanyama (43) and Dunn (7 steals), best first", [t.split(" (")[0] for t in texts[:3]] == ["Luka Doncic", "Victor Wembanyama", "Kris Dunn"], texts)
check("a standout line says the stat line and the result from the player's side (Dunn's team lost)", "Kris Dunn (LAC): 12 pts, 2 reb, 4 ast, 7 stl; 124-112 loss to Warriors" in texts[2] and "131-125 win over Raptors" in texts[0], texts)
check("no standout line repeats its own stat as a tag (no '40-point game' text)", not any("point game" in t or "blocks)" in t for t in texts))
one = dict(wem, PTS=12, REB=10, AST=10, BLK=0)
check("a triple-double is a standout and is named; a double-double is not", "triple-double" in nba.kinds_of(one) and not nba.kinds_of(dict(one, AST=9)))
check("20 points and 20 rebounds is a standout; 19 rebounds is not", "20-20 game" in nba.kinds_of(dict(wem, PTS=20, REB=20, BLK=0)) and "20-20 game" not in nba.kinds_of(dict(wem, PTS=22, REB=19, BLK=0)))
check("thresholds are exact: 39 points no, 40 yes; 4 blocks no, 5 yes; 4 steals no, 5 yes", not nba.kinds_of(dict(wem, PTS=39, BLK=4, STL=4, REB=1, AST=1)) and nba.kinds_of(dict(wem, PTS=40, BLK=0, STL=0, REB=1, AST=1)) and nba.kinds_of(dict(wem, PTS=3, BLK=5, STL=0, REB=1, AST=1)) and nba.kinds_of(dict(wem, PTS=3, BLK=0, STL=5, REB=1, AST=1)))

# ---- Game-winners, comebacks, stories ----
def synth(plays, away=0, home=0):
    return {"plays": [{"text": t, "value": 2, "period": per, "clock": clk, "away": a, "home": h, "team": "1", "athlete": "9"} for t, per, clk, a, h in plays]}

G = {"away": {"score": 100, "short": "Away", "abbr": "AAA"}, "home": {"score": 102, "short": "Home", "abbr": "HHH"}, "ot": False}
win = synth([("x", 1, "5:00", 10, 20), ("y makes three", 4, "0:03", 100, 102)])
check("a go-ahead score in the last 5 seconds of the fourth is a game-winner", nba.deciding_play(G, synth([("x", 4, "1:00", 100, 99), ("y makes three", 4, "0:03", 100, 102)])) is not None)
check("a go-ahead at 20 seconds is not; nor is a lead held from the start", nba.deciding_play(G, synth([("x", 4, "1:00", 100, 99), ("y", 4, "0:20", 100, 102)])) is None and nba.deciding_play(G, synth([("x", 1, "5:00", 10, 20), ("y", 4, "0:03", 100, 102)])) is None)
check("a go-ahead in overtime counts; a go-ahead in the second quarter never does", nba.deciding_play(G, synth([("x", 5, "1:00", 100, 100), ("y", 5, "2.5", 100, 102)])) is not None and nba.deciding_play(G, synth([("x", 2, "0:01", 50, 52)])) is None)
check("a tie that is then broken counts as the lead change (tie at 100, then home scores)", nba.deciding_play(G, synth([("t", 4, "0:30", 100, 100), ("y", 4, "0:02", 100, 102)]))["clock"] == "0:02")
check("the most the winner trailed by: 16 down", nba.biggest_deficit(G, synth([("a", 2, "5:00", 40, 24), ("b", 4, "1:00", 100, 102)])) == 16)
check("the game-winner story names the shot and the clock", "free throw in the last 2.5s" in nba.story(G, synth([("x", 4, "1:00", 100, 99), ("Y makes free throw 1 of 2", 4, "2.5", 100, 102)])))
check("stories: comeback, close, rout, plain, overtime", "came back from 16 down" in nba.story(G, synth([("a", 2, "5:00", 40, 24), ("b", 4, "1:00", 100, 102)])) and "held on by 2" in nba.story(G, synth([("a", 1, "5:00", 10, 20)]))
      and "ran away with it by 30" in nba.story({**G, "home": {**G["home"], "score": 130}}, synth([("a", 1, "5:00", 10, 20)])) and "won by 12" in nba.story({**G, "home": {**G["home"], "score": 112}}, synth([("a", 1, "5:00", 10, 20)]))
      and "in overtime" in nba.story({**G, "ot": True}, synth([("a", 1, "5:00", 10, 20)])))

# ---- The whole run ----
out = nba.run(NOW, TUE, {}, Saved())
html, t = out["html"], text(out["html"])
S = out["stats"]
check("run: 11 new games, 11 box scores, nothing failed", S["new"] == 11 and S["boxes"] == 11 and S["failed"] == 0, S)
raw_star = set()
for gid, b in BOXES.items():
    for tm in b["players"]:
        for a in tm["athletes"]:
            if a["id"] in nba.TRACKED and not a["dnp"] and a["stats"]:
                raw_star.add(gid)
    if {t["team"] for t in b["players"]} & {"PHI", "CLE"}:
        raw_star.add(gid)
check("independent: star games are the games with a tracked player who played, plus the games of LeBron's and Harden's teams (8 of 11)", S["star"] == len(raw_star) == 8, (S["star"], len(raw_star)))
check("the star table says 8 of 11 games and 2 underdog wins; the other table says 3 games", "Star Games 8 of 11 games" in t and "2 underdog wins" in t and "Other Games 3 games" in t, t[:300])
raw_dogs = 0
for gid, b in BOXES.items():
    g = BYID[gid]
    o = b["odds"]
    dog = "away" if o["away_dog"] else "home" if o["home_dog"] else None
    raw_dogs += bool(dog and dog == nba.winner(g))
check("independent: underdog wins counted straight from the odds flags are 2, and the header says 2", raw_dogs == 2 and "2 underdog wins" in t, raw_dogs)
check("each underdog winner carries one gold asterisk: two in the games plus the one in the header line", html.count('class="dog"') == 3, html.count('class="dog"'))
bold = len(re.findall(r'<tr class="[ahw]+ ?w"', html)) + len(re.findall(r'td class="(?:aw|hm) w"', html))
check("every game has exactly one winner in bold (11)", bold == 11, bold)
check("each game's two team names come with full names in the star table and nicknames in the other table", "Minnesota Timberwolves" in t and "San Antonio Spurs" in t and "Kings 105–136 Grizzlies" in t, t[:600])
check("every home team has one house icon: 11", html.count('class="home"') == 11, html.count('class="home"'))
check("both days get a day label because the games span two US dates", "Sat 31 Oct" in t and "Sun 1 Nov" in t)
check("star games are in date order, Saturday's before Sunday's", t.index("Sat 31 Oct") < t.index("Sun 1 Nov") < t.index("Luka Doncic: 45 pts"))
check("tracked players' lines come from the raw stats: Wembanyama 43 pts, 7 reb, 4 ast, 6 blk · 17-34 FG; Durant 3 blk shown", "Victor Wembanyama: 43 pts, 7 reb, 4 ast, 6 blk · 17-34 FG" in t.replace(" ", " ") and "Kevin Durant: 14 pts, 3 reb, 4 ast, 3 blk" in t)
check("untracked stars are not in the star lines (Maxey scored 38 but is not tracked and not a standout)", "Tyrese Maxey" not in t)
check("LeBron did not play (absent from the box score) and still gets a line and the milestone: 43,522 pts (478 to 44,000)", "LeBron James: did not play" in t and "Career: 43,522 pts (478 to 44,000)" in t, t[t.find("LeBron") - 40:t.find("LeBron") + 200])
check("Harden played and gets his line plus the assists milestone, 89 to 9,000; no points milestone while 561 away", "James Harden: 13 pts, 6 reb, 7 ast" in t and "Career: 29,439 pts, 8,911 ast (89 to 9,000)" in t and "to 30,000" not in t)
check("Curry and Edwards sat out (not in the box) and get no line: only LeBron and Harden are always shown", "Stephen Curry" not in t and "Anthony Edwards" not in t)
check("standouts section lists Doncic first", "Standouts Luka Doncic (LAL)" in t)
check("state: the 11 games are reported, underdogs saved, the watched pair's teams remembered", len(out["state"]["reported"]) == 11 and set(out["state"]["dogs"]) == set(BOXES) and out["state"]["teams"] == {"1966": "PHI", "3992": "CLE"})

# ---- Rhythm and state ----
again = nba.run(NOW, MON, copy.deepcopy(out["state"]), Saved())
check("a second run with the saved state shows nothing new on a Monday (no repeats)", again["html"] == "" and again["stats"]["new"] == 0, again["stats"])
check("Tuesday adds the standings; Monday does not", "Standings" in t and "Standings" not in text(nba.run(NOW, MON, {}, Saved())["html"]))
tue_quiet = nba.run(NOW, TUE, copy.deepcopy(out["state"]), Saved())
check("a Tuesday with no new games still shows the standings, and only those", "Eastern Conference" in tue_quiet["html"] and "Star Games" not in tue_quiet["html"])
later = nba.run(NOW + timedelta(days=10), MON, {}, Saved())
check("games older than 60 hours that were never reported are ignored (a first run does not dump a month)", later["stats"]["new"] == 0)
early = datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)
check("a game that has not started yet at the run time is never reported: only the 7 of 31 October (started by then) count", nba.run(early, TUE, {}, Saved())["stats"]["new"] == sum(1 for g in GAMES if g["date"] <= early) == 7)
part = nba.run(NOW, MON, {"reported": ["401909896", "401909897"]}, Saved())
check("games already reported are skipped: 9 new with two in the state", part["stats"]["new"] == 9 and "Damian Lillard" not in text(part["html"]), part["stats"])

# ---- Standings ----
east = next(c for c in STAND["children"] if c["name"].startswith("East"))
seeds = sorted(int(next(s["displayValue"] for s in e["stats"] if s["name"] == "playoffSeed")) for e in east["standings"]["entries"])
rows_e = re.findall(r"<tr class=\"z-(?:blue|lilac)\">", nba.standings_html(STAND))
check("independent: ESPN gives seeds 1 to 15 for each conference, and the table lists 15 per conference in seed order", seeds == list(range(1, 16)) and nba.standings_html(STAND).count("<tbody>") == 2 and text(nba.standings_html(STAND)).index(" PHI ") < text(nba.standings_html(STAND)).index(" DET "))
check("zones: seeds 1 to 6 blue, 7 to 10 lilac, none after (20 coloured rows for the two conferences: 12 blue, 8 lilac)", len(rows_e) == 20 and nba.standings_html(STAND).count("z-blue") == 12 and nba.standings_html(STAND).count("z-lilac") == 8)
check("the leader's games-behind shows '-' and the others show the gap", "PHI 6-1 - W3" in text(nba.standings_html(STAND)) and "DET 5-1 0.5 W2" in text(nba.standings_html(STAND)))
check("standings sanity check refuses a broken feed (one conference)", not nba.standings_ok({"children": [STAND["children"][0]]}) and nba.standings_ok(STAND))

# ---- Milestones ----
check("milestones: close points show the distance; far points show only the total; exact thousand shows no distance", nba.milestone({"PTS": 43522, "AST": 12051}, "1966") == "Career: 43,522 pts (478 to 44,000)" and nba.milestone({"PTS": 29439, "AST": 100}, "x") == "Career: 29,439 pts" and nba.milestone({"PTS": 44000, "AST": 0}, "x") == "Career: 44,000 pts")
check("no career data gives no milestone line", nba.milestone(None, "1966") == "" and nba.milestone({}, "1966") == "")

# ---- Auto-join and drop-off ----
st = {}
d0 = date(2026, 11, 3)
nba.update_tracking(st, [("999", "g1")], {}, {"999": "Rookie One"}, d0)
nba.update_tracking(st, [("999", "g2")], {}, {"999": "Rookie One"}, d0 + timedelta(days=5))
check("two standout games are not enough to join", "999" not in st["auto"])
nba.update_tracking(st, [("999", "g2")], {}, {"999": "Rookie One"}, d0 + timedelta(days=6))
check("the same game counted twice does not count twice", "999" not in st["auto"] and len(st["hits"]["999"]) == 2)
ids = nba.update_tracking(st, [("999", "g3")], {}, {"999": "Rookie One"}, d0 + timedelta(days=10))
check("a third standout within 30 days adds the player automatically", "999" in st["auto"] and "999" in ids and st["auto"]["999"]["name"] == "Rookie One")
nba.update_tracking(st, [], {}, {}, d0 + timedelta(days=10 + 55))
check("55 days after the last standout he is still tracked", "999" in st["auto"])
nba.update_tracking(st, [], {}, {}, d0 + timedelta(days=10 + 57))
check("after 56 days without a standout he drops off", "999" not in st["auto"])
st2 = {}
for i, off in enumerate((0, 20, 40)):
    nba.update_tracking(st2, [("888", f"g{i}")], {}, {"888": "Slow"}, d0 + timedelta(days=off))
check("three standouts spread over 40 days do not qualify (only two fall inside any 30 days)", "888" not in st2["auto"])
st3 = {}
for i, h in enumerate(("1966", "5104157")):
    nba.update_tracking(st3, [(h, f"a{i}"), (h, f"b{i}"), (h, f"c{i}")], {}, {}, d0)
check("D's own list never goes into the auto list, and cannot be dropped", st3["auto"] == {} and set(nba.TRACKED) <= nba.update_tracking(st3, [], {}, {}, d0 + timedelta(days=400)))
dunn = {"auto": {next(p["id"] for p in ALL if p["name"] == "Kris Dunn"): {"name": "Kris Dunn", "last": "2026-11-01"}}}
check("an auto-added player is followed like D's own: Kris Dunn's Clippers-Warriors game moves into the star table with his line", "Kris Dunn: 12 pts, 2 reb, 4 ast, 7 stl" in text(nba.run(NOW, MON, dunn, Saved())["html"]) and nba.run(NOW, MON, dunn, Saved())["stats"]["star"] == 9)

# ---- Failures and edge cases ----
bad = nba.run(NOW, MON, {}, Saved(fail_box=["401909896"]))
check("one failed box score: that game is left out and not marked reported; the other 10 show", bad["stats"]["failed"] == 1 and bad["stats"]["new"] == 11 and "401909896" not in bad["state"]["reported"] and len(bad["state"]["reported"]) == 10 and "Damian Lillard" not in text(bad["html"]))
check("the failed game comes back next run", "Damian Lillard" in text(nba.run(NOW, MON, bad["state"], Saved())["html"]))
none = nba.run(NOW, TUE, {}, Saved(fail_sb=True, fail_std=True))
check("scoreboard and standings down: nothing shown, no crash, failures counted", none["html"] == "" and none["stats"]["failed"] == 4, none["stats"])
nocar = nba.run(NOW, MON, {}, Saved(fail_career=True))
check("career totals down: the games still show, only the milestone line is missing", "LeBron James: did not play" in text(nocar["html"]) and "Career:" not in text(nocar["html"]) and nocar["stats"]["failed"] == 2)
check("no games at all: no html", nba.run(NOW, MON, {}, Saved(sbs={}))["html"] == "")
mixed = copy.deepcopy(SBS)
mixed["2026-11-01"]["events"][0]["status"]["period"] = 5
check("an overtime game shows an OT tag; without it there is none", out["html"].count('class="ot">OT') == 0 and nba.run(NOW, MON, {}, Saved(sbs=mixed))["html"].count('class="ot">OT') == 1)
inj = copy.deepcopy(BOXES)
for tm in inj["401909900"]["players"]:
    for a in tm["athletes"]:
        if a["id"] == "3992":
            a["dnp"], a["reason"] = True, "REST"
rest = text(nba.run(NOW, MON, {}, Saved(boxes=inj))["html"])
check("a watched player listed as did-not-play shows his reason", "James Harden: did not play (rest)" in rest, rest[rest.find("Harden") - 5:rest.find("Harden") + 80])
moved = nba.run(NOW, MON, {"teams": {"1966": "MIL"}}, Saved())
check("a traded player is followed: with LeBron's saved team set to Milwaukee, his did-not-play line moves to the Cavaliers-Bucks game", text(moved["html"]).count("LeBron James: did not play") == 1 and moved["state"]["teams"]["1966"] == "MIL")

# ---- Source ----
CALLS = []
def fake_get(url):
    CALLS.append(url)
    if "summary" in url:
        return {"boxscore": {"teams": [{"team": {"abbreviation": "AAA"}, "statistics": [{"name": "blocks", "displayValue": "4"}]}],
                             "players": [{"team": {"abbreviation": "AAA"}, "statistics": [{"labels": ["MIN", "PTS"], "athletes": [{"athlete": {"id": "1", "displayName": "P One"}, "starter": True, "stats": ["30", "12"], "reason": "R"}]}]}]},
                "pickcenter": [{"details": "AAA -3", "spread": 3, "awayTeamOdds": {"underdog": False, "moneyLine": -150}, "homeTeamOdds": {"underdog": True, "moneyLine": 130}}],
                "plays": [{"text": "a", "scoringPlay": True, "scoreValue": 2, "period": {"number": 1}, "clock": {"displayValue": "9:00"}, "awayScore": 2, "homeScore": 0, "team": {"id": "5"}, "participants": [{"athlete": {"id": "1"}}]},
                          {"text": "b", "scoringPlay": False, "period": {"number": 1}, "clock": {"displayValue": "8:00"}, "awayScore": 2, "homeScore": 0}]}
    if "stats" in url:
        return {"categories": [{"name": "averages", "labels": ["PTS"], "totals": ["26.7"]}, {"name": "totals", "labels": ["FG", "REB", "PTS"], "totals": ["15992-31571", "12,130", "43,522"]}]}
    if "roster" in url:
        return {"athletes": [{"id": "7", "displayName": "Seven"}]}
    if url.endswith("/teams"):
        return {"sports": [{"leagues": [{"teams": [{"team": {"id": "2", "abbreviation": "BOS"}}]}]}]}
    return {"ok": url}

src = espn_nba.Source(fake_get, pause=0)
b = src.box("1")
check("source: a box score is trimmed to players, team totals, the pre-game line and only the scoring plays", b["players"][0]["athletes"][0] == {"id": "1", "name": "P One", "starter": True, "dnp": False, "reason": "R", "stats": ["30", "12"]} and b["teams"] == {"AAA": {"blocks": "4"}}
      and b["odds"]["home_dog"] is True and len(b["plays"]) == 1 and b["plays"][0]["athlete"] == "1" and b["plays"][0]["team"] == "5", b)
check("source: the scoreboard asks for the date as yyyymmdd; career takes the whole-number totals and strips commas", (src.scoreboard(date(2026, 11, 1)) and "dates=20261101" in CALLS[-1]) and src.career("1966") == {"REB": 12130, "PTS": 43522})
check("source: rosters and team ids", src.roster("2") == {"7": "Seven"} and src.teams() == {"2": "BOS"} and src.calls == 5)
check("NBA needs no Claude: neither module imports anthropic", "anthropic" not in (ROOT / "kickoff" / "nba.py").read_text() and "anthropic" not in (ROOT / "kickoff" / "sources" / "espn_nba.py").read_text())
check("D's 24 tracked players are all there and the watched pair are LeBron James and James Harden", len(nba.TRACKED) == 24 and [nba.TRACKED[i] for i in nba.WATCHED] == ["LeBron James", "James Harden"])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
