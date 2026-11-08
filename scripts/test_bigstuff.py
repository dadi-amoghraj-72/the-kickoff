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
check("no star below the bar (70): none", bigstuff.stars([p("x", 69)]) == [])
check("Stars Of The Night: best first, up to three, D's own player first on a tie", [x["text"] for x in bigstuff.stars([p("a", 60), events.perf("cricket", "b", 80), p("c", 90), events.perf("football", "d", 75), p("e", 71)])] == ["c", "b", "d"]
      and bigstuff.stars([p("a", 100), p("b", 100, True)])[0]["text"] == "b")
_pf = lambda sp, t, sc: events.perf(sp, t, sc)  # noqa: E731
check("at most two stars from one sport, so a third basketball night makes room for another sport",
      [x["text"] for x in bigstuff.stars([_pf("nba", "n1", 100), _pf("nba", "n2", 99), _pf("nba", "n3", 98), _pf("football", "f1", 97)])] == ["n1", "n2", "f1"])
check("a hat-trick counts: three goals in a Champions League game scores about 97, above the bar", __import__("kickoff.performers", fromlist=["score"]).score({"goals": 3, "assists": 0, "shots_on": 3, "red": 0, "own_goals": 0, "pos": "F", "starter": True, "saves": 0, "conceded": 0}) * 6 >= importance.PERFORMANCE_MIN)
card = {"innings": [{"team": "Royal Challengers Bengaluru", "batting": [{"name": "Virat Kohli", "out": "not out", "mark": "*", "r": 82, "b": 54}]}]}
k = events.kohli_innings(card)
check("Kohli's innings is found by name in a saved scorecard", k == [(82, 54, True)])
check("his figures read 'Virat Kohli 82* (54)'", events.kohli_text(k) == "Virat Kohli 82* (54)")
check("a Kohli innings of 30 clears the Stars Of The Night bar, a duck does not",
      events.kohli_perf(30) >= importance.PERFORMANCE_MIN and events.kohli_perf(0) < importance.PERFORMANCE_MIN)
_ck = __import__("kickoff.cricket", fromlist=["x"])
_kcard = {"scorecard": [{"inning": "India Inning 1", "batting": [{"batsman": {"name": "Virat Kohli"}, "r": 7, "b": 7, "4s": 1, "6s": 0, "dismissal-text": "c X b Y"}], "bowling": []}]}
check("D, 2026-11-08: Kohli's 7 off 7 is not a standout (only a fifty, a century or a fast fifty would be)", not any("Kohli" in o["name"] for o in _ck.standouts(_kcard, {"matchType": "odi", "teams": ["India", "New Zealand"]})))
check("but his score is always shown under his match, small and muted", _ck.kohli_note({"innings": [{"batting": [{"name": "Virat Kohli", "r": 7, "b": 7, "out": "c X b Y"}]}]}) == '<span class="potm muted">Virat Kohli: 7 (7)</span>')
_ks = events.cricket([{"id": "k1", "name": "New Zealand vs India, 2nd ODI", "teams": ["New Zealand", "India"], "matchType": "odi", "matchEnded": True, "status": "India won by 4 runs", "class": {"label": "International"}}],
                     {"k1": {"innings": [{"batting": [{"name": "Virat Kohli", "r": 7, "b": 7, "out": "c X b Y"}]}], "standouts": []}}, 1)
check("and a 7 does not reach The Big Stuff, the headlines or the Stars: no Kohli on the result line, no Kohli performance", not any("Kohli" in x["text"] for x in _ks[0] + _ks[1]), [x["text"] for x in _ks[0] + _ks[1]])
_ks2 = events.cricket([{"id": "k2", "name": "New Zealand vs India, 2nd ODI", "teams": ["New Zealand", "India"], "matchType": "odi", "matchEnded": True, "status": "India won by 4 runs", "class": {"label": "International"}}],
                      {"k2": {"innings": [{"batting": [{"name": "Virat Kohli", "r": 82, "b": 54, "out": "not out"}]}], "standouts": []}}, 1)
check("an 82 does: on the result line and as a Star candidate", any("Virat Kohli 82" in x["text"] for x in _ks2[0]) and any("Kohli" in x["text"] for x in _ks2[1]), [x["text"] for x in _ks2[0] + _ks2[1]])

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
      ed["sections"][0]["id"] == "big-stuff" and all(x in big["html"] for x in ("Key Overnight Scores", "Biggest News", "Major Injuries", "Stars Of The Night", 'Arsenal <span class="n">3\u20130</span>')), big["html"][:300])
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

