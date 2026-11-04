"""Tests for The Big Stuff: the scoring table, the story converters, the picking rules and the lead sport. Run: .venv/bin/python scripts/test_bigstuff.py"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import bigstuff, daily, events, importance, nba, order  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


def st(sport, score, text=None, **kw):
    return {"kind": "result", "sport": sport, "comp": sport, "text": text or f"{sport} {score}", "score": score, "mine": kw.pop("mine", False), "stage": kw.pop("stage", "regular"), **kw}


SUN, MON, TUE, WED = 6, 0, 1, 2

# ---- the table -----------------------------------------------------------------------------------
reg = lambda sport, wd, **kw: importance.story_score(sport, "regular", weekday=wd, **kw)  # noqa: E731
check("a regular NBA game ranks below a regular NFL game, on every morning", reg("nba", WED) < reg("nfl", WED) and reg("nba", MON) < reg("nfl", MON))
check("on a heavy morning (Sunday, Monday) a plain NBA, MLB or cricket game is cut harder than on Wednesday",
      all(reg(s, MON) < reg(s, WED) and reg(s, SUN) < reg(s, WED) for s in ("nba", "mlb", "cricket")))
check("India's (D's) cricket game is not downshifted: a plain mine game keeps its full score on Monday",
      reg("cricket", MON, mine=True) == importance.STAGE["regular"] + importance.MINE)
check("playoff games all count: an NBA playoff game on a Monday outranks an ordinary Monday football league game with a listed club",
      importance.story_score("nba", "playoff", weekday=MON) > importance.story_score("football", "regular", listed=True, weekday=MON))
check("a crazy regular-season game (wow) climbs back above the cut line even for a downshifted sport", importance.story_score("nba", "regular", wow=True, weekday=MON) >= importance.MIN_SCORE)
check("Virat Kohli batting outranks any other regular cricket story, and even India without him",
      importance.story_score("cricket", "regular", mine=True, kohli=True) > importance.story_score("cricket", "regular", mine=True))
check("D's own NBA team is also downshifted on a heavy morning (his India, Sunrisers and Royal Challengers cricket is not)",
      reg("nba", MON, mine=True) < reg("nba", WED, mine=True) and reg("cricket", MON, mine=True) == reg("cricket", WED, mine=True))
check("the caps: weekend and Monday mornings carry more lines than a Wednesday", importance.CAP[SUN] > importance.CAP[WED] and importance.CAP[MON] > importance.CAP[WED])

# ---- picking -------------------------------------------------------------------------------------
many = [st("football", 9 - i * 0.2, f"Football: game {i}") for i in range(12)]
lots = many + [st("nfl", 8.5 - i * 0.1, f"NFL {i}") for i in range(4)] + [st("nba", 8 - i * 0.1, f"NBA {i}") for i in range(4)]
check("Sunday shows 8 lines at most, Wednesday 5; one sport never takes more than 4 of them", len(bigstuff.select(lots, SUN)) == 8 and len(bigstuff.select(lots, WED)) == 5
      and len(bigstuff.select(many, WED)) == 4)
mixed = [st("football", 9, "Football: a"), st("nfl", 8, "NFL: b"), st("nba", 7, "NBA: c"), st("cricket", 6, "Cricket: d"), st("mlb", 5, "MLB: e"), st("f1x", 4.5, "x: f"), st("tennis", 4.2, "Tennis: g")]
check("Wednesday cap is 5 lines in score order", [s["text"][-1] for s in bigstuff.select(mixed, WED)] == list("abcde"))
check("a story under the minimum score is dropped: a quiet morning has fewer lines", bigstuff.select([st("football", 3.9), st("nba", 2)], WED) == [])
ars = st("football", 6, "Football: Arsenal 1–0 Brentford", first=True, mine=True)
check("Arsenal's result is always first, even below a bigger story", bigstuff.select([st("nfl", 12), ars], WED)[0]["text"] == ars["text"])
mine_extra = [st("football", 9 - i * 0.1, f"F{i}") for i in range(4)] + [st("cricket", 7.5, "Cricket: India", mine=True), st("cricket", 7.4, "Cricket: RCB", mine=True)]
check("D's teams' stories and finals are never squeezed out by the per-sport limit or the cap (up to three over)", len(bigstuff.select(mine_extra, WED)) == 6)
promo = st("f1", 10, "F1: Max wins the Mexican Grand Prix", promote="f1")
check("a promoted F1 race is not in Key Overnight Scores (it has Major Events)", bigstuff.select([promo, st("football", 6)], MON) and all(not s.get("promote") for s in bigstuff.select([promo, st("football", 6)], MON)))
check("the pick is explained for the dev log", all("score" in s["why"] for s in bigstuff.select(many, MON)))

# ---- the Performance of the Day -----------------------------------------------------------------
p = lambda text, score, mine=False: events.perf("nba", text, score, mine)  # noqa: E731
check("no performance below the bar: none", bigstuff.performance([p("x", 49)]) is None)
check("the best performance wins, and D's own player wins a tie", bigstuff.performance([p("a", 60), p("b", 80)])["text"] == "b" and bigstuff.performance([p("a", 80), p("b", 80, True)])["text"] == "b")
card = {"innings": [{"team": "Royal Challengers Bengaluru", "batting": [{"name": "Virat Kohli", "out": "not out", "mark": "*", "r": 82, "b": 54}]}]}
k = events.kohli_innings(card)
check("Kohli's innings is found by name in a saved scorecard", k == [(82, 54, True)])
check("his figures read 'Virat Kohli 82* (54)'", events.kohli_text(k) == "Virat Kohli 82* (54)")
check("a modest Kohli innings clears the Performance of the Day bar, a duck does not",
      events.kohli_perf(12) >= importance.PERFORMANCE_MIN and events.kohli_perf(0) < importance.PERFORMANCE_MIN)
check("a Kohli match in the Cricket section: he is first in its standouts whatever he scored",
      __import__("kickoff.cricket", fromlist=["x"]).rank([{"kind": "century", "name": "A B", "runs": 140, "balls": 80}, {"kind": "kohli", "name": "Virat Kohli", "runs": 12, "balls": 9}])[0]["name"] == "Virat Kohli")

# ---- the lead sport ------------------------------------------------------------------------------
check("D's team first: Sunrisers/RCB/India cricket leads over a bigger non-mine story",
      bigstuff.lead_sport([st("cricket", 8, mine=True), st("nfl", 12)]) == "cricket")
check("among several of D's teams the more important stage leads (a final beats a league game)",
      bigstuff.lead_sport([st("football", 9, mine=True, first=True), st("cricket", 9, mine=True, stage="final")]) == "cricket")
check("equally important matches of D's teams: the normal order of the sports decides (Arsenal's football before the Jaguars)",
      bigstuff.lead_sport([st("nfl", 16, mine=True), st("football", 9, mine=True, first=True)]) == "arsenal")
check("none of D's teams: a big competition moment leads (an NBA playoff game)", bigstuff.lead_sport([st("nba", 8, stage="playoff"), st("football", 5)]) == "nba")
check("otherwise the normal order stays", bigstuff.lead_sport([st("football", 5), st("nba", 4)]) is None)
check("baseball never leads in the regular season, even as D's team", bigstuff.lead_sport([st("mlb", 8, mine=True, stage="regular")]) is None)
check("the Dodgers in the postseason can lead", bigstuff.lead_sport([st("mlb", 14, mine=True, stage="playoff")]) == "mlb")
check("Arsenal's result leads the football group (arsenal and football travel together)", bigstuff.lead_sport([st("football", 9, mine=True, first=True)]) == "arsenal")

# ---- converters on real data -----------------------------------------------------------------------
sb = json.load(open(FIX / "nba_scoreboards.json"))
games = [nba.parse_game(e) for day in sb.values() for e in day["events"]]
ev = events.nba(games, {"LAL"}, MON)
check("NBA: one story per finished game, winner first with the score", ev and all(e["text"].startswith("NBA: ") and "–" in e["text"] for e in ev), ev[:1])
check("NBA: a team with a tracked player makes the game 'mine'", any(e["mine"] for e in ev) == any(g["status"] == "final" and "LAL" in (g["home"]["abbr"], g["away"]["abbr"]) for g in games))
check("NBA: preseason is already dropped before the converter; a non-final game gives no story", events.nba([{**games[0], "status": "live"}], set(), MON) == [])

# ---- the whole edition ---------------------------------------------------------------------------
def fake(events_, news=(), inj=()):
    return lambda now, day, st_: {"sections": [{"id": "football", "title": "Football", "html": "<p>x</p>"}], "state": {}, "events": list(events_), "news": list(news), "injuries": list(inj)}


now = datetime(2026, 11, 8, 23, 15, tzinfo=timezone.utc)
day = datetime(2026, 11, 9).date()                    # a Monday
stories = [st("football", 12, "Football: Arsenal 3–0 Spurs", first=True, mine=True), st("nfl", 9, "NFL: Jaguars win", mine=True), events.perf("nba", "Shai: 52 pts", 88)]
out = daily.build_edition(now, day, {}, [("football", "Football", fake(stories, [{"text": "West Ham appoint Scott Parker", "link": "https://x", "source": "BBC"}], [{"text": "Saka (ARS): out, hamstring"}]))])
ed = out["edition"]
big = next(s for s in ed["sections"] if s["id"] == "big-stuff")
check("the edition's first section is The Big Stuff, with scores, news, injuries and the Performance of the Day",
      ed["sections"][0]["id"] == "big-stuff" and all(x in big["html"] for x in ("Key Overnight Scores", "Biggest News", "Major Injuries", "Performance Of The Day", "Arsenal 3")), big["html"][:300])
check("the headlines for the ping are the top stories, Arsenal first", ed["headlines"][0].startswith("Football: Arsenal") and len(ed["headlines"]) <= 3)
check("with no events at all the Big Stuff section is simply left out", "big-stuff" not in [s["id"] for s in daily.build_edition(now, day, {}, [("football", "Football", fake([]))])["edition"]["sections"]])
bad = daily.build_edition(now, day, {}, [("football", "Football", fake([{"kind": "result"}]))])
check("a broken story never breaks the edition: the sections stay and the problem is reported", bad["edition"]["sections"] and any("big stuff" in p for p in bad["problems"]), bad["problems"])
cric = daily.build_edition(now, day, {}, [("football", "Football", fake([st("cricket", 14, "Cricket: India v NZ, India won", mine=True)])),
                                         ("cricket", "Cricket", lambda n, d, s: {"sections": [{"id": "cricket", "title": "Cricket", "html": "<p>c</p>"}], "state": {}})])
check("a cricket story of D's team moves Cricket to the front of the sports", [s["id"] for s in cric["edition"]["sections"]][:3] == ["big-stuff", "cricket", "football"], [s["id"] for s in cric["edition"]["sections"]])
f1p = daily.build_edition(now, day, {}, [("f1", "F1", lambda n, d, s: {"sections": [{"id": "f1", "title": "F1", "html": "<p>f1</p>"}], "state": {}, "events": [events.f1([("Mexico City Grand Prix", "Max Verstappen", "Red Bull")])[0]]})])
fb = f1p["edition"]["sections"]
check("an F1 race gets a Major Events headline in The Big Stuff and its own section", fb[0]["id"] == "big-stuff" and "Major Events" in fb[0]["html"] and "Max Verstappen wins" in fb[0]["html"] and fb[1]["id"] == "f1", fb[0]["html"][:200])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
