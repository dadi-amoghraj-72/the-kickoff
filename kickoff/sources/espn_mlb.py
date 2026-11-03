"""MLB from ESPN's unofficial API (same family as the NFL, NBA and football data): the scoreboard for a date, one box score per game, the
division standings, one team's schedule and one player's game log (Ohtani's and Yamamoto's per-game lines, with stolen bases and decisions).

Undocumented and free; any failure is a SourceError and the caller leaves that part out. A short pause between calls keeps it polite."""
import time

from kickoff import http

SITE = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/"
V2 = "https://site.api.espn.com/apis/v2/sports/baseball/mlb/"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/baseball/mlb/"
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
        """One game, trimmed: {"teams": {code: {"batters": [...], "pitchers": [...]}}, "odds": the pre-game DraftKings line or None,
        "injuries": {athlete id: {"status", "type"}} as ESPN lists them for the two teams}. A batter is {"id", "name", "starter", "stats": {label: value}};
        a pitcher also has "dec" (the decision, 'W, 11-7', or '')."""
        j = self._call(SITE + f"summary?event={event_id}")
        teams = {}
        for t in j["boxscore"]["players"]:
            side = {"batters": [], "pitchers": []}
            for s in t.get("statistics", []):
                key = "batters" if s["type"] == "batting" else "pitchers" if s["type"] == "pitching" else None
                for a in s.get("athletes", []) if key else []:
                    row = {"id": a["athlete"]["id"], "name": a["athlete"]["displayName"], "starter": bool(a.get("starter")), "stats": dict(zip(s["labels"], a.get("stats", [])))}
                    if key == "pitchers":
                        row["dec"] = next((n["text"] for n in a.get("notes", []) if n.get("type") == "pitchingDecision"), "")
                    side[key].append(row)
            teams[t["team"]["abbreviation"]] = side
        pc = (j.get("pickcenter") or [None])[0]
        odds = None
        if pc:
            away, home = pc.get("awayTeamOdds") or {}, pc.get("homeTeamOdds") or {}
            odds = {"details": pc.get("details"), "away_dog": away.get("underdog"), "home_dog": home.get("underdog"),
                    "away_ml": away.get("moneyLine"), "home_ml": home.get("moneyLine")}
        injuries = {}
        for t in j.get("injuries", []):
            for i in t.get("injuries", []):
                injuries[i["athlete"]["id"]] = {"status": i.get("status", ""), "type": (i.get("details") or {}).get("type", "")}
        return {"teams": teams, "odds": odds, "injuries": injuries}

    def standings(self, season=None):
        """Both leagues by division (level 3) with every team's record, playoff seed, clincher mark and streak."""
        return self._call(V2 + "standings?level=3" + (f"&season={season}" if season else ""))

    def schedule(self, team_id, season=None, season_type=2):
        """One team's games of a season type (2 regular season, 3 postseason), played and still to come, trimmed:
        [{"id", "date", "status", "headline", "home": {"id", "abbr", "short", "name", "score"}, "away": {...}}]. season: the year."""
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

    def gamelog(self, athlete_id, season, category):
        """One player's games of a season ('batting' or 'pitching'): [{"id": game id, "date": ISO, "stats": {label: value}}], oldest first. The batting
        labels include 2B, HR, RBI, SB and the running AVG/OBP/SLG/OPS; the pitching ones IP, ER, K, Dec (W, L, ND, S...) and the running ERA."""
        j = self._call(WEB + f"athletes/{athlete_id}/gamelog?season={season}&category={category}")
        out = []
        for st in j.get("seasonTypes", []):
            for cat in st.get("categories", []):
                for ev in cat.get("events", []):
                    meta = j["events"].get(ev["eventId"], {})
                    out.append({"id": ev["eventId"], "date": meta.get("gameDate", ""), "stats": dict(zip(j["labels"], ev["stats"]))})
        return sorted(out, key=lambda x: x["date"])
