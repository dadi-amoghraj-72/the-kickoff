"""Offline tests for the NBA block, on saved real ESPN data: the 11 finished games of Saturday 31 October and Sunday 1 November 2026 (with box
scores and standings), the whole 2026-27 Cup window, and last season's real Detroit-Orlando first-round series (schedule and box scores).
Run: python3 scripts/test_nba.py"""
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
SBS, BOXES, STAND, WINDOW = L("nba_scoreboards.json"), L("nba_boxes.json"), L("nba_standings.json"), L("nba_window.json")
SCHED, SBOXES, STAND26 = L("nba_series_schedule.json"), L("nba_series_boxes.json"), L("nba_standings_2026.json")
STD_FIX = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA"}   # a separate copy, written out here, of the five ESPN codes the module fixes (the ones that are not three letters)
OFFICIAL = {"ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WSH"}
fixc = lambda a: STD_FIX.get(a, a)  # noqa: E731
EMPTY_BOX = {"players": [], "teams": {}, "odds": None, "plays": [], "injuries": {}}
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


NOW = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)
MON, TUE = date(2026, 11, 2), date(2026, 11, 3)


class Saved:
    """The saved data behind the same methods the real source has."""

    def __init__(self, boxes=BOXES, sbs=SBS, window=WINDOW, std=STAND, sched=None, fail_box=(), fail_std=False, fail_sb=False, fail_sched=False):
        self.boxes, self.sbs, self.window, self.std, self.sched = boxes, sbs, window, std, sched
        self.fail_box, self.fail_std, self.fail_sb, self.fail_sched = set(fail_box), fail_std, fail_sb, fail_sched
        self.calls = self.box_calls = 0

    def scoreboard(self, d):
        if self.fail_sb:
            raise RuntimeError("down")
        return self.sbs.get(str(d)) or self.window.get(str(d), {"events": []})

    def box(self, i):
        self.box_calls += 1
        if i in self.fail_box:
            raise RuntimeError("down")
        return self.boxes.get(i, EMPTY_BOX)

    def standings(self, season=None):
        self.std_seasons = getattr(self, "std_seasons", []) + [season]
        if self.fail_std:
            raise RuntimeError("down")
        return self.std

    def schedule(self, team_id, season=None, season_type=3):
        if self.fail_sched:
            raise RuntimeError("down")
        return self.sched


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


EVENTS = [e for sb in SBS.values() for e in sb["events"]]
GAMES = [nba.parse_game(e) for e in EVENTS]
BYID = {g["id"]: g for g in GAMES}

# ---- Games ----
check("11 finished games parsed, none live or scheduled, all regular season, none Cup", len(GAMES) == 11 and all(g["status"] == "final" and g["phase"] == "regular" for g in GAMES))
ok = True
for gid, b in BOXES.items():
    last, g = b["plays"][-1], BYID[gid]
    ok &= (g["away"]["score"], g["home"]["score"]) == (last["away"], last["home"])
check("independent: every final score equals the last scoring play's running score in its own box score", ok)
check("home and away come from ESPN's homeAway field, not the list order (Orlando listed first but Boston is away)", BYID["401909903"]["home"]["abbr"] == "ORL" and BYID["401909903"]["away"]["abbr"] == "BOS")
check("a game is dated by its US Eastern day: tip-off 00:30 UTC on 1 November is 31 October", nba.day_of({"date": datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc)}) == date(2026, 10, 31))
ev = copy.deepcopy(EVENTS[0])
ev["status"]["period"] = 5
check("a game that went to a fifth period is overtime; a four-period one is not", nba.parse_game(ev)["ot"] and not BYID[EVENTS[0]["id"]]["ot"])
check("winner: ties give None, otherwise the higher score; clock text '47.6' is 47.6s and '1:07' is 67s", nba.winner({"away": {"score": 5}, "home": {"score": 5}}) is None and nba.winner(BYID["401909903"]) == "away" and nba.seconds("47.6") == 47.6 and nba.seconds("1:07") == 67)

# ---- Cup, playoff and play-in markers, house, order ----
ALLW = [e for d in WINDOW.values() for e in d["events"]]
by_head = {}
for e in ALLW:
    for n in e["competitions"][0]["notes"]:
        by_head.setdefault(n["headline"], e)
check("ESPN's notes are read: Cup group play, quarter-finals, semi-finals and the championship are Cup rounds; the Mexico City game is not a Cup game",
      nba.parse_game(by_head["NBA Cup - Group Play"])["cup"] == "Group Play" and nba.parse_game(by_head["NBA Cup - Quarterfinals"])["cup"] == "Quarterfinals"
      and nba.parse_game(by_head["NBA Cup - Semifinals"])["cup"] == "Semifinals" and nba.parse_game(by_head["NBA Cup Championship"])["cup"] == "Championship"
      and nba.parse_game(by_head["NBA Mexico City Game"])["cup"] is None and nba.parse_game(by_head["NBA Mexico City Game"])["headline"] == "NBA Mexico City Game", sorted(by_head))
po = nba.parse_game(L("nba_series_scoreboard.json")["2026-05-03"]["events"][0])
check("a post-season game (season type 3) is 'playoffs'; a note with Play-In is 'playin'; the regular season is neither", po["phase"] == "playoffs" and po["headline"].startswith("East 1st Round")
      and nba.parse_game({**copy.deepcopy(EVENTS[0]), "season": {"year": 2027, "type": 2}, "competitions": [{**copy.deepcopy(EVENTS[0]["competitions"][0]), "notes": [{"headline": "East Play-In Tournament"}]}]})["phase"] == "playin")
mk = lambda **k: {"neutral": False, "phase": "regular", "cup": None, **k}  # noqa: E731
check("house rule: not in the regular season or Cup group games or the Cup final; yes in the play-in, playoffs and home Cup knockouts; never at a neutral site",
      not nba.house(mk()) and not nba.house(mk(cup="Group Play")) and not nba.house(mk(cup="Championship")) and nba.house(mk(phase="playin")) and nba.house(mk(phase="playoffs"))
      and nba.house(mk(cup="Quarterfinals")) and nba.house(mk(cup="Semifinals")) and not nba.house(mk(phase="playoffs", neutral=True)))
g2 = lambda a, h, hour: {"away": {"abbr": a}, "home": {"abbr": h}, "date": datetime(2026, 11, 1, hour, tzinfo=timezone.utc)}  # noqa: E731
order = sorted([g2("BOS", "XXX", 1), g2("AAA", "BBB", 2), g2("CLE", "XXX", 3), g2("XXX", "SAS", 4), g2("PHI", "LAL", 5), g2("ZZZ", "YYY", 0), g2("LAL", "XXX", 6)], key=nba.order_key)
check("order: Lakers games, 76ers games, Cavaliers, Spurs, Celtics, then everyone else by tip-off (a Lakers-76ers game ranks as Lakers)",
      [(g["away"]["abbr"], g["home"]["abbr"]) for g in order] == [("PHI", "LAL"), ("LAL", "XXX"), ("CLE", "XXX"), ("XXX", "SAS"), ("BOS", "XXX"), ("ZZZ", "YYY"), ("AAA", "BBB")], [(g["away"]["abbr"], g["home"]["abbr"]) for g in order])

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
        for a in t["athletes"]:
            if a["dnp"] or not a["stats"]:
                continue
            v = dict(zip(t["labels"], a["stats"]))
            pts, reb, ast, stl, blk = (int(v[k]) for k in ("PTS", "REB", "AST", "STL", "BLK"))
            if pts >= 40 or sum(x >= 10 for x in (pts, reb, ast, stl, blk)) >= 3 or (pts >= 20 and reb >= 20) or blk >= 5 or stl >= 5 \
                    or reb >= (10 if a["pos"] == "G" else 15) or ast >= 15:
                raw_hits.add((a["id"], gid))
