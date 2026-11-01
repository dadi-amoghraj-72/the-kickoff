"""Find out what the CricketData.org free key really gives us. Makes about 6 requests (of 100 a day); prints no keys.

  .venv/bin/python scripts/probe_cricketdata.py 2>&1 | tee preview/probe-cricketdata.log
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
KEY = os.environ.get("CRICKET_DATA_API_KEY", "")
BASE = "https://api.cricapi.com/v1"


def call(label, path, **params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode({'apikey': KEY, **params})}"
    print(f"\n=== {label}: /{path} {params}")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "TheKickoff/1.0"}), timeout=30) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"   HTTP {e.code}")
        return None
    except Exception as e:
        print(f"   FAILED {type(e).__name__}")
        return None
    info = body.get("info") or {}
    print(f"   status: {body.get('status')} | reason: {body.get('reason')} | calls used today: {info.get('hitsToday')} of {info.get('hitsLimit')}")
    return body


def names(rows, *keys):
    return " | ".join(" ".join(str(r.get(k, "")) for k in keys) for r in rows)


if not KEY:
    sys.exit("CRICKET_DATA_API_KEY is empty in .env")

cur = call("current matches", "currentMatches", offset=0)
rows = (cur or {}).get("data") or []
print(f"   {len(rows)} matches; record keys: {sorted(rows[0].keys()) if rows else None}")
for r in rows[:12]:
    print(f"   {str(r.get('date'))[:10]} | {r.get('matchType'):5} | {r.get('status')[:60] if r.get('status') else ''} | {r.get('name')}")

allm = call("matches list", "matches", offset=0)
rows2 = (allm or {}).get("data") or []
dates = sorted(str(r.get("date"))[:10] for r in rows2)
print(f"   {len(rows2)} matches | oldest {dates[0] if dates else None} | newest {dates[-1] if dates else None}")
text = " ".join(str(r.get("name")) for r in rows2 + rows).lower()
print("   mentions women's cricket:", "women" in text, "| WBBL/Big Bash:", "big bash" in text or "wbbl" in text, "| IPL:", "indian premier" in text or "ipl" in text)

ser = call("series list", "series", offset=0)
srows = (ser or {}).get("data") or []
print(f"   {len(srows)} series; first few: {names(srows[:6], 'name')}")

done = next((r for r in rows + rows2 if r.get("matchEnded")), None)
if done:
    print(f"\nTrying a finished match: {done.get('name')} ({str(done.get('date'))[:10]})")
    mi = call("match info", "match_info", id=done["id"])
    if mi:
        print("   keys:", sorted((mi.get("data") or {}).keys()))
    sc = call("match scorecard", "match_scorecard", id=done["id"])
    if sc and sc.get("data"):
        d = sc["data"]
        print("   scorecard keys:", sorted(d.keys()))
        inn = (d.get("scorecard") or [])
        print("   innings:", len(inn), "| first innings keys:", sorted(inn[0].keys()) if inn else None)
        if inn:
            bat = inn[0].get("batting") or []
            bowl = inn[0].get("bowling") or []
            print("   batting row keys:", sorted(bat[0].keys()) if bat else None)
            print("   bowling row keys:", sorted(bowl[0].keys()) if bowl else None)
else:
    print("\nNo finished match found in the lists, so scorecards could not be tested.")
