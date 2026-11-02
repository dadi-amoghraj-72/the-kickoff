"""Re-save the NFL test fixtures from ESPN (real data, no key). Run: .venv/bin/python scripts/save_nfl_fixtures.py
Saves the current week's scoreboard, a box score for every finished game, every team's roster positions and the standings, under tests/fixtures/nfl_w8_tue_*
(the Tuesday-morning state of week 8 of 2026: Sunday night final, Monday night still to play). The older nfl_w8_* files are the Monday state (Sunday night live) that the first tests were written on, and stay as they are. About 45 calls; free, no key."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff.sources import espn_nfl  # noqa: E402

FX = ROOT / "tests" / "fixtures"
s = espn_nfl.Source()
sb = s.scoreboard()
boxes = {e["id"]: s.box(e["id"]) for e in sb["events"] if e["status"]["type"]["name"] == "STATUS_FINAL"}
positions = {}
for e in sb["events"]:
    for c in e["competitions"][0]["competitors"]:
        positions.update(s.roster(c["team"]["id"]))
byes = sb["week"].get("teamsOnBye", [])
(FX / "nfl_w8_tue_scoreboard.json").write_text(json.dumps({"season": sb["season"], "week": {"number": sb["week"]["number"], "teamsOnBye": byes}, "teamsOnBye": byes, "events": sb["events"]}))
(FX / "nfl_w8_tue_boxes.json").write_text(json.dumps(boxes))
(FX / "nfl_w8_tue_positions.json").write_text(json.dumps(positions))
(FX / "nfl_w8_tue_standings.json").write_text(json.dumps(s.standings()))
print(f"week {sb['week']['number']}: {len(sb['events'])} games, {len(boxes)} final; {len(positions)} players with positions; calls: {s.calls}")
