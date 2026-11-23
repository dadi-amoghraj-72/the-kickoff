"""Tests for D's 23 Nov 2026 request: the world championship match table (Other Sports), the match in On Today and Don't Miss and only its NEXT game in the week ahead,
the weekly NHL leaders table (Saturday) and the NHL rail icon. Made-up games in Lichess's real layout.
Run: .venv/bin/python scripts/test_morning11.py"""
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import chess_live, fixtures, nhl, ontoday, order  # noqa: E402
from kickoff.sources import espn_nhl  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:400]}"))
    results.append(ok)


def ms(y, m, d, h, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)


def pgn(white, black, result):
    return f'[Event "FIDE World Chess Championship 2026"]\n[White "{white}"]\n[Black "{black}"]\n[Result "{result}"]\n[WhiteElo "2780"]\n[BlackElo "2760"]\n\n1. e4 e5 {result}\n'


# Game 1 Tue 24 Nov 22:00 SGT = 14:00 UTC; rounds every day except the rest days (Fri 27 Nov)
STARTS = [ms(2026, 11, 24, 14), ms(2026, 11, 25, 14), ms(2026, 11, 26, 14), ms(2026, 11, 28, 14), ms(2026, 11, 29, 14)]
INFO = {"format": "Match", "players": "Gukesh Dommaraju vs Javokhir Sindarov", "timeZone": "Europe/Zurich", "location": "Geneva, Switzerland"}
# Lichess's real layout: the pairing is listed before the game ("Gukesh D", result '*'); Sindarov has White in game 1
PAIRS = {1: ("Sindarov, Javokhir", "Gukesh D"), 2: ("Gukesh D", "Sindarov, Javokhir"), 3: ("Sindarov, Javokhir", "Gukesh D"), 4: ("Gukesh D", "Sindarov, Javokhir"), 5: ("Sindarov, Javokhir", "Gukesh D")}
RESULTS = {1: "1/2-1/2", 2: "1-0", 3: "1/2-1/2"}          # game 2: Gukesh (White) wins


class FakeLichess:
    def __init__(self, played):
        self.played = played

    def rounds(self):
        return [({"id": f"r{i + 1}", "name": f"Game {i + 1}", "startsAt": s, "finished": True, "finishedAt": s + 5 * 3600 * 1000} if i < self.played
                 else {"id": f"r{i + 1}", "name": f"Game {i + 1}", "startsAt": s}) for i, s in enumerate(STARTS)]

    def top(self):
        tour = {"id": "t1", "name": "FIDE World Chess Championship 2026", "slug": "wcc", "tier": 5, "info": INFO, "url": "https://lichess.org/broadcast/wcc/t1", "dates": [STARTS[0], STARTS[-1]]}
        nxt = min(self.played, len(STARTS) - 1)          # Lichess lists the CURRENT round (the next one), never the one just played
        rnd = {"id": f"r{nxt + 1}", "name": f"Game {nxt + 1}", "startsAt": STARTS[nxt], "url": "https://lichess.org/x"}
        return {"active": [{"tour": tour, "round": rnd}], "past": []}

    def tour(self, tid):
        return {"tour": FakeLichess.top(self)["active"][0]["tour"], "rounds": self.rounds()}

    def round_pgn(self, rid):
        n = int(rid[1:])
        return pgn(*PAIRS[n], RESULTS[n] if n <= self.played else "*")

    def chess(self):
        t = self.top()["active"][0]["tour"]
        return [{"name": t["name"], "players": INFO["players"], "url": t["url"], "rounds": self.rounds()}]


