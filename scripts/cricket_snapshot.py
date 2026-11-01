"""Save the current CricketData.org match list (about 3 calls) so we can see what is really there. No keys are saved.

  .venv/bin/python scripts/cricket_snapshot.py 2>&1 | tee preview/cricket-snapshot.log
  .venv/bin/python scripts/cricket_snapshot.py --scorecard <match id>      also saves one scorecard (10 calls)
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))
from kickoff.envfile import load_env  # noqa: E402

load_env()
KEY = os.environ.get("CRICKET_DATA_API_KEY", "")
BASE = "https://api.cricapi.com/v1"


def call(path, **params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode({'apikey': KEY, **params})}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "TheKickoff/1.0"}), timeout=30) as resp:
            return json.load(resp)
    except (urllib.error.URLError, ValueError) as e:
        print("request failed:", type(e).__name__)
        return None


if not KEY:
    sys.exit("CRICKET_DATA_API_KEY is empty in .env")
out = ROOT / "preview"
out.mkdir(exist_ok=True)
rows, used = [], None
for offset in (0, 25, 50, 75):
    body = call("currentMatches", offset=offset)
    if not body or body.get("status") != "success":
        print("stopped:", (body or {}).get("reason"))
        break
    used = (body.get("info") or {}).get("hitsToday")
    page = body.get("data") or []
    rows += page
    print(f"page at offset {offset}: {len(page)} matches | calls used today: {used}")
    if len(page) < 25:
        break
(out / "cricket-current.json").write_text(json.dumps(rows, indent=1))
women = re.compile(r"\b(women|womens|women's|wbbl|wpl)\b", re.I)
print(f"\n{len(rows)} matches saved to preview/cricket-current.json")
print("by format:", dict(Counter(r.get("matchType") for r in rows)))
print("finished:", sum(1 for r in rows if r.get("matchEnded")), "| not started:", sum(1 for r in rows if not r.get("matchStarted")))
dates = sorted(str(r.get("date"))[:10] for r in rows)
print("dates:", dates[0], "to", dates[-1])
print("women's matches:", sum(1 for r in rows if women.search(r.get("name") or "")))
print("\nevery match (date | format | ended | name):")
for r in sorted(rows, key=lambda r: str(r.get("date")), reverse=True):
    print(f"  {str(r.get('date'))[:10]} | {r.get('matchType'):4} | {'done' if r.get('matchEnded') else ('live' if r.get('matchStarted') else 'soon'):4} | {r.get('name')}")
if "--scorecard" in sys.argv:
    mid = sys.argv[sys.argv.index("--scorecard") + 1]
    card = call("match_scorecard", id=mid)
    if card and card.get("status") == "success":
        (out / f"cricket-scorecard-{mid}.json").write_text(json.dumps(card, indent=1))
        print(f"\nsaved preview/cricket-scorecard-{mid}.json | calls used today: {(card.get('info') or {}).get('hitsToday')}")