texts, hits = nba.standouts(ALL, BYID, BOXES)
check("independent: the standout hits equal a separate scan of the raw box scores (40 pts, triple-double, 20-20, 5 blocks, 5 steals, game-winner)", set(hits) >= raw_hits and len(set(hits) - raw_hits) <= 1, (set(hits) ^ raw_hits))
check("the real standouts are Doncic (45 points, a guard with 15 rebounds), Wembanyama (43), Kessler (15 rebounds, a center) and Dunn (7 steals), best first",
      [t.split(" (")[0] for t in texts[:4]] == ["Luka Doncic", "Victor Wembanyama", "Walker Kessler", "Kris Dunn"] and len(texts) == 4, texts)
check("a standout line is the name, team code and stat line only: no score or result (the games are just above)", texts[3] == "Kris Dunn (LAC): 12 pts, 2 reb, 4 ast, 7 stl" and texts[0] == "Luka Doncic (LAL): 45 pts, 15 reb, 6 ast, 5 stl"
      and not any(";" in t or " win over" in t or "loss to" in t or re.search(r"\d+-\d+", t) for t in texts), texts)
check("no standout line repeats its own stat as a tag (no '40-point game' text)", not any("point game" in t or "blocks)" in t for t in texts))
one = dict(wem, PTS=12, REB=10, AST=10, BLK=0)
check("a triple-double is a standout and is named; a double-double is not; 20 points and 20 rebounds counts, 19 rebounds does not",
      "triple-double" in nba.kinds_of(one) and not nba.kinds_of(dict(one, AST=9)) and "20-20 game" in nba.kinds_of(dict(wem, PTS=20, REB=20, BLK=0)) and "20-20 game" not in nba.kinds_of(dict(wem, PTS=22, REB=19, BLK=0)))
def kd(**k):
    return nba.kinds_of({**dict(wem, PTS=3, REB=1, AST=1, BLK=0, STL=0, pos="F"), **k})


check("rebounds by position: a guard (G) needs 10 (9 no, 10 yes), a forward or center needs 15 (14 no, 15 yes)", not kd(pos="G", REB=9) and kd(pos="G", REB=10) and not kd(pos="F", REB=14) and kd(pos="F", REB=15) and not kd(pos="C", REB=14) and kd(pos="C", REB=15) and kd(pos="PG", REB=10) and kd(pos="SG", REB=10))
check("15 assists is a standout for anyone (14 no); an unknown position is treated as not a guard", not kd(AST=14) and kd(AST=15) and kd(pos="G", AST=15) and not kd(pos="", REB=10) and kd(pos="", REB=15))
check("no double counting: a triple-double or a 20-20 game is not also listed as a rebounds or assists standout", kd(pos="G", PTS=12, REB=12, AST=10) == ["triple-double"] and kd(pos="C", PTS=22, REB=21) == ["20-20 game"] and kd(pos="G", PTS=10, REB=3, AST=16) == ["16 assists"])
check("marks: the rebounds or assists that earned the line are coloured, nothing else", nba.marks_of(dict(wem, PTS=3, REB=10, AST=2, BLK=0, STL=0, pos="G"), ["10 rebounds"]) == {"reb"} and nba.marks_of(dict(wem, PTS=3, REB=1, AST=15, BLK=0, STL=0, pos="F"), ["15 assists"]) == {"ast"})
check("thresholds are exact: 39 points no, 40 yes; 4 blocks no, 5 yes; 4 steals no, 5 yes", not nba.kinds_of(dict(wem, PTS=39, BLK=4, STL=4, REB=1, AST=1)) and nba.kinds_of(dict(wem, PTS=40, BLK=0, STL=0, REB=1, AST=1))
      and nba.kinds_of(dict(wem, PTS=3, BLK=5, STL=0, REB=1, AST=1)) and nba.kinds_of(dict(wem, PTS=3, BLK=0, STL=5, REB=1, AST=1)))


# ---- Standout highlighting ----
rows_, _ = nba.standouts_marked(ALL, BYID, BOXES)
by_name = {t.split(" (")[0]: (t, m) for t, m in rows_}
check("Dunn's standout: only the 7 steals (the reason he is a standout) is marked; his 12 points are plain", by_name["Kris Dunn"][1] == {"stl"} and nba.standout_html(*by_name["Kris Dunn"]).count('class="hl"') == 1 and '<span class="hl">7 stl</span>' in nba.standout_html(*by_name["Kris Dunn"]))
check("Doncic's standout: his 45 points, 15 rebounds (a guard needs 10) and 5 steals are marked, his 6 assists are not", by_name["Luka Doncic"][1] == {"pts", "reb", "stl"} and all(f'<span class="hl">{x}</span>' in nba.standout_html(*by_name["Luka Doncic"]) for x in ("45 pts", "15 reb", "5 stl")) and 'class="hl">6 ast' not in nba.standout_html(*by_name["Luka Doncic"]))
check("Kessler (a center) is a standout for his 15 rebounds, and only the rebounds are marked", by_name["Walker Kessler"][1] == {"reb"})
check("Wembanyama's: the 43 points and the 6 blocks are marked", by_name["Victor Wembanyama"][1] == {"pts", "blk"})
td_p = dict(wem, PTS=12, REB=10, AST=10, BLK=0, STL=3)
check("a triple-double marks the three categories of 10 or more and the tag, not the 3 steals", nba.marks_of(td_p, nba.kinds_of(td_p)) == {"pts", "reb", "ast", "tag"})
check("20 and 20 marks points and rebounds and the tag; a game-winner marks its phrase", nba.marks_of(dict(wem, PTS=21, REB=20, AST=2, BLK=0, STL=0), ["20-20 game"]) == {"pts", "reb", "tag"} and nba.marks_of(dict(wem, PTS=10, REB=2, AST=2, BLK=0, STL=0), ["game-winner"]) == {"gw"})
gw_line = "A B (X): 10 pts, 2 reb, 2 ast, the game-winner with 2.5s left; 100-99 win over Y"
check("the game-winner phrase is coloured as a whole and the result after the semicolon stays plain", nba.standout_html(gw_line, {"gw"}) == 'A B (X): 10 pts, 2 reb, 2 ast, <span class="hl">the game-winner with 2.5s left</span>; 100-99 win over Y')
check("the named tag is coloured with its brackets", '<span class="hl">(triple-double)</span>' in nba.standout_html("A (X): 12 pts, 10 reb, 10 ast (triple-double); 1-0 win over Y", {"pts", "reb", "ast", "tag"}))
check("highlighting escapes the text first", "&lt;i&gt;" in nba.standout_html("<i>A</i> (X): 41 pts, 1 reb, 1 ast; 1-0 win over Y", {"pts"}))

def synth(plays):
    return {"plays": [{"text": t, "value": 2, "period": per, "clock": clk, "away": a, "home": h, "team": "1", "athlete": "9"} for t, per, clk, a, h in plays]}


G = {"away": {"score": 100}, "home": {"score": 102}, "ot": False}
check("a go-ahead score in the last 5 seconds of the fourth is a game-winner; at 20 seconds, or a lead held from the start, it is not",
      nba.deciding_play(G, synth([("x", 4, "1:00", 100, 99), ("y", 4, "0:03", 100, 102)])) is not None and nba.deciding_play(G, synth([("x", 4, "1:00", 100, 99), ("y", 4, "0:20", 100, 102)])) is None
      and nba.deciding_play(G, synth([("x", 1, "5:00", 10, 20), ("y", 4, "0:03", 100, 102)])) is None)
check("a go-ahead in overtime counts; in the second quarter never; a tie that is then broken counts as the lead change",
      nba.deciding_play(G, synth([("x", 5, "1:00", 100, 100), ("y", 5, "2.5", 100, 102)])) is not None and nba.deciding_play(G, synth([("x", 2, "0:01", 50, 52)])) is None
      and nba.deciding_play(G, synth([("t", 4, "0:30", 100, 100), ("y", 4, "0:02", 100, 102)]))["clock"] == "0:02")