# ---- grouped by sport (D, 2026-11-05)
_gs = [{"kind": "result", "sport": "football", "comp": "Champions League", "text": "Champions League: Arsenal 2\u20131 Slavia Prague", "score": 40, "mine": True, "stage": "regular"},
       {"kind": "result", "sport": "football", "comp": "Champions League", "text": "Champions League: Como 9\u20131 Lens", "score": 30, "mine": False, "stage": "regular"},
       {"kind": "result", "sport": "cricket", "comp": "Cricket", "text": "Cricket: New Zealand v India, India won by 5 wickets", "score": 25, "mine": True, "stage": "regular"},
       {"kind": "result", "sport": "nba", "comp": "NBA", "text": "NBA: Boston Celtics 109\u2013102 Milwaukee Bucks", "score": 20, "mine": True, "stage": "regular"},
       {"kind": "result", "sport": "ufc", "comp": "UFC", "text": "UFC 330: Jon Jones def. Stipe Miocic", "score": 22, "mine": False, "stage": "final"}]
_gh = bigstuff.html(_gs)
check("each sport is named once as a header, its games are the bullets under it, without the repeated prefix",
      _gh.count("Champions League") == 1 and '<p class="subhead comp">Champions League</p><ul class="standouts bigstuff"><li>Arsenal <span class="n">2\u20131</span> Slavia Prague</li><li>Como <span class="n">9\u20131</span> Lens</li></ul>' in _gh
      and "<li>Champions League:" not in _gh and '<p class="subhead">NBA</p>' in _gh and '<li>Boston Celtics <span class="n">109\u2013102</span> Milwaukee Bucks</li>' in _gh, _gh)
check("the groups follow the order of their best story: Champions League, Cricket, NBA", _gh.index("Champions League") < _gh.index("Cricket") < _gh.index("NBA"))
check("a story that does not begin with its competition keeps its whole text under the header (UFC)", '<p class="subhead">UFC</p><ul class="standouts bigstuff"><li>UFC 330: Jon Jones def. Stipe Miocic</li>' in _gh, _gh)
_fb = bigstuff.html([{"kind": "result", "sport": "football", "comp": "Premier League", "text": "Premier League: Everton 3\u20131 Coventry City", "score": 20, "mine": False, "stage": "regular"},
                     {"kind": "result", "sport": "cricket", "comp": "International", "text": "Cricket: Afghanistan v Zimbabwe \u00b7 Day 2: Zimbabwe 504 (134.3), Afghanistan 113/1 (35)", "score": 6, "mine": False, "stage": "regular"},
                     {"kind": "result", "sport": "football", "comp": "FA Cup", "text": "FA Cup: Leicester City 4\u20132 Oxford City", "score": 5, "mine": False, "stage": "regular"}])
check("football is one header with its competitions under it, even when another sport ranks between them (D, 2026-11-07)",
      _fb.count('<p class="subhead">Football</p>') == 1 and _fb.index("Football") < _fb.index("Premier League") < _fb.index("FA Cup") < _fb.index("Cricket") and '<p class="subhead comp">FA Cup</p>' in _fb, _fb)
check("the scores are gold and the rest is plain: '504 (134.3)' and '113/1 (35)' gold, 'Day 2' not",
      '<span class="n">504 (134.3)</span>' in _fb and '<span class="n">113/1 (35)</span>' in _fb and '<span class="n">2</span>' not in _fb and "Day 2:" in _fb, _fb)
check("a tennis line's sets are gold, an F1 winner line has nothing to gold", bigstuff.gold_scores("Tennis: Sinner beat Alcaraz 6\u20134 7\u20136 in the final") == 'Tennis: Sinner beat Alcaraz <span class="n">6\u20134 7\u20136</span> in the final'
      and "<span" not in bigstuff.gold_scores("F1: Max Verstappen wins the Brazilian Grand Prix"))
_pl = events.f1_pole([("Brazilian Grand Prix", "Lando Norris", "McLaren", "1:27.470")])[0]
check("F1 pole reads 'On pole · Lando Norris · Brazilian Grand Prix · 1:27.470' with 'On pole' in gold (D, 2026-11-08)", '<li><span class="n">On pole</span> \u00b7 Lando Norris \u00b7 Brazilian Grand Prix \u00b7 1:27.470</li>' in bigstuff.html([_pl]), bigstuff.html([_pl]))
_mk = lambda h, a, hs, as_, hid, aid, **k: {"home": {"name": h, "id": hid}, "away": {"name": a, "id": aid}, "home_score": hs, "away_score": as_, "completed": True, "goals": [], "reds": [], "stage": "", **k}  # noqa: E731
_up = {e["text"]: e["score"] for e in events.football([("Premier League", [_mk("Nottingham Forest", "Manchester City", 3, 1, "393", "382", upset="upset"), _mk("Nottingham Forest", "Manchester City", 3, 1, "393", "382")]),
                                                      ("FA Cup", [_mk("Barrow", "Gillingham", 1, 0, "1", "2")]), ("Bundesliga", [_mk("RB Leipzig", "FC Augsburg", 5, 2, "11420", "3")])], 6)}
