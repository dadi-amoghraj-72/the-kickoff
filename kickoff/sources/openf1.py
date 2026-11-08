"""OpenF1 (api.openf1.org): a free, public F1 data service from F1's own live timing. The backup for Jolpica's lap and race times (D, 2026-11-08): Jolpica
had the Brazilian GP qualifying order at 8:41am Singapore time but not one lap time, more than five hours after the session; OpenF1 had every Q1-Q3 time.

Only fills what Jolpica left blank, matched by car number; never changes an order, a status or points. Anything that fails gives no fill, never an error."""
import time
from datetime import date, datetime, timedelta

from kickoff import http

BASE = "https://api.openf1.org/v1/"
NAMES = {"qualifying": "Qualifying", "sprint": "Sprint", "results": "Race"}


def clock(seconds, hours=False):
    """87.47 -> '1:27.470'; 8428.772 with hours=True -> '2:20:28' (a race time to the second, as the table shows it)."""
    if hours:
        s = int(seconds)
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:06.3f}" if m else f"{s:.3f}"


class Source:
    def __init__(self, get_json=http.get_json, pause=0.4):
        self._get, self.pause, self.calls = get_json, pause, 0

    def _call(self, path):
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        return self._get(BASE + path)

    def session_key(self, season, race_date, what):
        """The OpenF1 session of a weekend: the one named for `what` that starts within the four days up to and including the race day."""
        day = date.fromisoformat(race_date)
        for s in self._call(f"sessions?year={season}&session_name={NAMES[what]}") or []:
            start = datetime.fromisoformat(s["date_start"].replace("Z", "+00:00")).date()
            if timedelta(0) <= day - start <= timedelta(days=4):
                return s["session_key"]
        return None

    def results(self, session_key):
        """{car number (str): result row} for a session."""
        return {str(x["driver_number"]): x for x in self._call(f"session_result?session_key={session_key}") or [] if x.get("driver_number") is not None}


def fill_qualifying(rows, got):
    """Jolpica qualifying rows with blank Q1-Q3 filled from OpenF1's per-part durations (seconds). Returns how many rows were filled."""
    n = 0
    for x in rows:
        if any(x.get(k) for k in ("Q1", "Q2", "Q3")):
            continue
        o = got.get(str(x.get("number")))
        parts = (o or {}).get("duration") or []
        if not isinstance(parts, list):
            continue
        for k, v in zip(("Q1", "Q2", "Q3"), parts):
            if isinstance(v, (int, float)):
                x[k] = clock(v)
        n += 1 if any(x.get(k) for k in ("Q1", "Q2", "Q3")) else 0
    return n


def fill_race(rows, got):
    """Jolpica race or sprint rows whose finisher has no time: the winner's total time, the others' gap ('+0.799'). Returns how many rows were filled."""
    n = 0
    for x in rows:
        if x.get("status") != "Finished" or (x.get("Time") or {}).get("time"):
            continue
        o = got.get(str(x.get("number"))) or {}
        if x.get("position") == "1" and isinstance(o.get("duration"), (int, float)):
            x["Time"] = {"time": clock(o["duration"], hours=True)}
            n += 1
        elif isinstance(o.get("gap_to_leader"), (int, float)):
            x["Time"] = {"time": f"+{o['gap_to_leader']:.3f}"}
            n += 1
    return n
