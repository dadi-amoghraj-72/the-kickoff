"""Save real pages for the Around The Sporting World tests (run once; no keys needed): ESPN's Six Nations, PGA and UFC scoreboards, the UFC rankings and the BBC and Guardian sport feeds.

  .venv/bin/python scripts/save_other_sports_fixtures.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import http  # noqa: E402

FX = ROOT / "tests" / "fixtures"
SITE = "https://site.api.espn.com/apis/site/v2/sports/"
for name, url in (("other_rugby_six_nations", SITE + "rugby/180659/scoreboard"), ("other_golf_pga", SITE + "golf/pga/scoreboard"), ("other_ufc_scoreboard", SITE + "mma/ufc/scoreboard")):
    (FX / f"{name}.json").write_text(json.dumps(http.get_json(url), indent=1))
    print("saved", name)
rk = http.get_json(SITE + "mma/ufc/rankings")
slim = {"rankings": [{"name": d["name"], "ranks": [{"current": x["current"], "athlete": {"displayName": x["athlete"]["displayName"]}} for x in d["ranks"]]} for d in rk["rankings"]]}
(FX / "other_ufc_rankings.json").write_text(json.dumps(slim, indent=1))
print("saved other_ufc_rankings")
for name, url in (("other_bbc_sport", "https://feeds.bbci.co.uk/sport/rss.xml"), ("other_guardian_sport", "https://www.theguardian.com/sport/rss")):
    (FX / f"{name}.xml").write_bytes(http.get_bytes(url))
    print("saved", name)