_ups = sorted(e["score"] for e in events.football([("Premier League", [_mk("Nottingham Forest", "Manchester City", 3, 1, "393", "382", upset="upset")])], 6) + events.football([("Premier League", [_mk("Nottingham Forest", "Manchester City", 3, 1, "393", "382")])], 6))
check("D, 2026-11-08: an upset (the favourite lost, from the odds) scores: Forest 3–1 Man City is worth 4 more and outranks Leipzig's 5–2 and Barrow's 1–0",
      abs(_ups[1] - _ups[0] - importance.UPSET["upset"]) < 1e-6 and _ups[1] > _up["Bundesliga: RB Leipzig 5\u20132 FC Augsburg"] > _up["FA Cup: Barrow 1\u20130 Gillingham"], (_ups, _up))
check("the Telegram headlines keep the sport prefix on every line (they stand alone)", bigstuff.headlines(_gs)[0] == "Champions League: Arsenal 2\u20131 Slavia Prague")

# ---- review of the first real rehearsal (D, 2026-11-05)
_cr = bigstuff.html([{"kind": "result", "sport": "cricket", "comp": "International", "text": "Cricket: New Zealand v India, India won by 5 wickets", "score": 30, "mine": True, "stage": "regular"}])
check("cricket is headed 'Cricket', not its competition ('International')", '<p class="subhead">Cricket</p>' in _cr and "International" not in _cr and '<li>New Zealand v India, India won by <span class="n">5 wickets</span></li>' in _cr, _cr)
_nw = [{"text": "England captain Harry Kane has signed a new contract with Bayern Munich that lasts until 2029.", "source": "BBC Sport"}, {"text": "Harry Kane has put pencil to paper on a new contract, committing his future to Bayern Munich.", "source": "ESPN"},
       {"text": "Chelsea have sacked their manager Enzo Maresca.", "source": "BBC Sport"}]
check("the same story from two sources is shown once (Kane's contract on BBC and ESPN), a different story stays", len(bigstuff.dedupe_news(_nw)) == 2 and bigstuff.dedupe_news(_nw)[1]["text"].startswith("Chelsea"), bigstuff.dedupe_news(_nw))

# ---- a century or a five-wicket haul always makes Stars Of The Night (D, 2026-11-05)
_ms = {**events.perf("cricket", "Charli Knott (Brisbane Heat W): 104 (61), 12 fours, 4 sixes v Adelaide Strikers W", 86), "milestone": True}
_top = [events.perf("nba", "n1", 100), events.perf("football", "f1", 100), events.perf("cricket", "Virat Kohli (India): 74 (51)", 100)]
check("a century in a women's league makes the list even when three performances already filled it", _ms in bigstuff.stars(_top + [_ms]) and len(bigstuff.stars(_top + [_ms])) == 4, bigstuff.stars(_top + [_ms]))
check("an ordinary performance of the same score still waits outside the three", len(bigstuff.stars(_top + [events.perf("cricket", "x", 86)])) == 3)

_wm = {"id": "w1", "name": "Brisbane Heat Women vs Adelaide Strikers Women, 10th Match, Women's Big Bash League", "teams": ["Brisbane Heat Women", "Adelaide Strikers Women"], "matchType": "t20", "matchEnded": True,
       "status": "Brisbane Heat Women won by 14 runs", "class": {"kind": "league", "label": "WBBL", "women": True}}
_wo = {"kind": "century", "name": "Charli Knott", "team": "Brisbane Heat Women", "against": "Adelaide Strikers Women", "runs": 104, "balls": 61, "fours": 12, "sixes": 4, "not_out": False, "match": "x", "result": ""}
_, _wp, _wk = events.cricket([_wm], {"w1": {"innings": [], "standouts": [_wo]}}, 1)
check("a century in the Women's Big Bash is a milestone performance in the clean standout style with the team codes", len(_wp) == 1 and _wp[0]["milestone"] and _wp[0]["text"] == "Charli Knott (BH-W): 104 (61), 12\u00d74, 4\u00d76 v AS-W", _wp)

