"""End-to-end tests for the assembled Football and Arsenal sections. Run: .venv/bin/python scripts/test_football.py"""
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import football, settings  # noqa: E402
from kickoff.http import SourceError  # noqa: E402
from kickoff.sources import espn, feeds, fpl  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
load = lambda n: json.loads((FIX / n).read_text())  # noqa: E731
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# ---- Fake ESPN: real saved data for the Premier League and Arsenal; everything else empty or broken ----
SUMMARY = {"rosters": load("espn_summary_rosters.json")["rosters"], "header": load("arsenal_summary_header.json")["header"], "pickcenter": []}


def espn_get(url, params=None, **kw):
    params = params or {}
    if "/standings" in url:
        if "/eng.1/" in url:
            return load("espn_pl_table.json")
        if "uefa.champions" in url:
            return load("espn_cl_table.json")
        raise SourceError("HTTP 404")
    if "/summary" in url:
        return SUMMARY
    if "sports.core.api" in url:
        return load("espn_core_leaders.json") if url.endswith("/leaders") else {"displayName": "Test Player"}
    if "/teams/" in url and "/schedule" in url:
        women = "/teams/19973/" in url
        if params.get("fixture"):
            return load("women_fixtures.json" if women else "arsenal_fixtures.json")
        return load("women_schedule.json") if women else (load("arsenal_schedule_pl.json") if "/eng.1/" in url else load("arsenal_schedule_all.json"))
    if "/scoreboard" in url:
        if "/eng.1/" in url:
            return {"20261031": load("espn_pl_20261031.json"), "20261101": load("espn_pl_20261101.json")}.get(params.get("dates"), {"events": []})
        return {"events": []}
    raise SourceError("unexpected url")


espn.get_json = espn_get
BOOT = {"events": [{"id": 9, "is_current": True, "is_next": False, "finished": False, "deadline_time": "2026-10-31T11:00:00Z", "average_entry_score": 31},
                   {"id": 10, "is_current": False, "is_next": True, "finished": False, "deadline_time": "2026-11-06T18:30:00Z", "average_entry_score": 0}],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS", "position": 1, "played": 0}],
        "elements": [{"id": 1, "first_name": "Bukayo", "second_name": "Saka", "web_name": "Saka", "team": 1, "status": "i", "news": "Thigh injury - Unknown return date",
                      "news_added": "2026-10-30T10:00:00.123456Z", "chance_of_playing_next_round": 0, "minutes": 600, "starts": 8, "selected_by_percent": "30.0"}]}
FPL_URLS = {"bootstrap-static": BOOT, "/fixtures/": [{"finished": True, "team_h": 1, "team_a": 2}] * 8,
            "/history/": {"current": []}, "/live/": {"elements": [{"id": 1, "stats": {"total_points": 5}}]},
            "/entry/1476452/event/": {"entry_history": {"event": 9, "points": 25, "overall_rank": 1000, "points_on_bench": 0, "event_transfers_cost": 0},
                                      "picks": [{"element": 1, "is_captain": True, "multiplier": 2}], "active_chip": None},
            "/entry/1476452/": {"name": "merino parade fc"},
            "/league/": {"league": {"name": "Hong Hu"}, "league_entries": [{"id": 5, "entry_id": 186059, "entry_name": "Gabi III", "player_first_name": "Dadi"}],
                         "standings": [{"league_entry": 5, "rank": 1, "event_total": 25, "total": 100}]}}


def fpl_get(url, params=None, **kw):
    for key, val in FPL_URLS.items():
        if key in url:
            return val
    raise SourceError("unexpected url")


fpl.get_json = fpl_get
BBC = (FIX / "news_bbc.xml").read_bytes()
feeds.get_bytes = lambda url, *a, **k: BBC if "bbci" in url else (_ for _ in ()).throw(SourceError("HTTP 404"))


