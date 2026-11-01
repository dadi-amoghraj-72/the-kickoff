"""Offline tests for match notes, using a fake Claude. Run: python3 scripts/test_notes.py"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import notes, settings  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
espn.get_json = lambda url, params=None, **kw: json.loads((FIX / ("espn_pl_table.json" if "standings" in url else "espn_pl_20261031.json")).read_text())
MATCHES = espn.get_matches_on("eng.1", __import__("datetime").date(2026, 10, 31))
TABLE = espn.get_table("eng.1")
results = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


# ---- Choosing matches ----
sel = notes.select("eng.1", MATCHES)
check("Premier League: all 8 games get a note", len(sel) == 8, len(sel))
first = sel[0][0]
check("big six first: Manchester City's game leads", "382" in (first["home"]["id"], first["away"]["id"]), first["home"]["name"])
big_flags = [any(i in notes.BIG_SIX_ORDER for i in (m["home"]["id"], m["away"]["id"])) for m, _ in sel]
check("every big-six game comes before every other game", big_flags == sorted(big_flags, reverse=True), big_flags)
check("two big-six clubs meeting gets the fuller 'derby' length",
      [t for m, t in sel if {m["home"]["id"], m["away"]["id"]} == {"363", "360"}] == ["derby"])
mk = lambda i, h, a, hs=1, as_=0: {"id": i, "kickoff": "2026-11-01T15:00Z", "completed": True, "home": {"id": h, "name": "H"},  # noqa: E731
                                    "away": {"id": a, "name": "A"}, "home_score": hs, "away_score": as_, "goals": [], "reds": []}
other = notes.select("esp.1", [mk("1", "86", "9999"), mk("2", "110", "103"), mk("3", "8888", "9999"), mk("4", "359", "9999")])
check("other leagues: listed clubs only; Inter v Milan is a derby; Arsenal's game left out",
      [(m["id"], t) for m, t in other] == [("1", "short"), ("2", "derby")] or sorted((m["id"], t) for m, t in other) == [("1", "short"), ("2", "derby")], other)

# ---- Facts ----
che = next(m for m, _ in sel if m["home"]["id"] == "363")
prev = {"363": 8, "360": 5}
f = notes.match_facts(che, "derby", TABLE, prev)
check("facts: score, scorers with minutes, and a red card", f["final_score"] == "2-0" and len(f["goals"]) == 2
      and all(g["minute"] and g["scorer"] for g in f["goals"]) and len(f["red_cards"]) == 1, f)
check("facts: table position and points for both teams", set(f["table"]) == {"Chelsea", "Manchester United"}
      and all({"position_now", "points", "played"} <= set(v) for v in f["table"].values()))
check("facts: 'position_before' only when a team actually moved",
      all(("position_before" in v) == (v["position_now"] != prev[k]) for k, v in
          zip(("363", "360"), (f["table"]["Chelsea"], f["table"]["Manchester United"]))), f["table"])
check("facts hold no player or club that isn't in the match", "Arsenal" not in json.dumps(f))

# ---- The safety check ----
scorer = f["goals"][0]["scorer"]
minute = f["goals"][0]["minute"].rstrip("'’")
good = f"Chelsea beat Manchester United 2-0, with {scorer} scoring in the {minute}th minute."
check("a faithful note passes", notes.check_note(good, f) == [], notes.check_note(good, f))
check("an invented number is caught", any("number 61000" in p for p in notes.check_note("Chelsea won 2-0 in front of 61000 fans.", f)))
check("an invented name is caught", any("Mourinho" in p for p in notes.check_note("Chelsea won 2-0 and Mourinho smiled.", f)))
check("an invented name at the START of a sentence is caught", any("Mourinho" in p for p in notes.check_note("Chelsea won 2-0. Mourinho was pleased.", f)))
check("ordinary sentence openers and -ing words are not mistaken for names",
      notes.check_note("Overall, Chelsea won 2-0. Scoring twice, they never looked back. Meanwhile United struggled.", f) == [],
      notes.check_note("Overall, Chelsea won 2-0. Scoring twice, they never looked back. Meanwhile United struggled.", f))
check("club nicknames such as Spurs are allowed", notes.check_note("Spurs won 2-0.", f) == [])
check("possessives and hyphenated facts don\'t cause false alarms", notes.check_note("Chelsea's win over Manchester United finished 2-0.", f) == [])
nomove = {k: v for k, v in f["table"].items()}
stay = "Chelsea won 2-0 and stay fourth."
check("claiming a table move without a previous position is caught",
      any("implies a table move" in p for p in notes.check_note(stay, {**f, "table": {k: {kk: vv for kk, vv in v.items() if kk != "position_before"} for k, v in nomove.items()}})))
withprev = {**f, "table": {"Chelsea": {"position_now": 4, "position_before": 8, "points": 16, "played": 9}}}
check("the same wording is fine when the facts give the previous position", not any("implies" in p for p in notes.check_note("Chelsea climb to fourth.", withprev)), notes.check_note("Chelsea climb to fourth.", withprev))
check("plain wording about position is not mistaken for a move", notes.check_note("Chelsea are fourth on 16 points.", {**f, "table": {"Chelsea": {"position_now": 4, "points": 16, "played": 9}}}) == [])
SHORT = {"length": notes.TIERS["short"][0]}
STANDARD = {"length": notes.TIERS["standard"][0]}
haiku_barca = ("Barcelona thrashed Alavés 6-1 at home. Raphinha scored twice, in the 8th and 41st minutes, Fermín López added one in the 23rd, "
               "and Lamine Yamal scored twice, in first-half stoppage time and the 64th minute. Anthony Gordon made it six in the 81st, "
               "and Mariano Díaz replied for Alavés in the 84th.")
opus_atletico = "Alejandro Grimaldo and Giuliano Simeone scored as Atlético Madrid won 2-0 at Levante; Atlético are second on 28 points, Levante 18th on 10."
big = {**SHORT, "home": "Barcelona", "away": "Alavés", "final_score": "6-1", "goals": [{"minute": "8", "scorer": "Raphinha", "for": "Barcelona", "type": "goal"}],
       "table": {"Barcelona": {"position_now": 1, "points": 30, "played": 11}}}
check("a one-liner that runs to several sentences is rejected for length", any("over the limit" in p for p in notes.check_note(haiku_barca, big)), notes.check_note(haiku_barca, big))
check("a real one-sentence Opus note is within the one-liner limit",
      not any("over the limit" in p for p in notes.check_note(opus_atletico, {**big, "home": "Atlético Madrid", "away": "Levante"})))
check("a standard note has room for several sentences", not any("over the limit" in p for p in notes.check_note(" ".join(["word"] * 60), STANDARD)))
check("raw minute symbols are rejected", any("minute symbols" in p for p in notes.check_note("Grimaldo scored (36') in the 2-0 win.", big))
      and any("minute symbols" in p for p in notes.check_note("Adli scored in 90+4 minutes.", big)))
check("written-out minutes are fine", not any("minute symbols" in p for p in notes.check_note("Grimaldo scored in the 36th minute.", big)))
check("hype words are rejected", any("hype word" in p for p in notes.check_note("Barcelona thrashed Alavés 6-1.", big)))
check("'still' implies continuity and needs a previous position", any("implies" in p for p in notes.check_note("Milan are still fifth.", big)))
check("'now' is just a time word and is allowed", not any("implies" in p for p in notes.check_note("Arsenal are now top of the table.", big)))
check("plain fallback note has the score and scorers", notes.plain_note(f).startswith("Chelsea 2-0 Manchester United.") and scorer in notes.plain_note(f))

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


def reply(payload, stop="end_turn", i=1000, o=200):
    text = payload if isinstance(payload, str) else json.dumps({"notes": [{"id": k, "note": v} for k, v in payload.items()]})
    return NS(stop_reason=stop, usage=NS(input_tokens=i, output_tokens=o), content=[NS(type="text", text=text)])


facts = [notes.match_facts(m, t, TABLE) for m, t in sel[:2]]
ids = [x["id"] for x in facts]


def faithful(fx):
    return f"{fx['home']} {fx['final_score']} {fx['away']}."


c = Fake([reply({x["id"]: faithful(x) for x in facts})])
res, usage = notes.write_notes(c, facts)
check("good replies are used, marked as Claude's", all(r["source"] == "claude" for r in res.values()) and len(c.calls) == 1, res)
check("usage is added up", usage == {"input": 1000, "output": 200})
call = c.calls[0]
check("request: model from settings, low effort, JSON schema, system prompt, no temperature",
      call["model"] == settings.CLAUDE_MODEL and call["output_config"]["effort"] == "low"
      and call["output_config"]["format"]["type"] == "json_schema" and "Use ONLY the facts" in call["system"]
      and "temperature" not in call and "thinking" not in call, list(call))
check("facts are sent as data, with the 'use only these' system rule", '"final_score"' in call["messages"][0]["content"])

bad = {ids[0]: "Chelsea won, and Mourinho was thrilled.", ids[1]: faithful(facts[1])}
c = Fake([reply(bad), reply({ids[0]: faithful(facts[0])})])
res, _ = notes.write_notes(c, facts)
check("a bad note is retried once, and the fixed version is used",
      len(c.calls) == 2 and res[ids[0]]["source"] == "claude" and res[ids[0]]["problems"] == [], (len(c.calls), res))
check("the retry tells Claude exactly what was wrong",
      "problems_with_your_last_note" in c.calls[1]["messages"][0]["content"] and "Mourinho" in c.calls[1]["messages"][0]["content"])
check("the retry asks only about the match that failed",
      f'"id": "{ids[0]}"' in c.calls[1]["messages"][0]["content"] and f'"id": "{ids[1]}"' not in c.calls[1]["messages"][0]["content"])
c = Fake([reply(bad), reply(bad)])
res, _ = notes.write_notes(c, facts)
check("still bad after the retry: the plain scoreline is used, and the problem is recorded",
      res[ids[0]]["source"] == "plain" and res[ids[0]]["problems"] and "Mourinho" not in res[ids[0]]["note"], res[ids[0]])
res, _ = notes.write_notes(Fake([RuntimeError("down")]), facts)
check("an API failure gives plain notes for everything", all(r["source"] == "plain" for r in res.values()) and len(res) == 2)
res, _ = notes.write_notes(Fake([reply({}, stop="refusal")]), facts)
check("a refusal gives plain notes", all(r["source"] == "plain" for r in res.values()))
res, _ = notes.write_notes(Fake([reply("this is not json")]), facts)
check("an unreadable reply gives plain notes", all(r["source"] == "plain" for r in res.values()))
res, _ = notes.write_notes(Fake([reply({ids[0]: faithful(facts[0])}), reply({})]), facts)
check("a match Claude skipped gets a plain note", res[ids[1]]["source"] == "plain" and res[ids[0]]["source"] == "claude")
check("cost estimate uses the model's prices", abs(notes.cost({"input": 1_000_000, "output": 1_000_000}, "claude-opus-5-5") - 24.0) < 1e-9)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
