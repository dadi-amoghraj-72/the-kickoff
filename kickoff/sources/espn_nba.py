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
        "teams": {code: {blocks, steals, ...}}, "odds": the pre-game DraftKings line or None, "plays": the scoring plays in order, "injuries": {athlete id: {"status", "type"}}
        as ESPN lists them for the two teams (the reason a player who did not play was out)}."""
        j = self._call(SITE + f"summary?event={event_id}")
        players = []
        for t in j["boxscore"]["players"]:
            st = (t.get("statistics") or [{}])[0]
            players.append({"team": t["team"]["abbreviation"], "labels": st.get("labels", []), "athletes": [
                {"id": a["athlete"]["id"], "name": a["athlete"]["displayName"], "pos": (a["athlete"].get("position") or {}).get("abbreviation", ""),
                 "starter": bool(a.get("starter")), "dnp": bool(a.get("didNotPlay")),
                 "reason": a.get("reason") or "", "stats": a.get("stats", [])} for a in st.get("athletes", [])]})
        teams = {t["team"]["abbreviation"]: {s["name"]: s["displayValue"] for s in t["statistics"]} for t in j["boxscore"]["teams"]}
        pc = (j.get("pickcenter") or [None])[0]
        odds = None
        if pc:
            away, home = pc.get("awayTeamOdds") or {}, pc.get("homeTeamOdds") or {}
            odds = {"details": pc.get("details"), "spread": pc.get("spread"), "away_dog": away.get("underdog"), "home_dog": home.get("underdog"),
                    "away_ml": away.get("moneyLine"), "home_ml": home.get("moneyLine")}
        injuries = {}
        for t in j.get("injuries", []):
            for i in t.get("injuries", []):
                injuries[i["athlete"]["id"]] = {"status": i.get("status", ""), "type": (i.get("details") or {}).get("type", "")}
        plays = [{"text": p["text"], "value": p.get("scoreValue", 0), "period": p["period"]["number"], "clock": p["clock"]["displayValue"],
                  "away": p["awayScore"], "home": p["homeScore"], "team": (p.get("team") or {}).get("id"),
                  "athlete": ((p.get("participants") or [{}])[0].get("athlete") or {}).get("id")}
                 for p in j.get("plays", []) if p.get("scoringPlay")]
        return {"players": players, "teams": teams, "odds": odds, "plays": plays, "injuries": injuries}

    def standings(self, season=None):
        """Both conferences with every team's record, seed and streak (the current season, or the season ESPN labels with that year)."""
        return self._call(V2 + "standings" + (f"?season={season}" if season else ""))

    def roster(self, team_id):
        """{athlete id: name} for one team."""
        return {a["id"]: a["displayName"] for a in self._call(SITE + f"teams/{team_id}/roster")["athletes"]}

    def teams(self):
        """{team id: abbreviation}."""
        return {t["team"]["id"]: t["team"]["abbreviation"] for t in self._call(SITE + "teams")["sports"][0]["leagues"][0]["teams"]}

    def schedule(self, team_id, season=None, season_type=3):
        """One team's games of a season type (3 = playoffs), played and still to come, trimmed:
        [{"id", "date", "status", "headline", "home": {"id", "abbr", "short", "name", "score"}, "away": {...}}]. season: the year the season ends in."""
        extra = f"&season={season}" if season else ""
        out = []
        for e in self._call(SITE + f"teams/{team_id}/schedule?seasontype={season_type}{extra}")["events"]:
            c = e["competitions"][0]
            side = {}
            for x in c["competitors"]:
                sc = x.get("score")
                sc = sc.get("displayValue") if isinstance(sc, dict) else sc
                side[x["homeAway"]] = {"id": x["team"]["id"], "abbr": x["team"]["abbreviation"], "short": x["team"].get("shortDisplayName", x["team"]["abbreviation"]),
                                       "name": x["team"].get("displayName", x["team"].get("shortDisplayName", x["team"]["abbreviation"])),
                                       "score": int(sc) if str(sc or "").isdigit() else None}
            out.append({"id": e["id"], "date": e["date"], "status": c["status"]["type"]["name"],
                        "headline": next((n["headline"] for n in c.get("notes", [])), ""), "home": side["home"], "away": side["away"]})
        return out
