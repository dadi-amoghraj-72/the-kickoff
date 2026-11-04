"""Re-save the test fixture for ESPN's cricket JSON feed (real data, no key). Run: .venv/bin/python scripts/save_cricket_feed_fixtures.py
Saves tests/fixtures/espn_cricket_feed.json: the header scoreboard (every current cricket series with its matches) and the scoreboards of two series: India's tour of
New Zealand (24469) and the Women's Big Bash League (21284), with links, logos and other bulk removed."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import http  # noqa: E402

DROP = {"links", "logos", "logo", "headshot", "geoBroadcasts", "broadcasts", "broadcast", "highlights", "venue", "officials", "notes"}


def slim(x):
    if isinstance(x, dict):
        return {k: slim(v) for k, v in x.items() if k not in DROP}
    if isinstance(x, list):
        return [slim(v) for v in x]
    return x


head = http.get_json("https://site.web.api.espn.com/apis/v2/scoreboard/header?sport=cricket&lang=en&region=us")
out = {"header": slim(head), "series": {sid: slim(http.get_json(f"https://site.api.espn.com/apis/site/v2/sports/cricket/{sid}/scoreboard")) for sid in ("24469", "21284")}}
(ROOT / "tests" / "fixtures" / "espn_cricket_feed.json").write_text(json.dumps(out))
print("saved", len(json.dumps(out)), "bytes;", [(x["id"], x["name"]) for x in head["sports"][0]["leagues"]][:12])
