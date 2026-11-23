"""NHL from ESPN's unofficial API (the same family as the NBA data): the season's leaders for one stat, qualified players only. Any failure is an exception the caller catches."""
import time

from kickoff import http

STATS = "https://site.web.api.espn.com/apis/common/v3/sports/hockey/nhl/statistics/byathlete"
PAUSE = 0.25


class Source:
    def __init__(self, get_json=http.get_json, pause=PAUSE):
        self._get, self.pause, self.calls = get_json, pause, 0

    def leaders(self, category, sort, limit=5):
        """category 'skaters' or 'goalies'; sort like 'offensive.goals' (group.stat). [{"name", "team", "value"}], best first."""
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        j = self._get(f"{STATS}?category={category}&sort={sort}:desc&limit={limit}")
        group, key = sort.split(".")
        names = {c["name"]: c.get("names") or [] for c in j.get("categories") or []}
        out = []
        for a in j.get("athletes") or []:
            vals = {c["name"]: c.get("values") or [] for c in a.get("categories") or []}
            i = names.get(group, []).index(key) if key in names.get(group, []) else None
            if i is None or i >= len(vals.get(group, [])) or vals[group][i] is None:
                continue
            out.append({"name": a["athlete"]["displayName"], "team": a["athlete"].get("teamShortName") or "", "value": float(vals[group][i])})
        return out[:limit]
