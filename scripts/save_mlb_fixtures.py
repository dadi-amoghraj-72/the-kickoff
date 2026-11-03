"""Re-save the MLB test fixtures from ESPN (real data, no key). Run: .venv/bin/python scripts/save_mlb_fixtures.py
Saves the 2026 season, which is over, so the data never changes:
  - mlb_lad_schedule.json   the Dodgers' regular-season schedule, and mlb_lad_boxes_week.json the box scores of the week to Thursday 7 May (6 games)
  - mlb_gamelogs.json       Ohtani's batting and pitching and Yamamoto's pitching game logs for 2026
  - mlb_scoreboards.json    every game day from 18 September to 29 October (only the fields the code reads)
  - mlb_boxes.json          the box scores of the days the tests use: 19 and 20 September (the Dodgers' 155th game and after) and the playoff days
  - mlb_post_schedules.json each playoff team's postseason schedule
  - mlb_standings_2026.json the final standings"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff.sources import espn_mlb  # noqa: E402

FX = ROOT / "tests" / "fixtures"
s = espn_mlb.Source()
dump = lambda name, obj: (FX / name).write_text(json.dumps(obj))  # noqa: E731


def slim(e):
    c = e["competitions"][0]
    return {"id": e["id"], "date": e["date"], "season": e["season"], "status": {"period": e["status"].get("period"), "type": e["status"]["type"]},
            "competitions": [{"neutralSite": c.get("neutralSite"), "notes": c.get("notes", []), "series": {"summary": (c.get("series") or {}).get("summary"), "type": (c.get("series") or {}).get("type")},
                              "competitors": [{"homeAway": x["homeAway"], "score": x.get("score"), "records": x.get("records", []),
                                               "team": {k: x["team"][k] for k in ("id", "abbreviation", "displayName", "shortDisplayName")}} for x in c["competitors"]]}]}


dump("mlb_standings_2026.json", s.standings(2026))
sched = s.schedule("19", 2026, 2)
dump("mlb_lad_schedule.json", sched)
week_end = datetime(2026, 5, 7, tzinfo=timezone.utc)
week = [g for g in sched if g["status"] == "STATUS_FINAL" and week_end - timedelta(days=7) < datetime.fromisoformat(g["date"].replace("Z", "+00:00")) <= week_end]
dump("mlb_lad_boxes_week.json", {g["id"]: s.box(g["id"]) for g in week})
dump("mlb_gamelogs.json", {"ohtani_bat": s.gamelog("39832", 2026, "batting"), "ohtani_pit": s.gamelog("39832", 2026, "pitching"), "yamamoto_pit": s.gamelog("4872587", 2026, "pitching")})
boards, d = {}, date(2026, 9, 18)
while d <= date(2026, 10, 29):
    boards[str(d)] = {"events": [slim(e) for e in s.scoreboard(d)["events"]]}
    d += timedelta(days=1)
dump("mlb_scoreboards.json", boards)
USE = ("2026-09-19", "2026-09-20", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-03", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15") + tuple(f"2026-10-{d}" for d in range(23, 29))   # days whose games the tests read in full
boxes, teams = {}, set()
for day in USE:
    for e in boards[day]["events"]:
        if e["status"]["type"]["name"] == "STATUS_FINAL":
            boxes[e["id"]] = s.box(e["id"])
            if day >= "2026-09-29":
                teams |= {x["team"]["id"] for x in e["competitions"][0]["competitors"]}
dump("mlb_boxes.json", boxes)
dump("mlb_post_schedules.json", {t: s.schedule(t, 2026, 3) for t in sorted(teams)})
print("saved; games boxed:", len(boxes), "calls:", s.calls)