# ---- live Tests: a day-one century is a Star and a headline once; 150 is announced again (D, 2026-11-05)
_tm = {"id": "t9", "name": "Afghanistan vs Zimbabwe, 1st Test, Zimbabwe tour", "teams": ["Afghanistan", "Zimbabwe"], "matchType": "test", "matchEnded": False, "matchStarted": True,
       "status": "Zimbabwe won toss & batted", "class": {"kind": "international", "label": "International"}}
_bt = lambda runs, balls: {"kind": "century", "name": "Brendan Taylor", "team": "Zimbabwe", "against": "Afghanistan", "runs": runs, "balls": balls, "fours": 14, "sixes": 4, "not_out": True}  # noqa: E731
_s1, _p1, _k1 = events.cricket([_tm], {"t9": {"innings": [], "standouts": [_bt(131, 168)]}}, 4)
check("a century on day 1 of a live Test is a Star Of The Night (milestone), in the short style; it is NOT a Key Overnight Scores line any more (those are team scores, D 2026-11-06)", len(_p1) == 1 and _p1[0]["milestone"] and _p1[0]["text"] == "Brendan Taylor (ZIM): 131* (168), 14\u00d74, 4\u00d76 v AFG" and _s1 == [], (_s1, _p1))
_live = {**_tm, "dateTimeGMT": "2026-11-05T06:00:00", "score": [{"inning": "Zimbabwe Inning 1", "r": 326, "w": 5, "o": 87}]}
from datetime import datetime as _dt, timezone as _tz
_ts, _, _ = events.cricket([_live], {}, 4, (), None, _dt(2026, 11, 5, 23, 15, tzinfo=_tz.utc))
check("a Test in progress is a Key Overnight Scores line of team scores with its day: 'Afghanistan v Zimbabwe \u00b7 Day 1: Zimbabwe 326/5 (87)'", len(_ts) == 1 and _ts[0]["text"] == "Cricket: Afghanistan v Zimbabwe \u00b7 Day 1: Zimbabwe 326/5 (87)" and _ts[0]["score"] >= importance.MIN_SCORE, _ts)
check("it is shown only on the mornings its score moved (changed), not when play was rained off", events.cricket([_live], {}, 4, (), set(), _dt(2026, 11, 5, 23, 15, tzinfo=_tz.utc))[0] == [] and len(events.cricket([_live], {}, 4, (), {"t9"}, _dt(2026, 11, 5, 23, 15, tzinfo=_tz.utc))[0]) == 1)
_s2, _p2, _k2 = events.cricket([_tm], {"t9": {"innings": [], "standouts": [_bt(131, 168)]}}, 4, _k1)
check("announced once: the next morning, still 131, nothing again", _s2 == [] and _p2 == [], (_s2, _p2))
_s3, _p3, _k3 = events.cricket([_tm], {"t9": {"innings": [], "standouts": [_bt(163, 200)]}}, 4, _k1)
check("163 on day 2 passes 150: announced again as a Star, ranked above an ordinary century", len(_p3) == 1 and _p3[0]["score"] > _p1[0]["score"], _p3)
_s4, _p4, _k4 = events.cricket([_tm], {"t9": {"innings": [], "standouts": [_bt(205, 260)]}}, 4, _k3)
check("205 passes 200: announced once more; a later 210 is silent", len(_p4) == 1 and events.cricket([_tm], {"t9": {"innings": [], "standouts": [_bt(210, 270)]}}, 4, _k4)[1] == [])
_ten = {"kind": "ten-for", "name": "Taskin Ahmed", "team": "Bangladesh", "against": "West Indies", "wickets": 10, "runs_conceded": 121, "overs": 38, "maidens": 6, "economy": 3.18, "parts": [(5, 60), (5, 61)]}
_s5, _p5, _k5 = events.cricket([_tm], {"t9": {"innings": [], "standouts": [_ten]}}, 4)
check("ten wickets in a match: a Star (92), once; a five-for already announced is not repeated as a five-for", _p5 and _p5[0]["score"] >= 92 and events.cricket([_tm], {"t9": {"innings": [], "standouts": [_ten]}}, 4, _k5)[1] == [])
_ff = {"kind": "fast fifty", "name": "P", "team": "A", "against": "B", "runs": 62, "balls": 24, "fours": 6, "sixes": 4, "not_out": False}
_pf = events.cricket([{**_tm, "matchType": "t20", "matchEnded": True}], {"t9": {"innings": [], "standouts": [_ff, {**_ff, "kind": "fifty", "name": "Q", "balls": 40}]}}, 4)[1]
check("a T20 fast fifty can be a Star (at least the bar), an ordinary fifty never is", len([p for p in _pf if p["text"].startswith("P ")]) == 1 and [p for p in _pf if p["text"].startswith("P ")][0]["score"] >= importance.PERFORMANCE_MIN and not [p for p in _pf if p["text"].startswith("Q ")])