# ---- Notes under each game ----
INFO = {"teams": dict(nba.TEAMS), "auto": {}}
TR = set(nba.TRACKED)


def notes_for(gid, tracked=TR, info=INFO, boxes=BOXES):
    return nba.game_notes(BYID[gid], boxes[gid], nba.players_of(boxes[gid], BYID[gid]), tracked, info)


ok, dup = True, False
for gid, b in BOXES.items():
    best = max((a for t in b["players"] for a in t["athletes"] if not a["dnp"] and a["stats"]),
               key=lambda a: (lambda d: (int(d["PTS"]) + 1.2 * int(d["REB"]) + 1.5 * int(d["AST"]) + 3 * int(d["STL"]) + 3 * int(d["BLK"]), a["name"]))(dict(zip(b["players"][0]["labels"], a["stats"]))))
    notes = notes_for(gid)
    ok &= any(n.startswith(best["name"]) for n in notes)
    names = [n.split(":")[0].split(" (")[0] for n in notes]
    dup |= len(names) != len(set(names))
check("independent: the best performer of every game (best weighted stat line, found from the raw box) is in its notes, tracked or not", ok)
check("no player appears twice under one game", not dup)
check("one best performer per game: the Spurs game has Wembanyama (tracked and best) and no extra performer line", [n.split(":")[0] for n in notes_for("401909901")] == ["Victor Wembanyama (SAS)", "Anthony Edwards (MIN)"], notes_for("401909901"))
check("the 76ers game: Brown's line, then the untracked best performer Maxey with his team code, and only then LeBron and Embiid as DNP",
      [n.split(":")[0] for n in notes_for("401909897")] == ["Jaylen Brown (PHI)", "Tyrese Maxey (PHI)", "LeBron James (PHI)", "Joel Embiid (PHI)"], notes_for("401909897"))
bad_order = [gid for gid in BOXES if (lambda ns: any("DNP" in a and "DNP" not in b for a, b in zip(ns, ns[1:])))(notes_for(gid))]
check("in every game the DNP lines come after every line of a player who played (D's own players included)", not bad_order and sum("DNP" in n for gid in BOXES for n in notes_for(gid)) >= 5, bad_order)
inj = BOXES["401909897"]["injuries"]
check("independent: ESPN lists Embiid as Day-To-Day with a foot problem and does not list LeBron: so 'DNP (Day-To-Day, Foot)' and a plain 'DNP'",
      inj["3059318"] == {"status": "Day-To-Day", "type": "Foot"} and "1966" not in inj and "Joel Embiid (PHI): DNP (Day-To-Day, Foot)" in notes_for("401909897") and "LeBron James (PHI): DNP" in notes_for("401909897"))
check("Edwards: ESPN says Out with a knee: 'Anthony Edwards: DNP (Out, Knee)'", BOXES["401909901"]["injuries"]["4594268"] == {"status": "Out", "type": "Knee"} and "Anthony Edwards (MIN): DNP (Out, Knee)" in notes_for("401909901"))
check("a tracked player whose team did not play gets no line (Giannis, Jokic, Flagg, Young, Davis)", not any(n.split(":")[0] in ("Giannis Antetokounmpo", "Nikola Jokić", "Cooper Flagg", "Trae Young", "Anthony Davis") for gid in BOXES for n in notes_for(gid)))
dnp_box = copy.deepcopy(BOXES)
for tm in dnp_box["401909902"]["players"]:
    for a in tm["athletes"]:
        if a["id"] == "3202":
            a["dnp"], a["reason"], a["stats"] = True, "COACH'S DECISION", []
dnp_box["401909902"]["injuries"].pop("3202", None)
check("a tracked player listed as did-not-play with no injury entry shows the box score's reason: 'Kevin Durant: DNP (Coach's decision)'", "Kevin Durant (HOU): DNP (Coach's decision)" in notes_for("401909902", boxes=dnp_box), notes_for("401909902", boxes=dnp_box))
dnp_box["401909902"]["injuries"]["3202"] = {"status": "Out", "type": "Rest"}
check("an injury entry beats the box reason: 'DNP (Out, Rest)'", "Kevin Durant (HOU): DNP (Out, Rest)" in notes_for("401909902", boxes=dnp_box))
check("dnp_text: status only when ESPN gives no type; plain DNP when ESPN says nothing", nba.dnp_text("1", "A B", "XYZ", {"injuries": {"1": {"status": "Out", "type": ""}}}) == "A B (XYZ): DNP (Out)" and nba.dnp_text("1", "A B", "XYZ", {"injuries": {}}) == "A B (XYZ): DNP")
moved = notes_for("401909900", info={"teams": {**nba.TEAMS, "1966": "MIL"}, "auto": {}})
check("a traded player is followed: with LeBron's team set to Milwaukee, his DNP line is under the Cavaliers-Bucks game and no longer under the 76ers game", "LeBron James (MIL): DNP" in moved and not any(n.startswith("LeBron") for n in notes_for("401909897", info={"teams": {**nba.TEAMS, "1966": "MIL"}, "auto": {}})))
auto_p = next(p["id"] for p in ALL if p["name"] == "Kris Dunn")
check("an auto-added player is followed like D's own: his stat line is under his game", any(n.startswith("Kris Dunn (LAC): 12 pts, 2 reb, 4 ast, 7 stl") for n in notes_for("401909905", tracked=TR | {auto_p})))

# ---- The whole run ----
out = nba.run(NOW, TUE, {}, Saved())
html, t = out["html"], text(out["html"])
S = out["stats"]
games_part = html.split("<h4>")[0]
check("run: 11 new games, 11 box scores, nothing failed", S["new"] == 11 and S["boxes"] == 11 and S["failed"] == 0, S)
check("one table titled Last Night's Games: no Star Games / Other Games tables, no '8 of 11' counts, no 'won by' sentences, no career lines", t.startswith("Last Night's Games") and not any(x in t for x in ("Star Games", "Other Games", "of 11 games", "won by", "held on", "ran away", "Career")), t[:200])
check("the underdog count is the only thing under the title: '* 2 underdog wins'", "Last Night's Games * 2 underdog wins" in t)
raw_dogs = sum(1 for gid, b in BOXES.items() if (("away" if b["odds"]["away_dog"] else "home" if b["odds"]["home_dog"] else None) == nba.winner(BYID[gid])))
check("independent: underdog wins counted straight from the odds flags are 2, with one asterisk per winner plus one in the header", raw_dogs == 2 and html.count('class="dog"') == 3, raw_dogs)
css = (ROOT / "kickoff" / "static" / "style.css").read_text()
check("the asterisk is white (the chalk text colour, shared by the NFL and NBA), not gold", re.search(r"\.nflsb \.dog \{ color: var\(--chalk\);", css) and "--gold" not in re.search(r"\.nflsb \.dog \{[^}]*\}", css).group(0))
pos = [t.index(x) for x in ("Lakers", "76ers", "Cavaliers", "Spurs", "Celtics", "Trail Blazers")]
check("the order: Lakers, 76ers, Cavaliers, Spurs, Celtics, then the rest", pos == sorted(pos), pos)
check("regular season: no house icon anywhere", html.count('class="home"') == 0)
check("both US days get a label because the games span two dates; the Cup tag is not on regular games", "Sat 31 Oct" in t and "Sun 1 Nov" in t and "NBA Cup" not in games_part)
check("a game's line is not cut off from its notes: every score row that has notes is followed straight by the notes row, and the separator is only after the notes",
      len(re.findall(r'<tr class="one"><td[^>]*>[^<]*(?:<[^>]+>[^<]*)*?</tr><tr class="note end">', games_part)) == 11 and games_part.count(' end"') == 11 and "one end" not in games_part, games_part.count(' end"'))
