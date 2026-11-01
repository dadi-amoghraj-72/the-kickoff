"""Offline tests for the matchday overview. Run: .venv/bin/python scripts/test_overview.py"""
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import notes, overview  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
ODDS = json.loads((FIX / "espn_cl_odds_20261021.json").read_text())
SCORES = json.loads((FIX / "espn_cl_20261021.json").read_text())
espn.get_json = lambda url, params=None, **kw: ODDS[params["event"]] if "/summary" in url else SCORES
MS = espn.get_matches_on("uefa.champions", date(2026, 10, 21))
ODDS_BY_ID = overview.collect_odds("uefa.champions", MS)
TABLE = json.loads((FIX / "espn_cl_table.json").read_text())
espn.get_json = lambda url, params=None, **kw: (TABLE if "standings" in url else ODDS[params["event"]] if "/summary" in url else SCORES)
ROWS = espn.get_table(espn.CHAMPIONS_LEAGUE)
by = lambda name: next(m for m in MS if name in overview.label(m))  # noqa: E731
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


# ---- Odds to chances ----
check("Como v Man Utd: 40 / 25 / 35 once the bookmaker's margin is removed", ODDS_BY_ID[by("Como")["id"]] == {"home": 40, "draw": 25, "away": 35}, ODDS_BY_ID[by("Como")["id"]])
check("Sporting v LASK: a 70% home favourite", ODDS_BY_ID[by("Sporting")["id"]] == {"home": 70, "draw": 17, "away": 13})
check("chances always add to 100", all(sum(p.values()) in (99, 100, 101) for p in ODDS_BY_ID.values()))
check("no odds, or odd-looking odds, give None", overview.chances(None) is None and overview.chances([]) is None
      and overview.chances([{"homeTeamOdds": {}}]) is None and overview.chances([{"homeTeamOdds": {"moneyLine": "x"}}]) is None)

# ---- Verdicts ----
v = lambda name: overview.verdict(by(name), ODDS_BY_ID[by(name)["id"]])  # noqa: E731
check("no clear favourite means 'close_match', even when a team wins 4-1", v("Como") == "close_match" and v("Bayern") == "close_match")
check("a 70% favourite losing at home is a big upset", v("Sporting") == "big_upset")
check("a clear favourite winning is 'favourite_won'", v("Aston Villa") == "favourite_won" and v("Real Madrid") == "favourite_won")
mk = lambda hs, as_: {"home_score": hs, "away_score": as_}  # noqa: E731
check("a favourite held to a draw", overview.verdict(mk(1, 1), {"home": 60, "draw": 25, "away": 15}) == "favourite_held")
check("a 55% favourite losing is an upset, not a big one", overview.verdict(mk(0, 1), {"home": 55, "draw": 25, "away": 20}) == "upset")
check("an away favourite is handled too", overview.verdict(mk(0, 2), {"home": 15, "draw": 20, "away": 65}) == "favourite_won")
check("without odds there is no verdict", overview.verdict(mk(1, 0), None) is None)

# ---- Drama ----
d = lambda name: overview.drama(by(name))  # noqa: E731
check("minutes with stoppage time are read as the base minute", (overview.minute_number("90'+1'"), overview.minute_number("45'+3'"), overview.minute_number("7'")) == (90, 45, 7))
check("lead changes count swings that pass through a level score (Sporting led, LASK came back)", d("Sporting")["lead_changes"] == 1, d("Sporting"))
check("Lille v Galatasaray swung twice; Como v Man Utd never", (d("Lille")["lead_changes"], d("Como")["lead_changes"]) == (2, 0), (d("Lille"), d("Como")))
check("comebacks: LASK and Galatasaray came from behind, Como did not", (d("Sporting")["comeback"], d("Lille")["comeback"], d("Como")["comeback"]) == (True, True, False))
check("a goal from the 85th minute on is 'late'", d("Sporting")["late_goal_minute"] == 89 and d("Lille")["late_goal_minute"] is None)
ranked = sorted(MS, key=lambda m: -overview.excitement(overview.drama(m), overview.verdict(m, ODDS_BY_ID[m["id"]])))
check("game of the night ranking: Sporting-LASK, then Lille-Galatasaray, then Bayern-Arsenal",
      [overview.label(m).split()[0] for m in ranked[:3]] == ["Sporting", "Lille", "Bayern"], [overview.label(m) for m in ranked[:3]])

