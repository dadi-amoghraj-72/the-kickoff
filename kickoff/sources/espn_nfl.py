"""NFL from ESPN's unofficial API (the same family as the football data): the scoreboard (week number, games, teams on bye), one box score per
game, team rosters (the box score gives no positions) and the standings by division.

Undocumented and free; any failure is a SourceError and the caller leaves that part out. A short pause between calls keeps it polite: a
Wednesday wrap needs about 18 box scores."""
import time

from kickoff import http

SITE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
V2 = "https://site.api.espn.com/apis/v2/sports/football/nfl/"
PAUSE = 0.25


class Source:
    """One object per run; `calls` counts requests. get_json is injectable for tests."""

    def __init__(self, get_json=http.get_json, pause=PAUSE):
        self._get, self.pause, self.calls = get_json, pause, 0

    def _call(self, url):
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        return self._get(url)

    def scoreboard(self, week=None, season_type=None):
        """The current week's scoreboard, or a given week (of a season type, 2 = regular season)."""
        extra = f"?week={week}&seasontype={season_type or 2}" if week else ""
        return self._call(SITE + "scoreboard" + extra)

    def box(self, event_id):
        """One game: {"teamStats": {team id: {rushingYards, netPassingYards, turnovers}}, "players": [per team: {"team", "statistics"}],
        "odds": the pre-game DraftKings line or None, "plays": the scoring plays in order}."""
        j = self._call(SITE + f"summary?event={event_id}")
        bx, keep = j["boxscore"], ("rushingYards", "netPassingYards", "turnovers")
        pc = (j.get("pickcenter") or [None])[0]
        odds = None
        if pc:
            away, home = pc.get("awayTeamOdds") or {}, pc.get("homeTeamOdds") or {}
            odds = {"details": pc.get("details"), "spread": pc.get("spread"), "away_dog": away.get("underdog"), "home_dog": home.get("underdog"),
                    "away_ml": away.get("moneyLine"), "home_ml": home.get("moneyLine")}
        plays = [{"text": p["text"], "type": p["type"]["text"], "period": p["period"]["number"], "clock": p["clock"]["displayValue"],
                  "away": p["awayScore"], "home": p["homeScore"], "team": p["team"]["abbreviation"]} for p in j.get("scoringPlays", [])]
        return {"teamStats": {t["team"]["id"]: {s["name"]: s["displayValue"] for s in t["statistics"] if s["name"] in keep} for t in bx["teams"]},
                "players": bx["players"], "odds": odds, "plays": plays}

    def roster(self, team_id):
        """{athlete id: position abbreviation} for one team."""
        out = {}
        for group in self._call(SITE + f"teams/{team_id}/roster")["athletes"]:
            for p in group.get("items", []):
                out[p["id"]] = p["position"]["abbreviation"]
        return out

    def standings(self):
        """Standings with the divisions (level 3): conferences, each with its divisions and their teams."""
        return self._call(V2 + "standings?level=3")
