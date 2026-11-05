"""Save real UFC pages for the tests (run once, no keys): the UFC.com event pages of UFC 309 (Jones vs. Miocic, 16 November 2024) and UFC 316 (Dvalishvili vs. O'Malley 2, 7 June 2025) as they stand
now that the cards are over, and ESPN's scoreboard for UFC 309's date, trimmed to what the code reads.

  .venv/bin/python scripts/save_ufc_fixtures.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import http  # noqa: E402

FX = ROOT / "tests" / "fixtures"
for name, slug in (("ufc_com_309", "ufc-309"), ("ufc_com_316", "ufc-316")):
    try:
        body = http.get_bytes(f"https://www.ufc.com/event/{slug}", retries=1, timeout=30)
        (FX / f"{name}.html").write_bytes(body)
        print("saved", name, len(body))
    except Exception as e:
        print("could not save", name, e)
board = http.get_json("https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=20241116", retries=1)
keep = []
for e in board["events"]:
    keep.append({"id": e["id"], "name": e["name"], "date": e["date"], "venues": e.get("venues"), "status": e["status"],
                 "competitions": [{"id": c["id"], "status": c["status"], "type": c.get("type"), "competitors": [{"winner": x.get("winner"), "order": x.get("order"), "athlete": {"displayName": x["athlete"]["displayName"]}}
                                                                                                          for x in c["competitors"]]} for c in e["competitions"]]})
(FX / "ufc_espn_309.json").write_text(json.dumps({"events": keep}))
print("saved ufc_espn_309", len(keep))
