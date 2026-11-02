"""NBA from ESPN's unofficial API (same family as the NFL and football data): the scoreboard for a date, one box score per game, the
conference standings and team rosters (used once, to turn the tracked players' names into ESPN ids).

Undocumented and free; any failure is a SourceError and the caller leaves that part out. A short pause between calls keeps it polite."""
import time

from kickoff import http

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/"
V2 = "https://site.api.espn.com/apis/v2/sports/basketball/nba/"
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

    def scoreboard(self, day):
        """The games of one US calendar date (a `date`)."""
        return self._call(SITE + f"scoreboard?dates={day:%Y%m%d}")

    def box(self, event_id):
        """One game, trimmed: {"players": [per team: {"team": code, "labels": [...], "athletes": [{"id", "name", "starter", "dnp", "stats": [...]}]}],
        "teams": {code: {blocks, steals, ...}}, "odds": the pre-game DraftKings line or None, "plays": the scoring plays in order}."""
        j = self._call(SITE + f"summary?event={event_id}")
        players = []
        for t in j["boxscore"]["players"]:
            st = (t.get("statistics") or [{}])[0]
            players.append({"team": t["team"]["abbreviation"], "labels": st.get("labels", []), "athletes": [
                {"id": a["athlete"]["id"], "name": a["athlete"]["displayName"], "starter": bool(a.get("starter")), "dnp": bool(a.get("didNotPlay")),
                 "reason": a.get("reason") or "", "stats": a.get("stats", [])} for a in st.get("athletes", [])]})
        teams = {t["team"]["abbreviation"]: {s["name"]: s["displayValue"] for s in t["statistics"]} for t in j["boxscore"]["teams"]}
        pc = (j.get("pickcenter") or [None])[0]
        odds = None
        if pc:
            away, home = pc.get("awayTeamOdds") or {}, pc.get("homeTeamOdds") or {}
            odds = {"details": pc.get("details"), "spread": pc.get("spread"), "away_dog": away.get("underdog"), "home_dog": home.get("underdog"),
                    "away_ml": away.get("moneyLine"), "home_ml": home.get("moneyLine")}
        plays = [{"text": p["text"], "value": p.get("scoreValue", 0), "period": p["period"]["number"], "clock": p["clock"]["displayValue"],
                  "away": p["awayScore"], "home": p["homeScore"], "team": (p.get("team") or {}).get("id"),
                  "athlete": ((p.get("participants") or [{}])[0].get("athlete") or {}).get("id")}
                 for p in j.get("plays", []) if p.get("scoringPlay")]
        return {"players": players, "teams": teams, "odds": odds, "plays": plays}

    def standings(self):
        """Both conferences with every team's record, seed and streak."""
        return self._call(V2 + "standings")

    def roster(self, team_id):
        """{athlete id: name} for one team."""
        return {a["id"]: a["displayName"] for a in self._call(SITE + f"teams/{team_id}/roster")["athletes"]}

    def teams(self):
        """{team id: abbreviation}."""
        return {t["team"]["id"]: t["team"]["abbreviation"] for t in self._call(SITE + "teams")["sports"][0]["leagues"][0]["teams"]}

    def career(self, athlete_id):
        """Career regular-season totals {"PTS": int, "REB": int, "AST": int, ...} (only the whole-number columns)."""
        j = self._call(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}/stats")
        cat = next(c for c in j["categories"] if c["name"] == "totals")
        out = {}
        for label, v in zip(cat["labels"], cat["totals"]):
            v = str(v).replace(",", "")
            if v.isdigit():
                out[label] = int(v)
        return out