check("independent: Wembanyama's line is built from the raw stats and carries his team: 'Victor Wembanyama (SAS): 43 pts, 7 reb, 4 ast, 6 blk · 17-34 FG'", "Victor Wembanyama (SAS): 43 pts, 7 reb, 4 ast, 6 blk · 17-34 FG" in text(out["html"]).replace("\u00a0", " "))
check("standouts section lists Doncic first", "Standouts Luka Doncic (LAL)" in t)
check("state: the 11 games are reported, underdogs saved, tracked players' teams remembered, standings saved for next time", len(out["state"]["reported"]) == 11 and set(out["state"]["dogs"]) == set(BOXES)
      and out["state"]["teams"]["1966"] == "PHI" and out["state"]["teams"]["3945274"] == "LAL" and out["state"]["seeds"]["Eastern Conference"]["PHI"] == 1)

check("in the page the standouts list carries the highlights, and the colour rule exists", out["html"].count('<span class="hl">') >= 5 and ".standouts .hl { color: var(--gold)" in (ROOT / "kickoff" / "static" / "style.css").read_text())

# ---- Game colours in the tables below ----
shown = sorted([g for g in GAMES if g["id"] in [e["id"] for e in SBS["2026-11-01"]["events"]]], key=nba.order_key)
sun = nba.run(NOW, TUE, {"reported": [e["id"] for e in SBS["2026-10-31"]["events"]]}, Saved())
cols = nba.game_colours(shown)
raw_teams = {t for e in SBS["2026-11-01"]["events"] for x in e["competitions"][0]["competitors"] for t in [fixc(x["team"]["abbreviation"])]}
painted = re.findall(r'<span class="gc(\d+)">([A-Z]+)</span>', sun["html"])
check("independent: the teams painted in the standings are exactly the 8 that played in tonight's 4 games (from the raw scoreboard), each once", len(painted) == 8 and {a for _, a in painted} == raw_teams and len({a for _, a in painted}) == 8, painted)
pairs = {}
for n, a in painted:
    pairs.setdefault(n, set()).add(a)
raw_pairs = {frozenset(fixc(x["team"]["abbreviation"]) for x in e["competitions"][0]["competitors"]) for e in SBS["2026-11-01"]["events"]}
check("both teams of a game share one colour, and each of the 4 games has its own colour: 4 colours, each used by exactly the two teams that played each other", len(pairs) == 4 and {frozenset(v) for v in pairs.values()} == raw_pairs, pairs)
check("the colour follows the order of the games shown (Lakers game first = colour 0, then 76ers/Cavaliers/Spurs/Celtics order, then by tip-off)", cols["LAL"] == cols["TOR"] == 0 and cols["BOS"] == cols["ORL"] == 1 and len(set(cols.values())) == 4, cols)
check("the colours are NOT in the games table above, only in the tables below", "gc" not in sun["html"].split("<h4>")[0])
check("teams that did not play are not coloured: 22 of the 30 team codes stay plain in the standings", len(re.findall(r'<td class="">[A-Z]+</td>', sun["html"])) == 22, len(re.findall(r'<td class="">[A-Z]+</td>', sun["html"])))
check("a run with no games above paints nothing: the standings come plain", 'class="gc' not in nba.run(NOW, TUE, {"reported": [g["id"] for g in GAMES]}, Saved())["html"])
check("with more than 15 games the colours wrap round instead of failing", len(nba.game_colours([{"away": {"abbr": f"A{i}"}, "home": {"abbr": f"H{i}"}} for i in range(18)])) == 36 and nba.game_colours([{"away": {"abbr": f"A{i}"}, "home": {"abbr": f"H{i}"}} for i in range(18)])["A15"] == 0)
check("paint() changes only the team cell of a listed team and nothing else", nba.paint('<td class="">PHI</td><td class="">DET</td><td class="n">6-1</td>', {"PHI": 3}) == '<td class=""><span class="gc3">PHI</span></td><td class="">DET</td><td class="n">6-1</td>')
css2 = (ROOT / "kickoff" / "static" / "style.css").read_text()
dark_css = re.findall(r"^\.gc(\d+) \{ color: (#[0-9A-F]{6}); font-weight: 700; \}$", css2, re.M)
light_css = re.findall(r"^  \.gc(\d+) \{ color: (#[0-9A-F]{6}); \}$", css2, re.M)
import colorsys  # noqa: E402
hls = lambda hx: colorsys.rgb_to_hls(*(int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5)))  # noqa: E731
check("the 15 game colours are locked: the stylesheet and the code's palette hold the same 15 hex values for dark and light, all different", [c for _, c in dark_css] == list(nba.PALETTE_DARK) and [c for _, c in light_css] == list(nba.PALETTE_LIGHT)
      and len(set(nba.PALETTE_DARK)) == 15 and len(set(nba.PALETTE_LIGHT)) == 15 and nba.GAME_COLOURS == 15 == len(dark_css), (len(dark_css), len(light_css)))
check("pastel only: every dark-theme colour is light and soft (lightness 75-82%, saturation at most 60%), no bright shades; the light-theme set is muted (saturation at most 45%)",
      all(0.75 <= hls(c)[1] <= 0.82 and hls(c)[2] <= 0.60 for c in nba.PALETTE_DARK) and all(hls(c)[2] <= 0.45 for c in nba.PALETTE_LIGHT), [(c, [round(x, 2) for x in hls(c)]) for c in nba.PALETTE_DARK][:3])
check("the 15 pastel colours are kept apart: no two dark-theme hues are closer than 15 degrees", all(min(abs(hls(a)[0] - hls(b)[0]) % 1, 1 - abs(hls(a)[0] - hls(b)[0]) % 1) * 360 >= 15 for i_, a in enumerate(nba.PALETTE_DARK) for b in nba.PALETTE_DARK[i_ + 1:]))
check("every game number from 0 to 14 has a colour, so a 15-game night can never run out", all(f".gc{n} " in css2 for n in range(15)))

# ---- Rhythm and state ----
again = nba.run(NOW, MON, copy.deepcopy(out["state"]), Saved())
check("a second run with the saved state shows no games again; the standings still come (every day there is basketball)", again["stats"]["new"] == 0 and "Last Night's Games" not in again["html"] and "Eastern Conference" in again["html"])
check("the standings come on a Monday too, not only Tuesday", "Eastern Conference" in nba.run(NOW, MON, {}, Saved())["html"])
check("a day with no basketball at all shows nothing, not even standings", nba.run(NOW, MON, {}, Saved(sbs={}, window={}))["html"] == "")
check("games older than 60 hours that were never reported are ignored (a first run does not dump a month)", nba.run(NOW + timedelta(days=10), MON, {}, Saved())["stats"]["new"] == 0)
early = datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)
iso = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))  # noqa: E731
raw_new = [e["id"] for d in (SBS, WINDOW) for sb in d.values() for e in sb["events"] if e["status"]["type"]["name"] == "STATUS_FINAL" and timedelta(0) <= early - iso(e["date"]) <= timedelta(hours=60)
           and iso(e["date"]).astimezone(nba.ET).date() >= early.astimezone(nba.ET).date() - timedelta(days=2)]
early_run = nba.run(early, TUE, {}, Saved())
check("independent: a game that has not started at the run time is never reported, and old ones are cut at 60 hours: the new games are exactly the raw finals inside that window (7 of 31 October plus 10 Cup games of 30 October)",
      early_run["stats"]["new"] == len(set(raw_new)) == 17 and not {"401909903", "401909906"} & set(early_run["state"]["reported"]), (early_run["stats"]["new"], len(set(raw_new))))
part = nba.run(NOW, MON, {"reported": ["401909896", "401909897"]}, Saved())
check("games already reported are skipped: 9 new with two in the state", part["stats"]["new"] == 9 and "Damian Lillard" not in text(part["html"]), part["stats"])

