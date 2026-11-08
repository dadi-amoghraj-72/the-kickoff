"""F1 data from the Jolpica API (the community-run successor to Ergast). Free, no key. Be polite: a short pause between calls
(its limits are a few calls a second and a few hundred an hour; one edition needs about a dozen)."""
import time

from kickoff import http

BASE = "https://api.jolpi.ca/ergast/f1/"
PAUSE = 0.4


class Api:
    """One object per run. Every method returns plain data, or raises SourceError (messages never contain URLs)."""

    def __init__(self, get_json=http.get_json, pause=PAUSE, backup="openf1"):
        self._get, self.pause, self.calls = get_json, pause, 0
        if backup == "openf1":
            from kickoff.sources import openf1
            backup = openf1.Source()
        self.backup, self.filled = backup, []            # OpenF1 fills the lap and race times Jolpica has left blank (D, 2026-11-08)

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

    def _filled(self, race, season, what):
        """The race as Jolpica gave it, with blank times filled from the backup (OpenF1) when it has them. A backup that fails changes nothing."""
        key = {"qualifying": "QualifyingResults", "sprint": "SprintResults", "results": "Results"}[what]
        rows = (race or {}).get(key) or []
        if not (rows and self.backup):
            return race
        blank = (not any(x.get(k) for x in rows for k in ("Q1", "Q2", "Q3"))) if what == "qualifying" else \
            any(x.get("status") == "Finished" and not (x.get("Time") or {}).get("time") for x in rows)
        if not blank:
            return race
        try:
            from kickoff.sources import openf1
            sk = self.backup.session_key(season, race["date"], what)
            got = self.backup.results(sk) if sk else {}
            n = (openf1.fill_qualifying if what == "qualifying" else openf1.fill_race)(rows, got)
            if n:
                self.filled.append(f"{race.get('raceName', '')} {what}: {n} times from OpenF1")
        except Exception:
            pass
        return race

    def results(self, season, rnd):
        return self._filled(self._race(season, rnd, "results"), season, "results")

    def qualifying(self, season, rnd):
        return self._filled(self._race(season, rnd, "qualifying"), season, "qualifying")

    def sprint(self, season, rnd):
        return self._filled(self._race(season, rnd, "sprint"), season, "sprint")

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
