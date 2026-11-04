"""Season calendar and offseason material from ESPN (same free hosts as the other sports): when a season's regular season starts, the latest news and the transaction
log, for the "season is coming" note (kickoff.preview). Any failure is a SourceError and the caller skips the note for the day."""
import time

from kickoff import http

CORE = "https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/"
SITE = "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/"


class Source:
    def __init__(self, sport, league, get_json=http.get_json, pause=0.2):
        self.core, self.site = CORE.format(sport=sport, league=league), SITE.format(sport=sport, league=league)
        self._get, self.pause, self.calls = get_json, pause, 0

    def _call(self, url):
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        return self._get(url)

    def regular_season_start(self, season):
        """ISO start of the season's regular season ('2026-10-20T07:00Z'); preseason is never counted. Football has no such type: its first match day is the first date of
        the league's calendar on the scoreboard (the current season's)."""
        if "/soccer/" in self.site:
            cal = (self._call(self.site + "scoreboard").get("leagues") or [{}])[0].get("calendar") or []
            return min(cal) if cal else None
        return self._call(self.core + f"seasons/{season}/types/2").get("startDate")

    def news(self, limit=50):
        return self._call(self.site + f"news?limit={limit}").get("articles", [])

    def transactions(self, pages=3):
        """The newest transaction rows, newest first (100 a page)."""
        out = []
        for p in range(1, pages + 1):
            try:
                out += self._call(self.site + f"transactions?limit=100&page={p}").get("transactions", [])
            except http.SourceError:                          # football has no transaction log: the news alone then
                break
        return out