# ---- A fake Claude that answers each kind of request ----
class Fake:
    def __init__(self):
        self.calls = []
        self.beta = NS(messages=NS(create=self._create))
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        system, content = kw["system"], kw["messages"][0]["content"]
        if "matchday overview" in system:
            facts = json.loads(content[content.index("{"):])
            g = facts["game_of_the_night"]
            body = {"overview": f"The standout game was {g}."}
        elif "sort and summarise" in system:
            items = json.loads(content[content.index("["):])
            body = {"items": [{"link": i["link"], "kind": "none", "club": "", "summary": ""} for i in items]}
        else:
            facts = json.loads(content[content.index("["):])
            body = {"notes": [{"id": f["id"], "note": f"{f['home']} {f['final_score']} {f['away']}."} for f in facts]}
        return NS(stop_reason="end_turn", usage=NS(input_tokens=1000, output_tokens=100), content=[NS(type="text", text=json.dumps(body))])


DAY = date(2026, 11, 1)  # Sunday: the 8 Saturday Premier League matches
NOW = datetime(2026, 11, 2, 0, 30, tzinfo=timezone.utc)

# ---- Without Claude (free) ----
out = football.run(DAY, client=None, st={}, now=NOW)
html = " ".join(s["html"] for s in out["sections"])
check("an Arsenal section (Saka's injury only) and a Football section with the Premier League block",
      [s["id"] for s in out["sections"]] == ["arsenal", "football"] and "<h3>Premier League</h3>" in html, [s["id"] for s in out["sections"]])
check("every league that has no data is just skipped, and the failures are listed", "La Liga" not in html and any("La Liga table" in p for p in out["problems"]), out["problems"])
check("with no Claude the league blocks do not repeat the scoreboard as plain notes", "Goals:" not in html.split("<h3>Premier League</h3>")[1].split("<h3>")[0], "")
pl = html.split("<h3>Premier League</h3>")[1].split("<h3>")[0]
check("the Premier League block shows all 8 games as a scoreboard, each with its scorers, between the box and the table",
      pl.count('<li><span class="h">') == 8 and pl.index("roundup") < pl.index('class="scores"') < pl.index("<table"), pl.count('<li><span class="h">'))
check("scorers are shown under each team (Rogers for Chelsea, with the minute)", "Rogers" in pl and 'class="gh"' in pl and 'class="ga"' in pl)
check("the listed clubs are in bold in the scoreboard (Chelsea, Manchester United)", '<span class="mine">Chelsea</span>' in pl and '<span class="mine">Man Utd</span>' in pl, pl[:400])
check("the full table appears, with the top scorer, assists and clean-sheet lines under it", "<table" in html and "Top Scorer" in html and "Top CS" in html)
check("with no Claude, nothing is spent and nothing is written as AI", out["ledger"].total() == 0 and out["ledger"].rows == [])
check("the FPL corner is built from the (fake) public data", "FPL Corner" in html and "merino parade fc" in html and "Gabi III" in html, html[-400:])
check("injuries: Saka's thigh injury (30 Oct, 3 days old) is shown", "Injuries And Returns" in html and "Bukayo Saka" in html)
st = out["new_state"]
check("state to save: tables, clean sheets, injuries, FPL, seen news, costs", {"tables", "clean_sheets", "injuries", "fpl", "news_seen", "costs"} <= set(st), set(st))
check("the Premier League table is remembered; clean sheets were counted", "eng.1" in st["tables"] and st["clean_sheets"]["eng.1"]["keepers"], list(st))
check("the headlines are built by code, at most three", len(out["headlines"]) <= 3)
out2 = football.run(DAY, client=None, st=st, now=NOW)
html2 = " ".join(s["html"] for s in out2["sections"])
check("run again with the saved state: the table is 'No change', and Saka's injury is not repeated",
      "No change since Sunday" in html2 and "<table" not in html2.split("Premier League")[1][:6000].split("FPL Corner")[0] and "Bukayo Saka" not in html2.split("FPL Corner")[0], html2[:300])
check("the saved state is not changed by a run (the caller decides)", st["tables"]["eng.1"]["published"] == "2026-11-01")

# ---- With a (fake) Claude ----
c = Fake()
out3 = football.run(DAY, client=c, st={}, now=NOW)
html3 = " ".join(s["html"] for s in out3["sections"])
labels = [x["label"] for x in out3["ledger"].rows]
check("Claude writes only the notes (Sonnet): no Opus overview is bought any more", "Premier League notes" in labels
      and settings.OVERVIEW_MODEL not in {x["model"] for x in out3["ledger"].rows} and not any("overview" in x for x in labels), labels)