# ---- a dramatic finish clears the bar even on a quiet morning (D, 2026-11-05: the Heat's buzzer-beater)
_ng = lambda a_, h_, **k: {"status": "final", "phase": "regular", "away": {"abbr": "LAC", "name": "Los Angeles Clippers", "score": a_}, "home": {"abbr": "MIA", "name": "Miami Heat", "score": h_}, "ot": False, "headline": "", "cup": None, "series": None, **k}  # noqa: E731
_plain = events.nba([_ng(95, 110)], set(), 4)[0]["score"]
_thriller = events.nba([_ng(116, 117, ot=True, clutch=True)], set(), 4)[0]["score"]
check("a buzzer-beater in overtime by a point scores above the bar on a Friday, an ordinary 15-point game does not", _thriller >= importance.MIN_SCORE > _plain, (_thriller, _plain))
check("a one-point game and an overtime game by three each earn the bonus; an overtime game by ten does not", events.nba([_ng(110, 111)], set(), 4)[0]["score"] > _plain and events.nba([_ng(108, 111, ot=True)], set(), 4)[0]["score"] > events.nba([_ng(100, 110, ot=True)], set(), 4)[0]["score"])
_fm = lambda hs, as_, minute: {"home": {"id": "1", "name": "A", "short": "A"}, "away": {"id": "2", "name": "B", "short": "B"}, "home_score": hs, "away_score": as_, "completed": True, "goals": [{"minute": minute, "player": "P", "side": "home" if hs > as_ else "away"}]}  # noqa: E731
check("a winning goal in the 90th minute or later (one-goal game) is a late winner; one in the 60th, a draw, and a 3-goal win are not",
      events.late_winner(_fm(1, 0, "90'+3'")) and events.late_winner(_fm(2, 1, "90'")) and not events.late_winner(_fm(1, 0, "60'")) and not events.late_winner(_fm(1, 1, "90'")) and not events.late_winner(_fm(3, 0, "90'")))

# ---- the ping's headlines are never empty (D, 2026-11-05)
_st = lambda text, score: {"kind": "result", "sport": "nba", "comp": "NBA", "text": text, "score": score, "mine": False, "stage": "regular"}  # noqa: E731
_heat = _st("NBA: Miami Heat 117\u2013116 Los Angeles Clippers (OT)", 3.9)
_star = {**events.perf("cricket", "Charli Knott (Brisbane Heat W): 104 (61), 12 fours, 4 sixes v Adelaide Strikers W", 86), "milestone": True}
check("a quiet morning with nothing above the bar still has headlines: the Stars first, then the best game below the bar", bigstuff.fill_headlines([], [_heat], [_star]) == ["Star Of The Night: " + _star["text"], _heat["text"]], bigstuff.fill_headlines([], [_heat], [_star]))
_plainstar = events.perf("nba", "Victor Wembanyama (SAS): 52 pts", 100)
check("three key scores and no milestone Star: the ping is just the three scores", bigstuff.fill_headlines([_st("a", 9), _st("b", 8), _st("c", 7)], [_heat], [_plainstar]) == ["a", "b", "c"])
check("two team scores, then the best milestone Star (a century, 150+, ten in a match) in the third slot (D, 2026-11-06)", bigstuff.fill_headlines([_st("a", 9), _st("b", 8), _st("c", 7)], [_heat], [_plainstar, _star]) == ["a", "b", "Star Of The Night: " + _star["text"]])
check("the Stars lines carry the main figure in gold: '111* (171)', '4/35', '52 pts'", '<span class="n">111* (171)</span>' in bigstuff.gold_figures("Amir Jangoo (WI): 111* (171), 11\u00d74, 2\u00d76 v BAN") and '<span class="n">4/35</span>' in bigstuff.gold_figures("Alana King (PS-W): 4/35 (4 ov, 8.8 econ) v ST-W") and '<span class="n">52 pts</span>' in bigstuff.gold_figures("V (SAS): 52 pts, 24 reb"))
check("no games and no stars: still nothing to invent (an empty list, handled by the Today block)", bigstuff.fill_headlines([], [], []) == [])
_b = bigstuff.build([_heat], [], [], 4)
check("a quiet morning is flagged (fewer than three key scores) and its headline list comes from the fill", _b["quiet"] is True and _b["headlines"] == [_heat["text"]], _b["headlines"])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
