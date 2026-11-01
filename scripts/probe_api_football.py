"""Find out what API-Football's free plan really gives us. Makes 5 requests (of the 100 a day) and prints no keys.

  .venv/bin/python scripts/probe_api_football.py 2>&1 | tee preview/probe-apifootball.log
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff.envfile import load_env  # noqa: E402

load_env()
KEY = os.environ.get("API_FOOTBALL_KEY", "")
BASE = "https://v3.football.api-sports.io"
ARSENAL_ID, PL_ID = 42, 39  # API-Football's own IDs, different from ESPN's


def call(label, path, **params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    print(f"\n=== {label}: /{path} {params}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body, left = json.load(resp), resp.headers.get("x-ratelimit-requests-remaining")
    except urllib.error.HTTPError as e:
        print(f"   HTTP {e.code}")
        return None
    print(f"   results: {body.get('results')} | paging: {body.get('paging')} | requests left today: {left}")
    if body.get("errors"):
        print(f"   ERRORS: {body['errors']}")
    return body


if not KEY:
    sys.exit("API_FOOTBALL_KEY is empty in .env")

cov = call("coverage for the 2026 Premier League", "leagues", id=PL_ID, season=2026)
if cov and cov.get("response"):
    season = next((s for s in cov["response"][0]["seasons"] if s["year"] == 2026), None)
    print("   coverage flags:", json.dumps(season["coverage"]) if season else "2026 not listed")

for yr in (2026, 2025):
    body = call(f"Arsenal player stats, season {yr}", "players", team=ARSENAL_ID, season=yr, league=PL_ID)
    if body and body.get("response"):
        rows = []
        for p in body["response"][:6]:
            st = p["statistics"][0]
            rows.append(f"{p['player']['name']} ({st['games']['minutes']} min, {st['games']['appearences']} apps)")
        print("   sample:", "; ".join(rows))

inj = call("injuries in the 2026 Premier League", "injuries", league=PL_ID, season=2026)
if inj and inj.get("response"):
    for i in inj["response"][:5]:
        print(f"   {i['player']['name']} ({i['team']['name']}): {i['player'].get('type')} - {i['player'].get('reason')} | fixture {i['fixture']['date'][:10]}")
inj_d = call("injuries on one date", "injuries", league=PL_ID, season=2026, date="2026-11-01")
