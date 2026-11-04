"""Offline tests for the soccer best performers on real ESPN data (the Champions League night of 3 November 2026 and the Premier League matchdays of 31 October
and 1 November). Run: .venv/bin/python scripts/test_performers.py"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import performers  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FX = json.loads((ROOT / "tests" / "fixtures" / "espn_performers.json").read_text())
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


def fake_get_json(url, params=None, **kw):
    lg = "uefa.champions" if "uefa.champions" in url else "eng.1"
    return FX[lg]["summaries"][params["event"]]


espn.get_json = fake_get_json
text = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()  # noqa: E731


def raw_counts(lg, event):
    """Independent read of the raw summary: {athlete id: {stat name: value}} and the athlete names."""
    out, names = {}, {}
    for side in FX[lg]["summaries"][event]["rosters"]:
        for p in side["roster"]:
            out[p["athlete"]["id"]] = {x["name"]: x["value"] or 0 for x in p["stats"]}
            names[p["athlete"]["id"]] = p["athlete"]["shortName"]
    return out, names


def matches(lg):
    return [{"id": e["id"], "completed": e["status"]["type"]["name"] in ("STATUS_FULL_TIME", "STATUS_FINAL")} for e in FX[lg]["scoreboard"]["events"]]


# ---- Reading ESPN's summary ----
psg = next(e for e in FX["uefa.champions"]["scoreboard"]["events"] if "Villarreal" in e["name"])
players = espn.get_player_stats("uefa.champions", psg["id"])
raw, names = raw_counts("uefa.champions", psg["id"])
ruiz = next(p for p in players if p["short"] == "F. Ruiz")
check("the player stats come straight from ESPN's counts: Ruiz of PSG scored 2 goals in the 6-0 at Villarreal (the raw totalGoals), and the keeper, starter flag and team are read", ruiz["goals"] == 2 == int(raw[ruiz["id"]]["totalGoals"]) and ruiz["team_abbr"] == "PSG" and ruiz["starter"], ruiz)
sb_score = {c["team"]["abbreviation"]: int(c["score"]) for c in psg["competitions"][0]["competitors"]}
check("sanity on the whole match: the goals the players are credited with (plus own goals) add up to the final score, 0-6", sum(p["goals"] for p in players) + sum(p["own_goals"] for p in players) == sum(sb_score.values()) == 6, (sb_score, sum(p["goals"] for p in players)))
check("the players of both teams are there, with exactly one starting goalkeeper each", len(players) >= 36 and sum(1 for p in players if p["pos"] == "G" and p["starter"]) == 2, len(players))

# ---- The Champions League night ----
cl = matches("uefa.champions")
top = performers.best("uefa.champions", cl)
all_players = [p for m in cl for p in espn.get_player_stats("uefa.champions", m["id"])]
most_goals = max(p["goals"] for p in all_players)
check("three best performers of the night, best first, each once", len(top) == 3 and len({x["id"] for x in top}) == 3 and [x["score"] for x in top] == sorted((x["score"] for x in top), reverse=True), top)
check(f"the best performer is a player with the most goals of the night, found separately from the raw counts ({most_goals})", top[0]["id"] in {p["id"] for p in all_players if p["goals"] == most_goals}, (top[0], most_goals))
check("every listed player really scored, assisted or is a goalkeeper (nobody is there for a quiet night), checked against the raw counts", all(raw_counts("uefa.champions", m["id"])[0].get(x["id"], {}).get("totalGoals", 0) + raw_counts("uefa.champions", m["id"])[0].get(x["id"], {}).get("goalAssists", 0) > 0 or "saves" in x["text"] for x in top for m in cl if x["id"] in raw_counts("uefa.champions", m["id"])[0]))
check("a line reads 'F. Ruiz (PSG): 2 goals' with our code for a listed club (PSG, BAR, INT...) and ESPN's short name", any(re.fullmatch(r"[A-Z]\. [^()]+ \([A-Z]{2,4}\): \d goals?(, \d assists?)?", x["text"]) for x in top) and any("(PSG)" in x["text"] or "(BAR)" in x["text"] or "(INT)" in x["text"] or "(MUN)" in x["text"] for x in top), [x["text"] for x in top])

# ---- The Premier League days ----
pl = matches("eng.1")
ptop = performers.best("eng.1", pl)
check("the Premier League gives up to three, each a real contributor, and never more than three", 1 <= len(ptop) <= 3 and all(x["score"] >= performers.MIN_SCORE for x in ptop), ptop)

# ---- The scoring rules, on made-up players ----
P = lambda **k: {"id": k.pop("id", "x"), "name": "Name", "short": "N. Name", "team_id": "1", "team_abbr": "ABC", "team": "ABC FC", "pos": "F", "starter": True, "goals": 0, "assists": 0, "shots_on": 0, "saves": 0, "conceded": 0, "yellow": 0, "red": 0, "own_goals": 0, **k}  # noqa: E731
check("a brace beats a goal and an assist, which beats a single goal; shots on target only break ties", performers.score(P(goals=2)) > performers.score(P(goals=1, assists=1)) > performers.score(P(goals=1)) > performers.score(P(goals=0, assists=1, shots_on=2)))
tie = performers.best("lg", [{"id": "t"}], fetch=lambda lg, i: [P(id="o", short="O. Other", goals=2, team_id="9999"), P(id="p", short="P. Psg", goals=2, team_id="160", team_abbr="PSG", team="Paris Saint-Germain")])
check("on equal numbers one of D's listed clubs (PSG here) is ranked first, but a clearly better performance from another club still wins", tie[0]["text"].startswith("P. Psg") and performers.best("lg", [{"id": "t"}], fetch=lambda lg, i: [P(id="o", short="O. Other", goals=3, team_id="9999"), P(id="p", short="P. Psg", goals=2, team_id="160")])[0]["text"].startswith("O. Other"))
check("a goalkeeper counts on saves and a clean sheet only from 4 saves; a keeper with 2 saves and a clean sheet is nobody; a substitute keeper never counts", performers.score(P(pos="G", saves=6, conceded=0)) >= performers.MIN_SCORE and performers.score(P(pos="G", saves=2, conceded=0)) == 0 and performers.score(P(pos="G", saves=9, starter=False)) == 0)
check("a red card or an own goal costs: a scorer sent off is worth less than one who stayed on", performers.score(P(goals=1, red=1)) < performers.score(P(goals=1)) and performers.score(P(goals=1, own_goals=1)) < performers.score(P(goals=1)))
fake = {"m1": [P(id="a", short="A. One", goals=1), P(id="b", short="B. Two", goals=3), P(id="c", short="C. Three", assists=2), P(id="d", short="D. Four", goals=1, assists=1), P(id="e", short="E. Quiet", shots_on=5, saves=0)]}
tb = performers.best("lg", [{"id": "m1"}], fetch=lambda lg, i: fake[i])
check("best: the top three by score (3 goals, goal and assist, 2 assists), the single scorer and the quiet player left out", [x["text"].split(" (")[0] for x in tb] == ["B. Two", "D. Four", "C. Three"], tb)
check("a night where nobody did anything gives an empty list, and a match whose summary fails is skipped without stopping the rest",
      performers.best("lg", [{"id": "m1"}], fetch=lambda lg, i: [P(shots_on=3)]) == [] and performers.best("lg", [{"id": "bad"}, {"id": "m1"}], fetch=lambda lg, i: fake[i] if i == "m1" else (_ for _ in ()).throw(OSError("down")))[0]["text"].startswith("B. Two"))
check("an unfinished match is ignored, and a player appears once even if two matches list him", performers.best("lg", [{"id": "m1", "completed": False}], fetch=lambda lg, i: fake[i]) == [] and len(performers.best("lg", [{"id": "m1"}, {"id": "m1"}], fetch=lambda lg, i: fake[i], limit=10)) == 4)
check("the keeper line says saves and clean sheet", performers.line(P(pos="G", short="D. Vásquez", team_abbr="ROM", team="AS Roma", saves=6, conceded=0)) == "D. Vásquez (ROM): 6 saves, clean sheet")

# ---- The page ----
h = performers.html(top)
check("the block is a 'Best performers' heading and a list in the house style with the figures in gold; nothing when nobody qualified", h.startswith("<h4>Best performers</h4>") and h.count('class="pl"') == 3 and '<span class="n">' in h and performers.html([]) == "")
check("it reads cleanly as text", text(h).startswith("Best performers ") and "goal" in text(h), text(h))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