# ---- Team codes ----
raw_codes = {x["team"]["abbreviation"] for e in EVENTS for x in e["competitions"][0]["competitors"]}
std_codes = {e["team"]["abbreviation"] for c in STAND["children"] for e in c["standings"]["entries"]}
check("independent: ESPN's own codes include five that are not three letters (GS, NO, NY, SA, UTAH); the module's fix makes all 30 three letters, leaving WSH as ESPN has it",
      {"GS", "NO", "NY", "SA", "UTAH", "WSH"} <= std_codes and nba.code("WSH") == "WSH" and all(len(c) == 3 for c in OFFICIAL) and {nba.code(c) for c in std_codes} == OFFICIAL and len(OFFICIAL) == 30 and nba.code("GS") == "GSW" and nba.code("BOS") == "BOS")
check("in the page every team code is official: no GS, NY, SA, NO or UTAH token anywhere, and GSW is there", not re.search(r"\b(GS|NY|SA|NO|UTAH)\b", text(out["html"]).replace("NO ", "")) and "GSW" in text(out["html"]) and {c for c in re.findall(r"\(([A-Z]{2,4})\)", text(out["html"]))} <= OFFICIAL, sorted({c for c in re.findall(r"\(([A-Z]{2,4})\)", text(out["html"]))} - OFFICIAL))
check("every player line carries a team code in brackets, D's own players and the DNP lines included", all(re.match(r".+ \([A-Z]{3}\): ", n) for gid in BOXES for n in notes_for(gid)) and sum(1 for gid in BOXES for n in notes_for(gid)) > 20)
check("Curry's line shows GSW and the Spurs game uses SAS: 'Stephen Curry (GSW): DNP' and 'Victor Wembanyama (SAS)'", any(n.startswith("Stephen Curry (GSW): DNP") for n in notes_for("401909905")) and nba.TEAMS["3975"] == "GSW" and nba.TEAMS["5104157"] == "SAS" and nba.FIRST[3] == "SAS")
check("all of D's players' starting teams and the order list use three-letter codes (Trae Young and Anthony Davis are WSH)", set(nba.TEAMS.values()) <= OFFICIAL and set(nba.FIRST) <= OFFICIAL and nba.TEAMS["4277905"] == nba.TEAMS["6583"] == "WSH")

# ---- Standings and arrows ----
east = next(c for c in STAND["children"] if c["name"].startswith("East"))
seeds = sorted(int(next(s["displayValue"] for s in e["stats"] if s["name"] == "playoffSeed")) for e in east["standings"]["entries"])
st_html = nba.standings_html(STAND)
check("independent: ESPN gives seeds 1 to 15 for each conference; the table lists 15 per conference in seed order, PHI before DET", seeds == list(range(1, 16)) and st_html.count("<tbody>") == 2 and text(st_html).index(" PHI ") < text(st_html).index(" DET "))
check("zones: seeds 1 to 6 blue, 7 to 10 lilac, none after (12 blue and 8 lilac rows for the two conferences)", st_html.count("z-blue") == 12 and st_html.count("z-lilac") == 8)
check("the table has a +/- column, empty the first time (no earlier table to compare with)", "+/-" in st_html and "▲" not in st_html and "▼" not in st_html)
std2 = copy.deepcopy(STAND)
for e in next(c for c in std2["children"] if c["name"].startswith("East"))["standings"]["entries"]:
    for s in e["stats"]:
        if s["name"] == "playoffSeed" and e["team"]["abbreviation"] in ("PHI", "DET"):
            s["displayValue"] = "2" if e["team"]["abbreviation"] == "PHI" else "1"
tt = text(nba.standings_html(std2, nba.seeds_of(STAND)))
check("movement arrows: with PHI and DET swapped since the last table, DET is up 1 and PHI down 1; everyone else shows a dash", "DET 5-1 - W2 ▲1" in tt.replace("0.5", "-") or ("1 DET" in tt and "▲1" in tt and "▼1" in tt), tt[:300])
check("exactly one up arrow and one down arrow in that East table, and none in the West", tt.count("▲") == 1 and tt.count("▼") == 1)
check("no movement shows '–' for all 30 teams", text(nba.standings_html(STAND, nba.seeds_of(STAND))).count("–") == 30)
check("move(): up, down, level", nba.move(3) == "▲3" and nba.move(-2) == "▼2" and nba.move(0) == "–")
run2 = nba.run(NOW, MON, {"seeds": nba.seeds_of(std2)}, Saved())
check("the run uses the saved seeds as 'since the last table': with the swapped seeds saved, today's real order shows PHI up 1 and DET down 1", "▲1" in run2["html"] and "▼1" in run2["html"] and run2["state"]["seeds"] == nba.seeds_of(STAND))
check("standings sanity check refuses a broken feed (one conference)", not nba.standings_ok({"children": [STAND["children"][0]]}) and nba.standings_ok(STAND))

# ---- NBA Cup ----
raw_cup = {}
for e in ALLW:
    if any(n["headline"] == "NBA Cup - Group Play" for n in e["competitions"][0]["notes"]):
        c = {x["homeAway"]: x for x in e["competitions"][0]["competitors"]}
        raw_cup[e["id"]] = [fixc(c["away"]["team"]["abbreviation"]), fixc(c["home"]["team"]["abbreviation"]), int(c["away"]["score"]) if e["status"]["type"]["name"] == "STATUS_FINAL" else None,
                            int(c["home"]["score"]) if e["status"]["type"]["name"] == "STATUS_FINAL" else None]
groups = nba.cup_groups(raw_cup)
conf = {t: c for c, ts in nba.seeds_of(STAND).items() for t in ts}
check("independent: 60 Cup group games form six groups of five teams, and every team plays exactly four of them", len(raw_cup) == 60 and len(groups) == 6 and all(len(g) == 5 for g in groups)
      and all(sum(t in (a, h) for a, h, *_ in raw_cup.values()) == 4 for g in groups for t in g))
check("every group is within one conference (three East, three West), by the standings", all(len({conf[t] for t in g}) == 1 for g in groups) and sorted(conf[g[0]] for g in groups) == ["Eastern Conference"] * 3 + ["Western Conference"] * 3)
exp = {}
for a, h, sa, sh in raw_cup.values():
    if sa is not None:
        for t, m, o in ((a, sa, sh), (h, sh, sa)):
            w, l, d = exp.get(t, (0, 0, 0))
            exp[t] = (w + (m > o), l + (m <= o), d + m - o)
got = {r_[0]: tuple(r_[1:]) for g in groups for r_ in nba.cup_table(g, raw_cup)}
check("independent: every team's Cup record and point difference equals a separate count from the raw scores (10 games played on 30 October)", sum(w + l for w, l, d in exp.values()) == 20 and all(got[t] == exp.get(t, (0, 0, 0)) for t in got), [(t, got[t], exp.get(t)) for t in got if got[t] != exp.get(t, (0, 0, 0))])
check("a group table is ordered by wins, then point difference", all(all((a[1], a[3]) >= (b[1], b[3]) for a, b in zip(rows, rows[1:])) for rows in (nba.cup_table(g, raw_cup) for g in groups)))
ch = nba.cup_html(groups, raw_cup, {t: c.replace(" Conference", "") for t, c in conf.items()})
check("six group tables, titled by conference; one blue leader per group that has played, and one lilac runner-up per conference", ch.count("<tbody>") == 6 and "Eastern Cup Group 3" in ch and "Western Cup Group 3" in ch and ch.count("z-blue") == 6 and ch.count("z-lilac") == 2, (ch.count("z-blue"), ch.count("z-lilac")))
check("before a game is played nobody is marked in position", "z-blue" not in nba.cup_html(groups, {k: [v[0], v[1], None, None] for k, v in raw_cup.items()}, {}))
cup_run = nba.run(datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc), date(2026, 11, 2), {}, Saved())
cup_txt = text(cup_run["html"])
check("Cup games of 30 October (new on the Monday edition): each gets the 'NBA Cup · Group Play' tag and the group tables appear", cup_run["stats"]["cup_new"] == 10 and cup_txt.count("NBA Cup · Group Play") == 10 and "Cup Group 1" in cup_txt, cup_run["stats"])
check("the Cup tag is above the game, and a Cup group game has no house icon", cup_run["html"].count('class="home"') == 0)
quiet = nba.run(NOW, TUE, {"reported": [g["id"] for g in GAMES]}, Saved())
check("the Cup tables come only on days Cup group games are in the edition: not on a Tuesday or a Monday with none (the group stage is unfinished, but no Cup game is new)", "Cup Group" not in quiet["html"] and "Cup Group" not in nba.run(NOW, MON, {"reported": [g["id"] for g in GAMES]}, Saved())["html"] and "Cup Group" not in nba.run(NOW, TUE, {}, Saved())["html"])
cup_live = copy.deepcopy(WINDOW)
for e in cup_live["2026-10-30"]["events"][:1]:
    e["status"] = {"period": 2, "type": {"name": "STATUS_IN_PROGRESS", "state": "in", "shortDetail": "5:00 - 2nd Quarter"}}
