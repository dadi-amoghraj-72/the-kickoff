"""Offline tests for the Arsenal and Arsenal Women module. Run: .venv/bin/python scripts/test_focus.py"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import focus, notes  # noqa: E402
from kickoff.sources import espn  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
load = lambda n: json.loads((FIX / n).read_text())  # noqa: E731


def fake_get_json(url, params=None, **kw):
    if "/summary" in url:
        return load("arsenal_summary_header.json")
    women = "/teams/19973/" in url
    if params and params.get("fixture"):
        return load("women_fixtures.json" if women else "arsenal_fixtures.json")
    if women:
        return load("women_schedule.json")
    return load("arsenal_schedule_pl.json") if "/eng.1/" in url else load("arsenal_schedule_all.json")


espn.get_json = fake_get_json
results = []
NOW = datetime(2026, 11, 2, 0, 30, tzinfo=timezone.utc)


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


# ---- Games ----
games = espn.get_team_games("359", "eng.1", today=date(2026, 11, 2))
ids = [g["id"] for g in games]
check("games from both lists are merged with no duplicates", len(ids) == len(set(ids)) and len(games) >= 18, len(games))
liv = [g for g in games if g["home"]["abbr"] == "LIV"]
check("the Liverpool result is found (only the Premier League list has it)", len(liv) == 1 and liv[0]["completed"]
      and (liv[0]["home_score"], liv[0]["away_score"]) == (0, 1), liv)
check("games come out oldest first", [g["kickoff"] for g in games] == sorted(g["kickoff"] for g in games))
check("Champions League and cup games are included, not just the league",
      {"uefa.champions"} <= {g["league"] for g in games} and any("Carabao" in g["competition"] for g in games), {g["league"] for g in games})

# ---- Form (worked out by hand from the real fixture list) ----
fm = focus.form(games, "359")
check("unbeaten run is 7 (since the 3-0 loss at Brighton on 19 Sep)", fm["unbeaten_run"] == 7, fm)
check("last five: 3 won, 2 drawn, 0 lost", fm["last_five_record"] == "3 won, 2 drawn, 0 lost", fm)
friendly_loss = {"id": "x", "kickoff": "2026-11-01T20:00Z", "competition": "2026 Club Friendly", "completed": True,
                 "home": {"id": "359"}, "away": {"id": "9"}, "home_score": 0, "away_score": 3}
check("a lost friendly does not break the unbeaten run", focus.form(games + [friendly_loss], "359")["unbeaten_run"] == 7)
check("form 'up to' an earlier game ignores later results", focus.form(games, "359", upto=games[7])["unbeaten_run"] < 7)

# ---- This edition's result ----
tables = {}
out = focus.build(focus.ARSENAL, date(2026, 11, 2), tables, now=NOW)
check("Monday's edition holds the Sunday Liverpool match, and nothing else", len(out["facts"]) == 1, len(out["facts"]))
f = out["facts"][0]
check("facts: Liverpool 0-1 Arsenal, Arsenal's perspective", (f["home"], f["away"], f["final_score"], f["focus_team"]) == ("Liverpool", "Arsenal", "0-1", "Arsenal"), f)
g = f["goals"][0]
check("facts: scorer, assist-maker and the side they played for", (g["scorer"], g["assist"], g["for"]) == ("Kai Havertz", "Declan Rice", "Arsenal"), g)
check("facts hold the form, but not the fixtures (code writes those)", "form" in f and "next" not in json.dumps(f).lower())
check("an edition two days on has no Arsenal match", focus.build(focus.ARSENAL, date(2026, 11, 3), tables, now=NOW)["facts"] == [])

# ---- Next up ----
nxt = out["next"]
check("next up: Slavia Prague away in the Champions League, in Singapore time",
      nxt[0]["opponent"] == "Slavia Prague" and nxt[0]["competition"] == "UEFA Champions League" and nxt[0]["venue"] == "away" and nxt[0]["when"] == "Thu 5 Nov, 4am SGT", nxt[0])
check("then Hull at home on Saturday night", nxt[1]["venue"] == "home" and nxt[1]["when"] == "Sat 7 Nov, 11pm SGT", nxt[1])
later = focus.next_up(espn.get_team_games("359", "eng.1", upcoming=True), "359", datetime(2026, 11, 8, tzinfo=timezone.utc))
check("fixtures already past are skipped: from 8 Nov the next is Newcastle away (kick-off 21 Nov UTC = 22 Nov in Singapore)",
      later[0]["opponent"] == "Newcastle United" and later[0]["when"] == "Sun 22 Nov, 1:30am SGT", later[0])
check("kick-off times convert across midnight", focus.when_sgt("2026-11-04T20:00Z") == "Thu 5 Nov, 4am SGT"
      and focus.when_sgt("2026-11-07T15:00Z") == "Sat 7 Nov, 11pm SGT" and focus.when_sgt("2026-11-01T16:30Z") == "Mon 2 Nov, 12:30am SGT")
html = focus.next_up_html(nxt)
check("the next-up block: a heading, then one gold-diamond bullet a game, 'Sat 7 Nov, 11pm · Hull City (home) · EPL', the next three, in date order",
      html.startswith("<p><strong>Next up</strong></p><ul") and html.count("<li>") == 3 and "<li>Thu 5 Nov, 4am · Slavia Prague (away) · CL</li>" in html and "<li>Sat 7 Nov, 11pm · Hull City (home) · EPL</li>" in html, html)
check("competitions are short (EPL, CL, LC) except the FA Cup, and the Women's ones keep their names", [focus.short_comp(x) for x in ("English Premier League", "UEFA Champions League", "English League Cup", "Carabao Cup", "FA Cup", "UEFA Women's Champions League")] == ["EPL", "CL", "LC", "LC", "FA Cup", "UEFA Women's Champions League"])
check("no fixtures, no line", focus.next_up_html([]) == "")

# ---- Arsenal Women ----
wg = espn.get_team_games("19973", "eng.w.1", today=date(2026, 11, 2))
check("Women's games are read the same way", len(wg) > 0 and all(g["completed"] for g in wg), len(wg))
wn = focus.next_up(espn.get_team_games("19973", "eng.w.1", upcoming=True), "19973", NOW)
check("Women's next fixtures have Singapore times", len(wn) >= 2 and all(x["when"].endswith("SGT") for x in wn), wn)

# ---- A note through the safety check ----
good = ("Arsenal won 1-0 at Liverpool, Kai Havertz scoring in the 16th minute from a Declan Rice cross. "
        "It stretches the unbeaten run to 7 games across all competitions, with 3 wins and 2 draws in the last five.")
check("a faithful, form-aware note passes the checker", notes.check_note(good, f) == [], notes.check_note(good, f))
check("an invented streak is caught", any("number 12" in p for p in notes.check_note("Arsenal are unbeaten in 12 games.", f)))
check("the Arsenal length allows a full paragraph", notes.LIMITS[notes.TIERS["arsenal"][0]] >= 120)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
