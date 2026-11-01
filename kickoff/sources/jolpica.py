"""F1 data from the Jolpica API (the community-run successor to Ergast). Free, no key. Be polite: a short pause between calls
(its limits are a few calls a second and a few hundred an hour; one edition needs about a dozen)."""
import time

from kickoff import http

BASE = "https://api.jolpi.ca/ergast/f1/"
PAUSE = 0.4


class Api:
    """One object per run. Every method returns plain data, or raises SourceError (messages never contain URLs)."""

    def __init__(self, get_json=http.get_json, pause=PAUSE):
        self._get, self.pause, self.calls = get_json, pause, 0

    def _call(self, path):
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        return self._get(BASE + path)["MRData"]

    def schedule(self, season):
        return self._call(f"{season}.json?limit=40")["RaceTable"]["Races"]

    def _race(self, season, rnd, what):
        races = self._call(f"{season}/{rnd}/{what}.json")["RaceTable"]["Races"]
        return races[0] if races else None

    def results(self, season, rnd):
        return self._race(season, rnd, "results")

    def qualifying(self, season, rnd):
        return self._race(season, rnd, "qualifying")

    def sprint(self, season, rnd):
        return self._race(season, rnd, "sprint")

    def driver_standings(self, season, rnd):
        lists = self._call(f"{season}/{rnd}/driverStandings.json")["StandingsTable"]["StandingsLists"]
        return lists[0] if lists else None

    def constructor_standings(self, season, rnd):
        lists = self._call(f"{season}/{rnd}/constructorStandings.json")["StandingsTable"]["StandingsLists"]
        return lists[0] if lists else None

    def finishes(self, driver_id, position):
        """How many times this driver has finished in this position, across his career (including any race just added)."""
        return int(self._call(f"drivers/{driver_id}/results/{position}.json?limit=1")["total"])

    def poles(self, driver_id):
        return int(self._call(f"drivers/{driver_id}/qualifying/1.json?limit=1")["total"])