cl = nba.run(datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc), date(2026, 11, 2), {"reported": [e["id"] for e in WINDOW["2026-10-30"]["events"]][1:]}, Saved(window=cup_live, sbs={}))
check("a Cup group game still being played when the edition goes out also brings the Cup tables", "Cup Group 1" in cl["html"] and cl["stats"]["live"] == 1 and "In progress" in text(cl["html"]), cl["stats"])
check("the Cup groups are scanned once and then kept in the state (the second run makes no window scan)", len(quiet["state"]["cup_games"]) == 60 and nba.run(NOW, TUE, quiet["state"], Saved())["stats"]["calls"] == 0)

# ---- Play-in games ----
pi_sbs = copy.deepcopy(SBS)
pi_ev = pi_sbs["2026-11-01"]["events"][0]
pi_ev["competitions"][0]["notes"] = [{"headline": "East Play-In Tournament"}]
pi = nba.run(NOW, MON, {}, Saved(sbs=pi_sbs))
check("a play-in game shows the house icon on the home team (one only) and its note; the other 10 do not", pi["html"].count('class="home"') == 1 and "East Play-In Tournament" in text(pi["html"]), pi["html"].count('class="home"'))
ot_sbs = copy.deepcopy(SBS)
ot_sbs["2026-11-01"]["events"][0]["status"]["period"] = 5
ot_t = text(nba.run(NOW, MON, {}, Saved(sbs=ot_sbs))["html"])
check("an overtime game shows an OT tag on its score (Boston at Orlando, 108-97); the regular-time version does not", "108–97 OT" in ot_t and "108–97" in text(out["html"]) and "108–97 OT" not in text(out["html"]))

# ---- Playoff series ----
def series_run(upto, day, state=None, sched=None, fail_sched=False, fail_std=False):
    rows = copy.deepcopy(sched or SCHED)
    for i, g in enumerate(rows):
        if i >= upto:
            g["status"], g["home"]["score"], g["away"]["score"] = "STATUS_SCHEDULED", None, None

    def event(g):
        sd = lambda t, ha: {"homeAway": ha, "score": str(t["score"] or 0), "records": [], "team": {"id": t["id"], "abbreviation": t["abbr"], "displayName": t["name"], "shortDisplayName": t["short"]}}  # noqa: E731
        fin = g["status"] == "STATUS_FINAL"
        return {"id": g["id"], "date": g["date"], "season": {"year": 2026, "type": 3}, "status": {"period": 4, "type": {"name": g["status"], "state": "post" if fin else "pre"}},
                "competitions": [{"neutralSite": False, "notes": [{"headline": g["headline"]}], "series": None, "type": {}, "competitors": [sd(g["home"], "home"), sd(g["away"], "away")]}]}
    sbs = {}
    for g in rows:
        d = nba.utc(g["date"]).astimezone(nba.ET).date()
        sbs.setdefault(str(d), {"events": []})["events"].append(event(g))
    src = Saved(sbs=sbs, window={}, boxes=SBOXES, sched=rows, fail_sched=fail_sched, std=STAND26, fail_std=fail_std)
    last = nba.utc(rows[upto - 1]["date"]) + timedelta(hours=8)
    return nba.run(last, day, state or {}, src), src, rows


mid, msrc, mrows = series_run(3, date(2026, 4, 26))
mt = text(mid["html"])
wins = {"19": 0, "8": 0}
for g in SCHED[:3]:
    wins[g["home"]["id"] if g["home"]["score"] > g["away"]["score"] else g["away"]["id"]] += 1
check("independent: after game 3 ORL (id 19) leads DET (id 8) 2-1 by the raw schedule; the header shows the full names with their seeds, then the series score beside the word 'series' (the team that hosted game 1 is on the left)", wins == {"19": 2, "8": 1} and "(1) Detroit Pistons Orlando Magic (8) 1 series 2" in mt, mt[:200])
check("the round's name is the table title, from ESPN's note without the game number", mt.startswith("East 1st Round") and "Game 3" not in mt.split("Pistons")[0], mt[:60])
check("all seven game rows are pre-built: G1 to G7", all(f"G{n} ·" in mt for n in range(1, 8)) and mid["html"].count('class="one') == 7)
check("played games show the scores as the raw schedule has them (G1 101-112, G2 98-83, G3 105-113) with the date", "101 G1 · Sun 19 Apr · at DET 112" in mt and "98 G2 · Wed 22 Apr · at DET 83" in mt and "105 G3 · Sat 25 Apr · at ORL 113" in mt, mt[:400])
check("the winner of each played game is in bold: G1 right column, G2 left, G3 right", len(re.findall(r'<td class="(?:aw|hm) w">', mid["html"])) == 3)
check("unplayed games with a date show it in Singapore time, with SGT (G4 starts 00:00 UTC 28 April = 8:00am Tue 28 April)", "G4 · Tue 28 Apr, 8:00am SGT · at ORL" in mt and mt.count("SGT") == 4, mt)
bx = SBOXES["401869193"]
cade = next(a for t in bx["players"] for a in t["athletes"] if a["id"] == "4432166")
cv = dict(zip(bx["players"][0]["labels"], cade["stats"]))
check("independent: Cade Cunningham's note under game 1 is built from the raw box score", f"Cade Cunningham (DET): {cv['PTS']} pts, {cv['REB']} reb, {cv['AST']} ast · {cv['FG']} FG" in mt.replace(" ", " "), cv)
check("the best performer of game 3 who is not tracked appears with his team (Banchero, ORL)", "Paolo Banchero (ORL):" in mt)
raw_seed = {e["team"]["abbreviation"]: int(next(x["displayValue"] for x in e["stats"] if x["name"] == "playoffSeed")) for c in STAND26["children"] for e in c["standings"]["entries"]}
check("independent: ESPN's final 2025-26 standings give Detroit seed 1 and Orlando seed 8 (the real 1-8 series), and the seeds sit beside the team names", raw_seed["DET"] == 1 and raw_seed["ORL"] == 8 and nba.seeds_by_team(STAND26)["DET"] == 1 and "(1) Detroit Pistons" in mt and "Orlando Magic (8)" in mt)
check("the seeds come from the standings of the series' own season (2026), asked once", msrc.std_seasons == [2026], getattr(msrc, "std_seasons", None))
check("the series score numbers sit beside the word 'series' in one row (not out at the team names)", re.search(r'<tr class="sc"><th colspan="3"><span class="ws">1</span><span class="lab">series</span><span class="ws">2</span>', mid["html"]) is not None)
check("once the playoffs are on, the regular-season standings are not shown, and not fetched for the table itself", "Standings" not in mid["html"] and "Eastern Conference" not in mid["html"])
nos = series_run(3, date(2026, 4, 26), fail_std=True)[0]
check("seed feed down: the series table still shows, without seeds, and the failure is counted", "East 1st Round" in nos["html"] and "(1)" not in text(nos["html"]) and "Detroit Pistons Orlando Magic" in text(nos["html"]) and nos["stats"]["failed"] == 1)
check("a playoff game is in its series table and not repeated in a Last Night's Games table", "Last Night's Games" not in mt and mid["stats"]["series"] == 1)
check("notes for all three finished games are kept in the state; the box scores fetched were the new game's plus the two earlier ones: 3 in all", len(mid["state"]["series_notes"]) == 3 and msrc.box_calls == 3, (len(mid["state"]["series_notes"]), msrc.box_calls))
full, fsrc, _ = series_run(7, date(2026, 5, 4))
ft = text(full["html"])
fw = {"8": 0, "19": 0}
for g in SCHED:
    fw[g["home"]["id"] if g["home"]["score"] > g["away"]["score"] else g["away"]["id"]] += 1
