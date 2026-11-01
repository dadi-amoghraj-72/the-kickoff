"""Offline tests for the international block. Run: .venv/bin/python scripts/test_international.py"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import international as intl, rankings  # noqa: E402
from kickoff.sources import espn, natleague as src  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
STAND = json.loads((FIX / "nl_standings.json").read_text())
EVENTS = json.loads((FIX / "nl_events.json").read_text())["events"]
TOP = {"source": "test list", "teams": ["Spain", "Argentina", "England", "France", "Portugal", "Netherlands", "Belgium", "Italy", "Norway", "Germany", "Denmark",
                                      "Croatia", "Austria", "Greece", "Sweden", "Turkey", "Switzerland", "Poland", "Serbia", "Ukraine"]}
rankings.load = lambda today, saved=None: (TOP, None)
requested = []


def synthetic(home, away, hs, as_, date_text):
    def side(ha, name, score):
        return {"homeAway": ha, "score": str(score), "team": {"id": name, "displayName": name, "abbreviation": name[:3].upper(), "shortDisplayName": name}}
    return {"id": f"{home}-{away}", "date": date_text, "season": {"slug": "qualifying"}, "status": {"type": {"completed": True, "description": "Full Time", "state": "post"}},
            "competitions": [{"competitors": [side("home", home, hs), side("away", away, as_)], "details": []}]}


EXTRA = {}  # {slug: events}


def fake(url, params=None, **kw):
    requested.append(url)
    if "uefa.nations/standings" in url:
        return STAND
    slug = url.split("/soccer/")[1].split("/")[0]
    if "/teams/" in url and "/schedule" in url:  # a team's upcoming fixtures, in ESPN's schedule shape
        team = url.split("/teams/")[1].split("/")[0]
        out = []
        for e in EVENTS:
            c = e["competitions"][0]
            if not e["status"]["type"]["completed"] and any(x["team"]["id"] == team for x in c["competitors"]):
                out.append({"id": e["id"], "date": e["date"], "league": {"slug": "uefa.nations", "name": "UEFA Nations League"},
                            "competitions": [{"competitors": [{"homeAway": x["homeAway"], "score": {"value": 0}, "team": x["team"]} for x in c["competitors"]],
                                              "status": {"type": {"state": "pre", "completed": False}}}]})
        return {"events": out}
    day = (params or {}).get("dates", "")
    if slug == "uefa.nations":
        return {"events": [e for e in EVENTS if e["date"][:10].replace("-", "") == day]}
    return {"events": [e for e in EXTRA.get(slug, []) if e["date"][:10].replace("-", "") == day]}


espn.get_json = fake
src.get_json = fake
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# ---- A break: the day after matchday 4 ----
NOW = datetime(2026, 10, 5, 0, 30, tzinfo=timezone.utc)
out = intl.run(date(2026, 10, 5), NOW)
h = out["html"]
check("after a matchday the block appears, headed 'International Football' then 'UEFA Nations League'", h.startswith("<h3>International Football</h3><h3>UEFA Nations League</h3>"), h[:120])
check("it has the four League A group tables and some League B ones", all(f"Group A{i} · League A" in h for i in (1, 2, 3, 4)) and "League B" in h)
check("REGRESSION: after matchday 4 no group is called finished: every shown group has two matchdays left", "The group is finished" not in h and h.count("2 matchdays left") >= 4, h.count("2 matchdays left"))
check("it has the matchday's scoreboard with scorers", '<li><span class="h">' in h and 'class="gh"' in h)
check("no friendlies were looked at", not any("friendly" in u for u in requested), [u for u in requested if "friendly" in u][:2])
check("nothing else broke: no problems reported", out["problems"] == [], out["problems"])

# ---- Quiet days ----
requested.clear()
quiet = intl.run(date(2026, 10, 20), datetime(2026, 10, 20, 0, 30, tzinfo=timezone.utc))
check("in the weeks between breaks there is no block", quiet["html"] == "")
check("and the Nations League standings are never even requested", not any("standings" in u for u in requested), len(requested))

# ---- The morning of a matchday: fixtures within 30 hours ----
before = intl.run(date(2026, 11, 12), datetime(2026, 11, 12, 0, 30, tzinfo=timezone.utc))
check("on a matchday morning the block appears before any result exists, with stake lines", "UEFA Nations League" in before["html"] and "matchday" in before["html"] and "left" in before["html"], before["html"][:300])
check("with no result yet there is no scoreboard", 'class="scores"' not in before["html"])
far = intl.run(date(2026, 11, 8), datetime(2026, 11, 8, 0, 30, tzinfo=timezone.utc))
check("four days before the break: nothing", far["html"] == "")

# ---- Other competitive internationals ----
EXTRA["fifa.worldq.afc"] = [synthetic("Singapore", "Laos", 2, 0, "2026-10-04T12:00Z"), synthetic("Nepal", "Bhutan", 1, 1, "2026-10-04T10:00Z")]
EXTRA["uefa.euroq"] = [synthetic("Denmark", "Faroe Islands", 3, 0, "2026-10-04T18:45Z")]
o = intl.run(date(2026, 10, 5), NOW)["html"]
check("a Singapore qualifier is shown, under its competition", "World Cup qualifiers (Asia)" in o and "Singapore" in o and "Laos" in o)
check("a qualifier between two sides outside the top 30, Singapore and India is not shown", "Nepal" not in o and "Bhutan" not in o)
check("a top-30 side (Denmark) in a European qualifier is shown", "European Championship qualifiers" in o and "Denmark" in o)
EXTRA["fifa.worldq.afc"] = [synthetic("India", "Bhutan", 1, 0, "2026-10-04T12:00Z")]
check("India is always wanted", "India" in intl.run(date(2026, 10, 5), NOW)["html"])
EXTRA.clear()
only = intl.run(date(2026, 10, 20), datetime(2026, 10, 20, 0, 30, tzinfo=timezone.utc))
check("outside a break with no qualifiers, nothing", only["html"] == "")
EXTRA["uefa.euroq"] = [synthetic("Denmark", "Faroe Islands", 3, 0, "2026-10-19T18:45Z")]
qual = intl.run(date(2026, 10, 20), datetime(2026, 10, 20, 0, 30, tzinfo=timezone.utc))
check("a qualifier alone still earns a block, without any Nations League tables", "Denmark" in qual["html"] and "UEFA Nations League" not in qual["html"], qual["html"][:200])
EXTRA.clear()

# ---- Failures ----
def boom(today, saved=None):
    raise RuntimeError("elo down")


rankings.load = boom
nr = intl.run(date(2026, 10, 5), NOW)
check("if the ranking fails, League A is still shown and the problem is recorded", "Group A1" in nr["html"] and "League B" not in nr["html"] and any("ranking" in p for p in nr["problems"]), nr["problems"])
rankings.load = lambda today, saved=None: (TOP, None)
espn.get_json = lambda *a, **k: (_ for _ in ()).throw(__import__("kickoff.http", fromlist=["x"]).SourceError("HTTP 500"))
src.get_json = espn.get_json
dead = intl.run(date(2026, 10, 5), NOW)
check("with every source down it returns nothing and does not crash", dead["html"] == "")
W = lambda h, a, t: intl.wanted({"home": {"name": h}, "away": {"name": a}}, t)  # noqa: E731
check("wanted: a top-30 side counts", W("Spain", "Laos", TOP))
check("wanted: Singapore counts, whoever they play", W("Laos", "Singapore", TOP))
check("wanted: two sides outside the top 30, Singapore and India do not count", not W("Laos", "Nepal", TOP))
check("wanted: with no ranking available, Spain is unknown but India is still always wanted", not W("Spain", "Nepal", None) and W("India", "Nepal", None))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