# ---- the match table (D, 2026-11-24: every game, date, fixed columns, colours, venue)
after3 = datetime(2026, 11, 26, 23, 30, tzinfo=timezone.utc)                 # 7:30 SGT on 27 Nov, the morning after game 3 (a rest day)
blocks = chess_live.match_blocks(FakeLichess(3), after3)
check("one table for the running match, every edition (id carries the day)", len(blocks) == 1 and blocks[0][1] == "chess:t1:table:2026-11-27", blocks and blocks[0][1])
h = blocks[0][0] if blocks else ""
check("the title and a grey line with the venue and dates (the fake has 5 games, so it ends 30 Nov)", ">World Championship<span class=prog>Geneva · 24 Nov – 30 Nov</span>" in h, h[:400])
check("the gold score row: Gukesh 2 – 1 Sindarov", "Gukesh 2 – 1 Sindarov" in h, h)
rows = re.findall(r'<tr><td class="cm-no">(\w+)</td><td class="cm-dt">([^<]*)</td><td class="cm-nm( cm-win)?">(\w+)</td><td class="cm-cl">\((\w)\)</td><td class="cm-sc([^"]*)">([^<]+)</td><td class="cm-nm( cm-win)?">(\w+)</td><td class="cm-cl">\((\w)\)</td></tr>', h)
check("every game is listed, played or not (5 here)", len(rows) == 5, rows)
check("Gukesh is always left, Sindarov always right", all(x[3] == "Gukesh" and x[8] == "Sindarov" for x in rows), rows)
check("colours in their own column: game 1 Gukesh (B) v Sindarov (W), game 2 Gukesh (W)", rows[0][4] == "B" and rows[0][9] == "W" and rows[1][4] == "W", rows[:2])
check("the score is read from Gukesh's side and his win is gold", rows[1][6] == "1–0" and rows[1][2] == " cm-win" and rows[1][7] == "", rows[1])
check("draws are ½–½ with no gold", rows[0][6] == "½–½" and rows[0][2] == rows[0][7] == "", rows[0])
check("the dates are the SGT dates", [x[1] for x in rows] == ["24 Nov", "25 Nov", "26 Nov", "28 Nov", "29 Nov"], [x[1] for x in rows])
check("games still to come show a grey dash (next game more than a day away: rest day)", rows[3][5] == " cm-up" and rows[3][6] == "–", rows[3])
check("no class the match board colours (.pl, .r, .y, .g): Sindarov was red", not re.search(r'class="[^"]*\b(pl|r|y|g|l|w)\b', h), re.findall(r'class="[^"]*"', h)[:20])
morning1 = datetime(2026, 11, 23, 23, 30, tzinfo=timezone.utc)
h1 = chess_live.match_blocks(FakeLichess(0), morning1)[0][0]
check("before game 1 no time in the score column (it is in On Today)", "cm-next" not in h1, h1)
h2 = chess_live.match_blocks(FakeLichess(1), datetime(2026, 11, 24, 23, 30, tzinfo=timezone.utc))[0][0]
check("once a game is played, the next game shows its time (10pm) in gold", '<td class="cm-sc cm-next">10pm</td>' in h2 and h2.count("cm-next") == 1, h2)
check("before game 1 the score is 0 – 0 and 14 games to play", "Gukesh 0 – 0 Sindarov" in h1 and "First to 7½ · 14 games to play" in h1, h1[-300:])
check("the foot says first to 7½ and 11 games to play", "First to 7½ · 11 games to play" in h, h[-300:])
check("nothing two days before the first game", chess_live.match_blocks(FakeLichess(0), morning1 - timedelta(days=2)) == [])
check("no line for the match in the generic Around lines (no duplicate)", chess_live.run(FakeLichess(3), after3) == [], chess_live.run(FakeLichess(3), after3))
won = [{"label": str(i), "tb": False, "starts": STARTS[0] + i * 86400000, "white": "Gukesh D", "black": "Sindarov, Javokhir", "result": "1-0"} for i in range(1, 9)]
check("7½ points ends the match", "Gukesh wins the match" in chess_live.match_table("World Championship", "", won, morning1))
level = [{"label": str(i), "tb": False, "starts": STARTS[0] + i * 86400000, "white": "Gukesh D", "black": "Sindarov, Javokhir", "result": "1/2-1/2"} for i in range(1, 15)]
lt = chess_live.match_table("World Championship", "", level, morning1)
check("level after 14: tiebreaks next, never a negative count", "tiebreaks next" in lt and "-1" not in lt, lt[-200:])
check("halves print as ½ and 2½", chess_live._points(0.5) == "½" and chess_live._points(2.5) == "2½" and chess_live._points(3.0) == "3" and chess_live._points(0.0) == "0")
check("a match whose tour moved to Lichess's past list still gets its table", len(chess_live.match_blocks(type("S", (FakeLichess,), {"top": lambda self: {"active": [], "past": {"currentPageResults": [FakeLichess.top(self)["active"][0]]}}})(3), after3)) == 1)
check("a match tour is recognised from Lichess's info", chess_live.is_match({"info": INFO}) and not chess_live.is_match({"info": {"format": "Round-robin", "players": ""}}))
check("names: Gukesh, Sindarov", chess_live.short("Gukesh Dommaraju") == "Gukesh" and chess_live.short("Javokhir Sindarov") == "Sindarov" and chess_live.short("Gukesh, D") == "Gukesh")

# ---- On Today and the week ahead
now = datetime(2026, 11, 23, 23, 30, tzinfo=timezone.utc)                    # 7:30 SGT, Tue 24 Nov
end = ontoday.day_end(date(2026, 11, 24))
got = fixtures.chess(FakeLichess(0), now, end, 1)
check("On Today has game 1 at 10pm", len(got) == 1 and ontoday.clock(got[0]["when"]) == "10pm" and "Game 1" in got[0]["text"] and "Gukesh v Sindarov" in got[0]["text"], got)
check("it is a Don't Miss game", got and ontoday.is_big(got[0]), got)
week = fixtures.chess(FakeLichess(0), end, end + timedelta(days=6), 0, True)
check("the week ahead lists only the next game, not all five", len(week) == 1 and "Game 2" in week[0]["text"], week)
week2 = fixtures.chess(FakeLichess(2), datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc), datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc) + timedelta(days=6), 0, True)
check("when the next game changes, the line changes (Game 2 played: Game 3 is next)", len(week2) == 1 and "Game 3" in week2[0]["text"], week2)
check("a finished game is never listed", all("Game 1" not in f["text"] for f in fixtures.chess(FakeLichess(1), now, end + timedelta(days=9), 1)))
check("a source without chess adds nothing and does not fail", fixtures.chess(object(), now, end, 1) == [])
check("the week-ahead picker keeps the chess line", ontoday.watch_pick(week) == week, ontoday.watch_pick(week))

