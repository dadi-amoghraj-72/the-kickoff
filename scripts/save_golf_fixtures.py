"""Save real golf boards for the tests (run once, no keys): the 2025 Masters, PLAYERS Championship, PGA Championship, Evian Championship and U.S. Women's Open as ESPN gives them once finished,
trimmed to what the code reads (each round's total and how many holes were played, not every hole), plus each tour's season calendar.

  .venv/bin/python scripts/save_golf_fixtures.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import http  # noqa: E402

FX = ROOT / "tests" / "fixtures"
SITE = "https://site.api.espn.com/apis/site/v2/sports/golf/{tour}/scoreboard?dates={d}"
BOARDS = {"golf_masters_2025": ("pga", "20250413"), "golf_players_2025": ("pga", "20250316"), "golf_pga_championship_2025": ("pga", "20250518"),
          "golf_evian_2025": ("lpga", "20250713"), "golf_us_womens_open_2025": ("lpga", "20250601")}


def trim(board):
    out = {"leagues": [{"calendar": [{"id": c["id"], "label": c["label"], "startDate": c["startDate"], "endDate": c["endDate"]} for c in board["leagues"][0].get("calendar", [])]}], "events": []}
    for e in board["events"]:
        comp = e["competitions"][0]
        people = []
        for c in comp["competitors"]:
            people.append({"id": c["id"], "order": c["order"], "score": c["score"], "athlete": {"displayName": c["athlete"]["displayName"], "shortName": c["athlete"].get("shortName", ""),
                           "flag": {"alt": (c["athlete"].get("flag") or {}).get("alt", "")}},
                           "linescores": [{"period": l["period"], "value": l.get("value"), "displayValue": l.get("displayValue"), "holes": len(l.get("linescores", []))} for l in c.get("linescores", [])]})
        out["events"].append({"id": e["id"], "name": e["name"], "date": e["date"], "endDate": e["endDate"], "status": e["status"], "competitions": [{"status": comp.get("status"), "competitors": people}]})
    return out


for name, (tour, d) in BOARDS.items():
    board = http.get_json(SITE.format(tour=tour, d=d), retries=2)
    (FX / f"{name}.json").write_text(json.dumps(trim(board)))
    e = board["events"][0]
    print("saved", name, e["name"], len(e["competitions"][0]["competitors"]))