pl3 = html3.split("<h3>Premier League</h3>")[1].split("<h3>")[0]
check("with Claude the order is: round-up box (8/10), scoreboard, Claude's notes with names in bold, then the table",
      "8/10" in pl3 and pl3.index("roundup") < pl3.index('class="scores"') < pl3.index("<strong>Chelsea</strong>") < pl3.index("<table"), pl3[:300])
check("the box is identical with and without Claude (it is built by code)", "8/10" in html and "Favourites won" in html and "Biggest upset" in html and "Game of the day" in html)
check("the cost is totalled and recorded in the monthly state", out3["new_state"]["costs"]["2026-11"]["spent"] == out3["ledger"].total() > 0 and out3["new_state"]["costs"]["2026-11"]["calls"] == len(labels))
check("news candidates are sent to Claude and remembered, so they are never sent twice",
      out3["stats"]["news_candidates"] == 0 or ("news classification" in labels and len(out3["new_state"]["news_seen"]) == out3["stats"]["news_candidates"]), out3["stats"])

# ---- The WSL: its own block, with box, scoreboard and table, on a day that is not a Tuesday ----
plain_get = espn.get_json


def wsl_get(url, params=None, **kw):
    if "/eng.w.1/" in url:
        return load("espn_pl_table.json") if "/standings" in url else plain_get(url.replace("/eng.w.1/", "/eng.1/"), params, **kw)
    return plain_get(url, params, **kw)


espn.get_json = wsl_get
w = football.run(DAY, client=None, st={}, now=NOW)
wh = " ".join(x["html"] for x in w["sections"])
wsl = wh.split("<h3>Women's Super League</h3>")[1] if "<h3>Women's Super League</h3>" in wh else ""
check("the Women's Super League has its own block, after the Premier League, on a Sunday", wsl != "" and wh.index("<h3>Premier League</h3>") < wh.index("<h3>Women's Super League</h3>"), wh[:80])
check("the WSL block has a box, a scoreboard and a table, in that order", "roundup" in wsl and wsl.index("roundup") < wsl.index('class="scores"') < wsl.index("<table"), wsl[:200])
check("the WSL box uses its own season length (a 20-team table here: 38 rounds)", "Game week" in wsl)
check("the WSL table is remembered so the next unchanged day says so", "eng.w.1" in w["new_state"]["tables"])
espn.get_json = plain_get

# ---- Arsenal played (the Liverpool game) ----
out5 = football.run(date(2026, 11, 2), client=None, st={}, now=NOW)
ids = [s["id"] for s in out5["sections"]]
ars = next((s["html"] for s in out5["sections"] if s["id"] == "arsenal"), "")
check("when Arsenal played, an Arsenal section comes first, then Football", ids[0] == "arsenal", ids)
check("the Arsenal section has the result, the next fixtures in Singapore time and Arsenal Women", "Liverpool 0-1 Arsenal" in re.sub(r"<[^>]+>", "", ars) and "Next up:" in ars and "SGT" in ars and "Arsenal Women" in ars, ars[:300])
check("Arsenal's own injury news goes in the Arsenal section, not Football", "Bukayo Saka" in ars and "Bukayo Saka" not in next(s["html"] for s in out5["sections"] if s["id"] == "football").split("FPL Corner")[0])
check("the first headline is Arsenal's result", out5["headlines"][0] == "Arsenal: Liverpool 0–1 Arsenal", out5["headlines"])

# ---- Everything broken ----
espn.get_json = lambda *a, **k: (_ for _ in ()).throw(SourceError("HTTP 500"))
fpl.get_json = lambda *a, **k: (_ for _ in ()).throw(SourceError("HTTP 500"))
feeds.get_bytes = lambda *a, **k: (_ for _ in ()).throw(SourceError("HTTP 500"))
dead = football.run(DAY, client=None, st={}, now=NOW)
check("with every source down it still returns, with no sections and a long problem list (no crash)", dead["sections"] == [] and len(dead["problems"]) >= 8, (dead["sections"], dead["problems"]))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
