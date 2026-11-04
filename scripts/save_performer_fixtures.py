"""Re-save the test fixtures for the soccer best performers from ESPN (real data, no key). Run: .venv/bin/python scripts/save_performer_fixtures.py
Saves tests/fixtures/espn_performers.json: for the Champions League night of 3 November 2026 and a Premier League matchday, each match's ESPN summary
trimmed to what espn.get_player_stats reads (the rosters with each player's name, position and stat counts)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import http  # noqa: E402

SITE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/"
out = {}
for lg, days in (("uefa.champions", ("20261103",)), ("eng.1", ("20261031", "20261101"))):
    sb = {"events": []}
    for day in days:
        sb["events"] += http.get_json(SITE.format(lg=lg) + f"scoreboard?dates={day}")["events"]
    out[lg] = {"scoreboard": {"events": [{"id": e["id"], "name": e["name"], "status": e["status"], "competitions": [{"competitors": [{"homeAway": c["homeAway"], "score": c.get("score"), "team": {k: c["team"].get(k) for k in ("id", "displayName", "abbreviation", "shortDisplayName")}} for c in e["competitions"][0]["competitors"]]}]} for e in sb["events"]]}, "summaries": {}}
    for e in sb["events"]:
        j = http.get_json(SITE.format(lg=lg) + f"summary?event={e['id']}")
        out[lg]["summaries"][e["id"]] = {"rosters": [{"team": {k: s["team"].get(k) for k in ("id", "displayName", "abbreviation")}, "roster": [
            {"starter": p.get("starter"), "athlete": {k: p["athlete"].get(k) for k in ("id", "displayName", "shortName")}, "position": {"abbreviation": (p.get("position") or {}).get("abbreviation")},
             "stats": [{"name": x["name"], "value": x.get("value")} for x in p.get("stats", [])]} for p in s.get("roster", [])]} for s in j.get("rosters", [])]}
(ROOT / "tests" / "fixtures" / "espn_performers.json").write_text(json.dumps(out))
print("saved", {lg: len(v["summaries"]) for lg, v in out.items()})