# ---- Facts ----
f = overview.matchday_facts("UEFA Champions League", MS, ODDS_BY_ID, ROWS)
check("tally: 5 favourites won, 1 upset, 3 close matches", f["tally"] == {"matches": 9, "favourite_won": 5, "favourite_held": 0, "upsets": 1, "close_matches": 3}, f["tally"])
check("game of the night is Sporting CP 2-3 LASK Linz", f["game_of_the_night"] == "Sporting CP 2-3 LASK Linz", f["game_of_the_night"])
como = next(r for r in f["matches"] if r["match"].startswith("Como"))
check("each match carries named chances, the label and ESPN's report headline",
      como["pre_match_chances_pct"] == {"Como": 40, "draw": 25, "Manchester United": 35} and como["result_vs_expectation"] == "close_match"
      and "Carrick" in como["recap"]["headline"], como)
check("the facts say where expectations came from", f["expectations"] == "from pre-match betting odds")
nof = overview.matchday_facts("UEFA Champions League", MS, {m["id"]: None for m in MS})
check("with no odds: no tally, no labels, and the facts say so", nof["expectations"] == "unavailable" and "tally" not in nof
      and all("result_vs_expectation" not in r for r in nof["matches"]))
check("plain fallback: favourites tally, the upset, and the game of the night",
      overview.plain_overview(f) == "The favourites won 5 of 9 matches. Upsets: Sporting CP 2-3 LASK Linz. Game of the night: Sporting CP 2-3 LASK Linz, with 5 goals.", overview.plain_overview(f))
check("plain fallback without odds still names the game of the night", overview.plain_overview(nof).startswith("Game of the night:"))

# ---- Goal timeline, winning goal, league records ----
spo = next(r for r in f["matches"] if r["match"].startswith("Sporting"))
check("goal timeline: who, when, for which team, and the running score",
      [(g["minute"], g["for"], g["score_after"]) for g in spo["goals"]] ==
      [(5, "Sporting CP", "1-0"), (15, "LASK Linz", "1-1"), (63, "LASK Linz", "1-2"), (68, "LASK Linz", "1-3"), (89, "Sporting CP", "2-3")], spo["goals"])
check("the winning goal is LASK's third (68th minute), not Sporting's late one",
      spo["winning_goal"]["minute"] == 68 and spo["winning_goal"]["for"] == "LASK Linz", spo["winning_goal"])
bay = next(r for r in f["matches"] if r["match"].startswith("Bayern"))
como_row = next(r for r in f["matches"] if r["match"].startswith("Como"))
check("a draw has no winning goal; Como's winning goal is their second", "winning_goal" not in bay and como_row["winning_goal"]["minute"] == 49, (bay.get("winning_goal"), como_row.get("winning_goal")))
rm = next(r for r in f["matches"] if r["match"].startswith("Real Madrid"))
check("league records carry played, won, drawn, lost and position", {"position", "points", "played", "won", "drawn", "lost"} <= set(rm["league_table_now"]["Real Madrid"]), rm["league_table_now"])
check("perfect_start appears only when a team has won every game", rm["league_table_now"]["Real Madrid"].get("perfect_start") is True
      and "perfect_start" not in como_row["league_table_now"]["Como"], (rm["league_table_now"], como_row["league_table_now"]))
check("the misleading 'late goal' label is gone from the facts", all("late_goal_minute" not in r for r in f["matches"]))

# ---- The checker ----
good = ("Five of the nine favourites won, but Sporting CP's 3-2 defeat by LASK Linz was the night's big upset: LASK came from behind, "
        "and Sporting's 89th-minute goal was not enough.")
check("a faithful overview passes", overview.check_overview(good, f) == [], overview.check_overview(good, f))
check("'upset' without an upset label is rejected", any("not supported" in p for p in overview.check_overview("Como's win over Manchester United was a shock.", nof)))
check("'upset' is fine when the data labels one", not any("not supported" in p for p in overview.check_overview(good, f)))
check("favourite talk is rejected when no odds were available", any("no odds" in p for p in overview.check_overview("The favourites mostly won.", nof)))
copied = "Como embarrass Man United as rout adds to Carrick pressure, and Como won 4-1."
check("copying a run of six words from ESPN's headline is rejected", any("copies" in p for p in overview.check_overview(copied, f)), overview.check_overview(copied, f))
para = "Como beat Manchester United 4-1, which adds to the pressure on Carrick."
check("a paraphrase that uses a name from the report is fine", not any("copies" in p or "Carrick" in p for p in overview.check_overview(para, f)), overview.check_overview(para, f))
check("an invented name is rejected", any("Mourinho" in p for p in overview.check_overview("Mourinho watched Como win.", f)))
norecap = {**f, "matches": [{k: v for k, v in r.items() if k != "recap"} for r in f["matches"]]}
check("'former club' is rejected when the facts don't say it", any("former" in p for p in overview.check_overview("Madrid beat their former club Leipzig.", norecap)))
check("'former club' is allowed when ESPN's report says it (the Leipzig report does)", not any("former" in p for p in overview.check_overview("Madrid beat their former club Leipzig.", f)))
bare = {**norecap, "matches": [{k: v for k, v in r.items() if k != "league_table_now"} for r in norecap["matches"]]}
check("'perfect start' is rejected when neither the reports nor the table records support it",
      any("perfect" in p for p in overview.check_overview("Como kept their perfect start going.", bare)))
