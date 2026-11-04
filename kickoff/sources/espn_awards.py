"""League awards from ESPN's core API (the same free host as the other sports): the awards of a season with their winners (athlete and team ids), and the
names behind those ids. Used for the NBA, NFL and MLB. ESPN gives no announcement date, so the caller finds what is new by comparing with what it saved.

Undocumented; any failure is a SourceError and the caller leaves the awards out for the day."""
import time

from kickoff import http

CORE = "https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/"
PAUSE = 0.2


class Source:
    """One object per run; `calls` counts requests. get_json is injectable for tests."""

    def __init__(self, sport, league, get_json=http.get_json, pause=PAUSE):
        self.base, self._get, self.pause, self.calls = CORE.format(sport=sport, league=league), get_json, pause, 0
        self._teams, self._athletes = {}, {}

    def _call(self, url):
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        return self._get(url.replace("http://", "https://"))

    def awards(self, season):
        """[{"id", "name", "winners": [{"athlete": id, "team": id or None}]}] for a season, in ESPN's order; [] when the season has no awards listed."""
        listing = self._call(self.base + f"seasons/{season}/awards")
        out = []
        for it in listing.get("items", []):
            a = self._call(it["$ref"])
            winners = []
            for w in a.get("winners") or []:
                ath = (w.get("athlete") or {}).get("$ref", "")
                tm = (w.get("team") or {}).get("$ref", "")
                if ath:
                    winners.append({"athlete": ath.split("/athletes/")[1].split("?")[0], "team": tm.split("/teams/")[1].split("?")[0] if "/teams/" in tm else None})
            out.append({"id": str(a["id"]), "name": a["name"], "winners": winners})
        return out

    def athlete(self, season, athlete_id):
        """{"name": 'Shai Gilgeous-Alexander', "short": 'S. Gilgeous-Alexander'}; asked once per player and season (a player wins several awards)."""
        if (season, athlete_id) not in self._athletes:
            j = self._call(self.base + f"seasons/{season}/athletes/{athlete_id}")
            self._athletes[(season, athlete_id)] = {"name": j.get("displayName") or j.get("fullName") or "", "short": j.get("shortName") or j.get("displayName") or ""}
        return self._athletes[(season, athlete_id)]

    def team(self, season, team_id):
        """The team's abbreviation ('OKC'); asked once per team and season."""
        if (season, team_id) not in self._teams:
            j = self._call(self.base + f"seasons/{season}/teams/{team_id}")
            self._teams[(season, team_id)] = j.get("abbreviation") or j.get("shortDisplayName") or ""
        return self._teams[(season, team_id)]

    def winners(self, season, award_id):
        """The athlete ids that won one award in one season (a team award has five); [] when ESPN has no such award that season (a 404)."""
        try:
            j = self._call(self.base + f"seasons/{season}/awards/{award_id}")
        except http.SourceError as e:
            if "404" in str(e):
                return []
            raise
        return [(w.get("athlete") or {}).get("$ref", "").split("/athletes/")[-1].split("?")[0] for w in j.get("winners") or [] if (w.get("athlete") or {}).get("$ref")]
