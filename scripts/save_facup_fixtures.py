"""Re-save the FA Cup test fixtures from ESPN (real data, no key). Run: .venv/bin/python scripts/save_facup_fixtures.py
Saves tests/fixtures/espn_facup.json: the scoreboards of Saturday 7 November 2026 (first round: 33 ties) and Saturday 10 January 2026 (third round: 18 ties), trimmed
to what espn.parse_match reads."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import http  # noqa: E402

out = {}
for day in ("20261107", "20260110"):
    sb = http.get_json(f"https://site.api.espn.com/apis/site/v2/sports/soccer/eng.fa/scoreboard?dates={day}")
    events = []
    for e in sb["events"]:
        c = e["competitions"][0]
        events.append({"id": e["id"], "date": e["date"], "season": e.get("season"), "status": {"type": {"completed": e["status"]["type"].get("completed"), "description": e["status"]["type"].get("description"), "name": e["status"]["type"].get("name")}},
                       "competitions": [{"competitors": [{"homeAway": x["homeAway"], "score": x.get("score"), "team": {k: x["team"].get(k) for k in ("id", "displayName", "abbreviation", "shortDisplayName")}} for x in c["competitors"]],
                                         "details": c.get("details", [])}]})
    out[day] = {"events": events}
(ROOT / "tests" / "fixtures" / "espn_facup.json").write_text(json.dumps(out))
print("saved", {d: len(v["events"]) for d, v in out.items()})