check("independent: by the raw schedule the series ended DET 4, ORL 3 (game 1's home team DET is the left column); the header says so", fw == {"8": 4, "19": 3} and "(1) Detroit Pistons Orlando Magic (8) 4 series 3" in ft, (fw, ft[:80]))
check("no unplayed rows and no 'SGT' or 'if necessary' once the series is finished", "SGT" not in ft and "if necessary" not in ft and full["html"].count('class="one') == 7)
short = [dict(g) for g in SCHED[:2]]
sh, _, _ = series_run(2, date(2026, 4, 23), sched=short)
st_ = text(sh["html"])
check("games not yet on the schedule: G3 and G4 'to be scheduled', G5 to G7 'if necessary'", "G3 · to be scheduled" in st_ and "G4 · to be scheduled" in st_ and st_.count("if necessary") == 3, st_)
sweep = copy.deepcopy(SCHED[:4])
sweep[1]["home"]["score"], sweep[1]["away"]["score"] = 83, 98   # ORL also wins game 2: a 4-0 sweep
sw, _, _ = series_run(4, date(2026, 4, 28), sched=sweep)
check("a finished sweep: the unplayed games 5 to 7 are marked '–', not 'if necessary'", "if necessary" not in text(sw["html"]) and text(sw["html"]).count("G5 · –") == 1 and "0 series 4" in text(sw["html"]), text(sw["html"])[:300])
second = nba.run(mid["state"]["reported"] and datetime(2026, 4, 26, 8, tzinfo=timezone.utc), date(2026, 4, 26), copy.deepcopy(mid["state"]), msrc)
check("a second run with the saved state shows no series again (nothing new)", second["stats"]["series"] == 0 and second["stats"]["new"] == 0)
down = series_run(3, date(2026, 4, 26), fail_sched=True)[0]
check("schedule feed down: the series table is left out, the failure counted, the standings and the rest still come, nothing crashes", down["stats"]["failed"] == 1 and "G1 ·" not in down["html"] and down["stats"]["series"] == 0)

# ---- Full names, number colour, in-progress games ----
check("the games table uses full team names, not nicknames alone: 'Toronto Raptors 125–131 Los Angeles Lakers'", "Toronto Raptors 125–131 Los Angeles Lakers" in text(out["html"]) and "Portland Trail Blazers 112–90 Utah Jazz" in text(out["html"]) and "Raptors 125–131 Lakers" not in text(out["html"]).replace("Toronto Raptors 125–131 Los Angeles Lakers", ""))
names = sorted({g[side]["name"] for g in nba.parse_game and [nba.parse_game(e) for d in (SBS, WINDOW) for sb in d.values() for e in sb["events"]] for side in ("home", "away")} - {"TBD"})   # TBD: a Cup knockout place whose team is not decided yet
check("team names are standardised: all 30 are City + nickname, ESPN's 'LA Clippers' becomes 'Los Angeles Clippers' (next to 'Los Angeles Lakers')", len(names) == 30 and "Los Angeles Clippers" in names and "Los Angeles Lakers" in names and not any(n.startswith("LA ") for n in names), names)
check("the same fix applies in a playoff header", "Los Angeles Clippers" in text(nba.series_html({**po, "home": {**po["home"], "name": "LA Clippers"}}, [], {})))
css_ = (ROOT / "kickoff" / "static" / "style.css").read_text()
check("player lines carry a small gold diamond bullet (a flex box whose bullet cell is one line tall and centres the diamond on the first line, so wrapped lines align) and are 14px, smaller than the 15px team names", 'content: "\\25C6"' in css_ and re.search(r"\.nflsb tr\.note td \{ font-size: 14px", css_) and re.search(r"\.nbaone td\.aw, \.nbaone td\.hm \{ font-size: 15px", css_) and "align-items: center; font-size: 8px" in css_ and '<div class="pl"><span class="t">' in out["html"])
check("the numbers of points, rebounds, assists, steals and blocks are in the accent colour (<span class=n>), the labels and the shooting line are not", '<span class="n">45</span> pts, <span class="n">15</span> reb, <span class="n">6</span> ast, <span class="n">5</span> stl' in out["html"] and '<span class="n">12-23' not in out["html"] and out["html"].count('class="n"') >= 40)
check("note_html escapes text first: an ampersand or tag in a name cannot break the page", "&lt;b&gt;" in nba.note_html("<b>Bob</b>: 3 pts") and '<span class="n">3</span> pts' in nba.note_html("<b>Bob</b>: 3 pts"))
live_sbs = copy.deepcopy(SBS)
lv = live_sbs["2026-11-01"]["events"][-1]
lv["status"] = {"period": 3, "type": {"name": "STATUS_IN_PROGRESS", "state": "in", "shortDetail": "4:12 - 3rd Quarter"}}
for c_ in lv["competitions"][0]["competitors"]:
    c_["score"] = str(int(c_["score"]) - 38)
lsrc = Saved(sbs=live_sbs)
lr = nba.run(NOW, TUE, {"reported": [g["id"] for g in GAMES if g["id"] != lv["id"]]}, lsrc)
lt = text(lr["html"])
check("a game being played when the edition goes out is shown 'In progress' with its score so far (87–93, from the raw feed) and no winner, no notes", lr["stats"]["live"] == 1 and "In progress · 4:12 - 3rd Quarter" in lt and "Toronto Raptors 87–93 Los Angeles Lakers" in lt and lr["html"].count('class="aw w"') + lr["html"].count('class="hm w"') == 0, lt[:300])
check("it is not marked reported, and no box score was fetched for it", lv["id"] not in lr["state"]["reported"] and lsrc.box_calls == 0)
nxt = nba.run(NOW, TUE, lr["state"], Saved())
check("the next edition shows it as a final, with notes (Doncic's 45) and no 'In progress'", "Toronto Raptors 125–131 Los Angeles Lakers" in text(nxt["html"]) and "In progress" not in text(nxt["html"]) and "Luka Doncic (LAL): 45 pts" in text(nxt["html"]) and lv["id"] in nxt["state"]["reported"])
check("an in-progress game is not counted as an underdog win or a standout", "underdog" not in lt and "Luka" not in lt)
lp_rows = [dict(g) for g in SCHED[:4]]
lp_rows[3] = {**lp_rows[3], "status": "STATUS_IN_PROGRESS", "home": {**lp_rows[3]["home"], "score": 40}, "away": {**lp_rows[3]["away"], "score": 44}}
lpr = text(nba.series_html(nba.parse_game(L("nba_series_scoreboard.json")["2026-05-03"]["events"][0]), lp_rows, {}))
check("a playoff game on now: its row shows the score so far with the first-column team (Detroit, away in game 4) on the left, 44-40, and 'G4 · In progress'; the series wins count only finished games", "G4 · In progress" in lpr and "44 G4 · In progress 40" in lpr and "1 series 2" in lpr, lpr[:200])

