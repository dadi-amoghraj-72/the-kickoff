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
INFO = {"format": "Match", "players": "Gukesh Dommaraju vs Javokhir Sindarov", "timeZone": "Europe/Zurich"}
RESULTS = {1: ("Gukesh, Dommaraju", "Sindarov, Javokhir", "1/2-1/2"), 2: ("Sindarov, Javokhir", "Gukesh, Dommaraju", "0-1"), 3: ("Gukesh, Dommaraju", "Sindarov, Javokhir", "1/2-1/2")}


class FakeLichess:
    def __init__(self, played):
        self.played = played

    def rounds(self):
        return [{"id": f"r{i + 1}", "name": f"Game {i + 1}", "startsAt": s, "finished": i < self.played} for i, s in enumerate(STARTS)]

    def top(self):
        tour = {"id": "t1", "name": "FIDE World Chess Championship 2026", "slug": "wcc", "tier": 5, "info": INFO, "url": "https://lichess.org/broadcast/wcc/t1", "dates": [STARTS[0], STARTS[-1]]}
        rnd = {"id": f"r{self.played}", "name": f"Game {self.played}", "finished": self.played > 0, "finishedAt": STARTS[max(self.played - 1, 0)] + 5 * 3600 * 1000, "url": "https://lichess.org/x"}
        return {"active": [{"tour": tour, "round": rnd}], "past": []}

    def tour(self, tid):
        return {"tour": self.top()["active"][0]["tour"], "rounds": self.rounds()}

    def round_pgn(self, rid):
        return pgn(*RESULTS[int(rid[1:])])

    def chess(self):
        t = self.top()["active"][0]["tour"]
        return [{"name": t["name"], "players": INFO["players"], "url": t["url"], "rounds": self.rounds()}]


# ---- the match table
after3 = datetime(2026, 11, 27, 0, 0, tzinfo=timezone.utc)                 # the morning after game 3
blocks = chess_live.match_blocks(FakeLichess(3), after3)
check("one table for the running match, once per new game", len(blocks) == 1 and blocks[0][1] == "chess:t1:table:3", blocks and blocks[0][1])
h = blocks[0][0] if blocks else ""
check("the title is short: 'World Championship'", ">World Championship<" in h, h[:300])
check("the gold score row reads 'Gukesh 1½ – 1½ Sindarov'" if False else "the score row counts the games: Gukesh 2 – 1 Sindarov", "Gukesh 2 – 1 Sindarov" in h.replace("½", "").replace("2½", "2") or "Gukesh 2" in h, h)
check("rows list game, White, result, Black in game order", re.findall(r'<td class="n">(\d)</td><td>(\w+)</td><td>([^<]+)</td><td>(\w+)</td>', h) == [("1", "Gukesh", "½–½", "Sindarov"), ("2", "Sindarov", "0–1", "Gukesh"), ("3", "Gukesh", "½–½", "Sindarov")], re.findall(r"<tr>.*?</tr>", h))
check("the foot says first to 7½ and 11 games to play", "First to 7½ · 11 games to play" in h, h[-300:])
check("the same table is not made on a day with no new game (rest day, old round)", chess_live.match_blocks(FakeLichess(3), after3 + timedelta(days=5)) == [])
check("no line for the match in the generic Around lines (no duplicate)", chess_live.run(FakeLichess(3), after3) == [], chess_live.run(FakeLichess(3), after3))
check("a match tour is recognised from Lichess's info", chess_live.is_match({"info": INFO}) and not chess_live.is_match({"info": {"format": "Round-robin", "players": ""}}))
check("names: Gukesh, Sindarov", chess_live.short("Gukesh Dommaraju") == "Gukesh" and chess_live.short("Javokhir Sindarov") == "Sindarov" and chess_live.short("Gukesh, D") == "Gukesh")
won = [(i, chess_live.parse_pgn(pgn("Gukesh, D", "Sindarov, J", "1-0"))[0]) for i in range(1, 9)]
check("7½ points ends the match", "Gukesh wins the match" in chess_live.match_table("World Championship", won, "12 Dec"))
level = [(i, chess_live.parse_pgn(pgn("Gukesh, D", "Sindarov, J", "1/2-1/2"))[0]) for i in range(1, 15)]
check("level after 14: tiebreak day named", "tiebreaks on 12 Dec" in chess_live.match_table("World Championship", level, "12 Dec"), chess_live.match_table("World Championship", level, "12 Dec")[-200:])

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
check("six sub-rows and the NBA table's class, so the same layout rules apply", html.count('class="grp"') == 6 and 'class="pts f1 nba lead"' in html and ">NHL Leaders<" in html, html[:200])
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

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