# ---- NHL leaders
def jcat(rows):
    return {"categories": [{"name": "general", "names": ["games", "plusMinus", "timeOnIcePerGame", "shifts", "production", "wins", "losses", "timeOnIce"]},
                           {"name": "offensive", "names": ["goals", "assists", "points"]}, {"name": "defensive", "names": ["overtimeLosses", "avgGoalsAgainst", "shotsAgainst", "goalsAgainst", "saves", "savePct", "shootoutShotsAgainst", "shootoutSaves", "shootoutSavePct", "shutouts"]}],
            "athletes": [{"athlete": {"displayName": n, "teamShortName": t}, "categories": [{"name": "general", "values": g}, {"name": "offensive", "values": o}, {"name": "defensive", "values": d}]} for n, t, g, o, d in rows]}


SK = [("Connor McDavid", "EDM", [26, 26, 1422, 0, 0, 0, 0, 0], [13, 45, 58], [0] * 10), ("Leon Draisaitl", "EDM", [26, 23, 1320, 0, 0, 0, 0, 0], [23, 24, 47], [0] * 10), ("Kirill Kaprizov", "MIN", [25, 25, 1290, 0, 0, 0, 0, 0], [18, 27, 45], [0] * 10)]
GK = [("Linus Ullmark", "OTT", [12, 0, 3460, 0, 0, 7, 0, 0], [None, None, None], [0, 1.474, 270, 18, 252, 0.935, 0, 0, 0, 2]), ("Igor Shesterkin", "NYR", [5, 0, 3212, 0, 0, 3, 0, 0], [None, None, None], [0, 1.793, 109, 0, 0, 0.921, 0, 0, 0, 1])]
urls = []


def fake_get(url):
    urls.append(url)
    return jcat(GK if "goalies" in url else SK)


src = espn_nhl.Source(get_json=fake_get, pause=0)
by = {lab: src.leaders(cat, sort) for lab, cat, sort, _ in nhl.LEADER_STATS}
check("skater values are read by the names ESPN lists (goals, assists, points)", [x["value"] for x in by["Goals"]][:1] == [13.0] and by["Assists"][0]["value"] == 45.0 and by["Points"][0]["value"] == 58.0, by["Points"])
check("goalies: wins, save % and shutouts", by["Goalie wins"][0]["value"] == 7.0 and abs(by["Save percentage"][0]["value"] - 0.935) < 1e-9 and by["Shutouts"][0]["value"] == 2.0, by["Save percentage"])
check("a missing value (a skater stat on a goalie) is skipped, not a crash", all(x["value"] is not None for x in src.leaders("goalies", "offensive.goals")))
html = nhl.leaders_html(by)
check("six sub-rows and the NBA table's class, so the same layout rules apply", html.count('class="grp"') == 6 and 'class="pts f1 nba lead nhl"' in html and ">NHL Leaders<" in html, html[:200])
check("each leader is gold, names are 'C. McDavid'", html.count('class="p1"') == 6 and "C. McDavid" in html, html[:900])
check("save percentage prints as .935 and counts as whole numbers", ">.935<" in html and ">58<" in html and ">45<" in html, html)
check("the team is shown in its own column", "<td>EDM</td>" in html and "<td>OTT</td>" in html)
sat, fri = date(2026, 11, 28), date(2026, 11, 27)
check("it comes on Saturday only", nhl.run(None, sat, {}, src)["html"] != "" and nhl.run(None, fri, {}, src)["html"] == "")
check("no table in the summer", nhl.run(None, date(2027, 7, 3), {}, src)["html"] == "")


class Dead:
    calls = 0

    def leaders(self, *a):
        raise RuntimeError("down")


try:
    nhl.run(None, sat, {}, Dead())
    check("every stat failing is an error (the section says no data, loudly)", False)
except RuntimeError:
    check("every stat failing is an error (the section says no data, loudly)", True)
check("the NHL has its own place in the order", ["nhl"] in order.GROUPS)
secs = order.assemble({"nhl": {"title": "NHL", "html": "<p>x</p>"}, "nba": {"title": "NBA", "html": "<p>y</p>"}})
check("NHL comes after the NBA", [s["id"] for s in secs] == ["nba", "nhl"], secs)
js = (ROOT / "kickoff/static/rail-icons.js").read_text()
check("a puck-and-stick icon is on the rail for the NHL section", "hockey: {" in js and 'nhl: "hockey"' in js)

crowd = [fixtures.fixture("football", "PL", f"Premier League: A{i} v B{i}", now + timedelta(hours=i + 1), 40 + i, True, "knockout") for i in range(4)]
check("Don't Miss keeps the chess game even when four bigger games compete", any(f["sport"] == "chess" for f in ontoday.dont_miss(crowd + got)) and len(ontoday.dont_miss(crowd + got)) == 3)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