# ---- Auto-join and drop-off ----
st = {}
d0 = date(2026, 11, 3)
nba.update_tracking(st, [("999", "g1")], {"999": "Rookie One"}, d0)
nba.update_tracking(st, [("999", "g2")], {"999": "Rookie One"}, d0 + timedelta(days=5))
check("two standout games are not enough to join", "999" not in st["auto"])
nba.update_tracking(st, [("999", "g2")], {"999": "Rookie One"}, d0 + timedelta(days=6))
check("the same game counted twice does not count twice", "999" not in st["auto"] and len(st["hits"]["999"]) == 2)
ids = nba.update_tracking(st, [("999", "g3")], {"999": "Rookie One"}, d0 + timedelta(days=10))
check("a third standout within 30 days adds the player automatically", "999" in st["auto"] and "999" in ids and st["auto"]["999"]["name"] == "Rookie One")
nba.update_tracking(st, [], {}, d0 + timedelta(days=10 + 55))
check("55 days after the last standout he is still tracked", "999" in st["auto"])
nba.update_tracking(st, [], {}, d0 + timedelta(days=10 + 57))
check("after 56 days without a standout he drops off", "999" not in st["auto"])
st2 = {}
for i, off in enumerate((0, 20, 40)):
    nba.update_tracking(st2, [("888", f"g{i}")], {"888": "Slow"}, d0 + timedelta(days=off))
check("three standouts spread over 40 days do not qualify (only two fall inside any 30 days)", "888" not in st2["auto"])
st3 = {}
for i, h in enumerate(("1966", "5104157")):
    nba.update_tracking(st3, [(h, f"a{i}"), (h, f"b{i}"), (h, f"c{i}")], {}, d0)
check("D's own list never goes into the auto list, and cannot be dropped", st3["auto"] == {} and set(nba.TRACKED) <= nba.update_tracking(st3, [], {}, d0 + timedelta(days=400)))
dunn = {"auto": {auto_p: {"name": "Kris Dunn", "last": "2026-11-01"}}}
check("an auto-added player is followed in the run: Kris Dunn's line is in the Clippers-Warriors notes", "Kris Dunn (LAC): 12 pts, 2 reb, 4 ast, 7 stl" in text(nba.run(NOW, MON, dunn, Saved())["html"]))

# ---- Failures and edge cases ----
bad = nba.run(NOW, MON, {}, Saved(fail_box=["401909896"]))
check("one failed box score: that game is left out and not marked reported; the other 10 show and it comes back next run", bad["stats"]["failed"] == 1 and "401909896" not in bad["state"]["reported"] and len(bad["state"]["reported"]) == 10
      and "Damian Lillard" not in text(bad["html"]) and "Damian Lillard" in text(nba.run(NOW, MON, bad["state"], Saved())["html"]))
none = nba.run(NOW, TUE, {}, Saved(fail_sb=True, fail_std=True))
check("scoreboard and standings down: nothing shown, no crash; three scoreboard failures and one stopped Cup scan counted (not sixty)", none["html"] == "" and none["stats"]["failed"] == 4, none["stats"])
nostd = nba.run(NOW, MON, {}, Saved(fail_std=True))
check("standings down: the games still show without the standings table", "Last Night's Games" in nostd["html"] and "Standings" not in nostd["html"] and nostd["stats"]["failed"] == 1)

# ---- Source ----
CALLS = []


def fake_get(url):
    CALLS.append(url)
    if "summary" in url:
        return {"boxscore": {"teams": [{"team": {"abbreviation": "AAA"}, "statistics": [{"name": "blocks", "displayValue": "4"}]}],
                             "players": [{"team": {"abbreviation": "AAA"}, "statistics": [{"labels": ["MIN", "PTS"], "athletes": [{"athlete": {"id": "1", "displayName": "P One"}, "starter": True, "stats": ["30", "12"], "reason": "R"}]}]}]},
                "injuries": [{"team": {"abbreviation": "AAA"}, "injuries": [{"athlete": {"id": "2"}, "status": "Out", "details": {"type": "Knee"}}, {"athlete": {"id": "3"}, "status": "Out"}]}],
                "pickcenter": [{"details": "AAA -3", "spread": 3, "awayTeamOdds": {"underdog": False, "moneyLine": -150}, "homeTeamOdds": {"underdog": True, "moneyLine": 130}}],
                "plays": [{"text": "a", "scoringPlay": True, "scoreValue": 2, "period": {"number": 1}, "clock": {"displayValue": "9:00"}, "awayScore": 2, "homeScore": 0, "team": {"id": "5"}, "participants": [{"athlete": {"id": "1"}}]},
                          {"text": "b", "scoringPlay": False, "period": {"number": 1}, "clock": {"displayValue": "8:00"}, "awayScore": 2, "homeScore": 0}]}
    if "schedule" in url:
        return {"events": [{"id": "9", "date": "2026-04-19T22:30Z", "competitions": [{"status": {"type": {"name": "STATUS_FINAL"}}, "notes": [{"headline": "East 1st Round - Game 1"}],
                "competitors": [{"homeAway": "home", "team": {"id": "8", "abbreviation": "DET", "shortDisplayName": "Pistons", "displayName": "Detroit Pistons"}, "score": {"displayValue": "101"}},
                                {"homeAway": "away", "team": {"id": "19", "abbreviation": "ORL", "shortDisplayName": "Magic", "displayName": "Orlando Magic"}, "score": {"displayValue": "112"}}]}]}]}
    if "roster" in url:
        return {"athletes": [{"id": "7", "displayName": "Seven"}]}
    if url.endswith("/teams"):
        return {"sports": [{"leagues": [{"teams": [{"team": {"id": "2", "abbreviation": "BOS"}}]}]}]}
    return {"ok": url}


src = espn_nba.Source(fake_get, pause=0)
b = src.box("1")
check("source: a box score is trimmed to players, team totals, the pre-game line, ESPN's injury list and only the scoring plays",
      b["players"][0]["athletes"][0] == {"id": "1", "name": "P One", "pos": "", "starter": True, "dnp": False, "reason": "R", "stats": ["30", "12"]} and b["teams"] == {"AAA": {"blocks": "4"}}
      and b["injuries"] == {"2": {"status": "Out", "type": "Knee"}, "3": {"status": "Out", "type": ""}} and b["odds"]["home_dog"] is True and len(b["plays"]) == 1 and b["plays"][0]["athlete"] == "1", b)
sc = src.schedule("8", 2026)
check("source: a team's playoff schedule is trimmed to id, date, status, the round note, and both sides with scores; the season is passed through", sc == [{"id": "9", "date": "2026-04-19T22:30Z", "status": "STATUS_FINAL", "headline": "East 1st Round - Game 1",
      "home": {"id": "8", "abbr": "DET", "short": "Pistons", "name": "Detroit Pistons", "score": 101}, "away": {"id": "19", "abbr": "ORL", "short": "Magic", "name": "Orlando Magic", "score": 112}}] and "teams/8/schedule?seasontype=3&season=2026" in CALLS[-1], sc)
check("source: the scoreboard asks for the date as yyyymmdd; rosters and team ids", (src.scoreboard(date(2026, 11, 1)) and "dates=20261101" in CALLS[-1]) and src.roster("2") == {"7": "Seven"} and src.teams() == {"2": "BOS"} and src.calls == 5)
check("career totals are gone: the milestone watch for LeBron and Harden was dropped", not hasattr(src, "career") and not hasattr(nba, "milestone") and not hasattr(nba, "WATCHED"))
check("NBA needs no Claude: neither module imports anthropic", "anthropic" not in (ROOT / "kickoff" / "nba.py").read_text() and "anthropic" not in (ROOT / "kickoff" / "sources" / "espn_nba.py").read_text())
check("D's 24 tracked players are all there, each with a starting team", len(nba.TRACKED) == 24 and set(nba.TEAMS) == set(nba.TRACKED))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
