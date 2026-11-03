"""A stand-in for the ESPN MLB source that reads the saved 2026 files (the season is over, so the data never changes), as the feed would have looked at a
given moment: games that had not started by `now` are still to come, and a game that was under way at `now` is left out (its score so far was never saved).
Used by the previews and the tests. The standings are the final 2026 table whatever `now` is, since ESPN cannot go back in time."""
import copy
import json
from datetime import timedelta
from pathlib import Path

from kickoff.nfl import utc

FX = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
GAME_HOURS = 4


class Saved:
    calls = 0

    def __init__(self, now):
        self.now = now
        self.boards, self.std = load("mlb_scoreboards.json"), load("mlb_standings_2026.json")
        self.boxes = {**load("mlb_lad_boxes_week.json"), **load("mlb_boxes.json")}
        self.lad, self.post, self.logs = load("mlb_lad_schedule.json"), load("mlb_post_schedules.json"), load("mlb_gamelogs.json")

    def scoreboard(self, day):
        out = []
        for e in self.boards.get(str(day), {"events": []})["events"]:
            start = utc(e["date"])
            if start + timedelta(hours=GAME_HOURS) <= self.now:
                out.append(e)
            elif start >= self.now:                                   # not started: scheduled, no score
                e = copy.deepcopy(e)
                e["status"]["type"] = {"name": "STATUS_SCHEDULED", "state": "pre"}
                out.append(e)
        return {"events": out}

    def box(self, event_id):
        return self.boxes[event_id]

    def standings(self, season=None):
        return self.std

    def _as_of(self, rows):
        out = []
        for g in rows:
            done = utc(g["date"]) + timedelta(hours=GAME_HOURS) <= self.now
            out.append(g if done else {**g, "status": "STATUS_SCHEDULED", "home": {**g["home"], "score": None}, "away": {**g["away"], "score": None}})
        return [g for g in out if g["status"] == "STATUS_FINAL" or utc(g["date"]) >= self.now]

    def schedule(self, team_id, season=None, season_type=2):
        if season_type == 3:
            return self._as_of(self.post.get(str(team_id), []))
        return self._as_of(self.lad)

    def gamelog(self, athlete_id, season, category):
        key = {("39832", "batting"): "ohtani_bat", ("39832", "pitching"): "ohtani_pit", ("4872587", "pitching"): "yamamoto_pit"}[(str(athlete_id), category)]
        return [x for x in self.logs[key] if utc(x["date"]) + timedelta(hours=GAME_HOURS) <= self.now]