check("'perfect start' is allowed when the facts support it", not any("perfect" in p for p in overview.check_overview("Real Madrid kept their perfect start going.", f)))
check("calling the 89th-minute goal decisive is rejected (Sporting's late goal only made it 2-3)",
      any("decisive" in p for p in overview.check_overview("Sporting lost, with the decisive goal arriving in the 89th minute.", f)))
check("calling the real winning goal decisive is fine", not any("decisive" in p for p in overview.check_overview("LASK's decisive goal came in the 68th minute.", f)))
REAL = ("The favourites mostly did their jobs, with five of the nine winning, but Sporting CP were the exception. They were given a 70 per cent chance "
        "against LASK Linz and lost 3-2 after a comeback, with the decisive goal arriving in the 89th minute. That makes it the game of the night and the "
        "big upset. Real Madrid and Aston Villa both kept their perfect starts going, though Madrid's win over former club RB Leipzig looked the more "
        "emphatic of the two. In Munich, Arsenal fought back for a draw, and Como's rout of Manchester United will keep the pressure on Carrick.")
real_problems = overview.check_overview(REAL, f)
check("the real overview from Sonnet: its one genuine error (the 'decisive' 89th-minute goal) is caught; 'former club' and 'perfect start' came from ESPN's reports and are allowed",
      len(real_problems) == 1 and "decisive" in real_problems[0], real_problems)
check("an over-long overview is rejected", any("over the limit" in p for p in overview.check_overview(" ".join(["word"] * 140), f)))


# ---- Talking to Claude (fake) ----
class Fake:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.beta = NS(messages=NS(create=self._create))
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def reply(text, stop="end_turn"):
    body = text if text.startswith("{") or text == "not json" else json.dumps({"overview": text})
    return NS(stop_reason=stop, usage=NS(input_tokens=2000, output_tokens=150), content=[NS(type="text", text=body)])


c = Fake([reply(good)])
res, usage = overview.write_overview(c, f)
check("a good overview is used and marked as Claude's", res["source"] == "claude" and res["note"] == good and len(c.calls) == 1)
call = c.calls[0]
check("request: facts as data, the 'do not list results' system prompt, low effort, no temperature",
      "do NOT list results" in call["system"] and "pre_match_chances_pct" in call["messages"][0]["content"]
      and call["output_config"]["effort"] == "low" and "temperature" not in call)
bad = "Como's win over Manchester United was a shock."
c = Fake([reply(bad), reply(para)])
res, usage = overview.write_overview(c, nof)
check("a rejected overview is retried once, and the retry names the problem",
      res["source"] == "claude" and len(c.calls) == 2 and "not supported" in c.calls[1]["messages"][0]["content"], res)
check("usage is added across both calls", usage == {"input": 4000, "output": 300})
res, _ = overview.write_overview(Fake([reply(bad), reply(bad), reply(bad)]), nof)
check("still bad after the retry: the plain overview, with the problems recorded", res["source"] == "plain" and res["problems"] and "shock" not in res["note"], res)
check("both rejected attempts are kept, with their text and reasons, for diagnosis",
      [r["attempt"] for r in res["rejected"]] == [1, 2, 3] and all(r["note"] == bad and r["problems"] for r in res["rejected"]), res["rejected"])
res, _ = overview.write_overview(Fake([RuntimeError("down")] * 3), f)
check("an API failure gives the plain overview", res["source"] == "plain" and res["note"] == overview.plain_overview(f))
res, _ = overview.write_overview(Fake([reply("not json")] * 3), f)
check("an unreadable reply gives the plain overview", res["source"] == "plain")
res, _ = overview.write_overview(Fake([reply("{}", stop="refusal")] * 3), f)
check("a refusal gives the plain overview", res["source"] == "plain")

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
