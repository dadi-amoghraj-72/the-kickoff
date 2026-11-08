"""Tests for OpenF1 as the backup for Jolpica's blank lap and race times (kickoff/sources/openf1.py, D 2026-11-08: the Brazilian GP qualifying had its order and no times
at 8:41am Singapore time). Run: .venv/bin/python scripts/test_openf1.py"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import f1  # noqa: E402
from kickoff.sources import jolpica, openf1  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# Brazil 2026 as both sources really had it at 9am SGT on 8 November (three drivers kept)
drv = lambda n, code, fam, team: {"number": n, "Driver": {"driverId": fam.lower(), "code": code, "givenName": "X", "familyName": fam}, "Constructor": {"name": team}}  # noqa: E731
QUALI = {"raceName": "Brazilian Grand Prix", "date": "2026-11-08", "QualifyingResults": [
    {**drv("1", "NOR", "Norris", "McLaren"), "position": "1", "Q1": "", "Q2": "", "Q3": ""},
    {**drv("63", "RUS", "Russell", "Mercedes"), "position": "2", "Q1": "", "Q2": "", "Q3": ""},
    {**drv("5", "BOR", "Bortoleto", "Audi"), "position": "22", "Q1": "", "Q2": "", "Q3": ""}]}
OPEN = [{"position": 1, "driver_number": 1, "duration": [90.939, 89.207, 87.47], "gap_to_leader": [0.0, 2.462, 0.0]},
        {"position": 2, "driver_number": 63, "duration": [91.206, 86.745, 87.674], "gap_to_leader": [0.267, 0.0, 0.204]},
        {"position": 22, "driver_number": 5, "duration": [101.564, None, None], "gap_to_leader": [10.6, None, None]}]
SESSIONS = [{"session_key": 11200, "session_name": "Qualifying", "date_start": "2026-10-31T21:00:00+00:00"},
            {"session_key": 11408, "session_name": "Qualifying", "date_start": "2026-11-07T18:00:00+00:00"}]


def fake_get(jolpica_race, what="qualifying", open_rows=OPEN, sessions=SESSIONS, boom=False):
    asked = []

    def get(url):
        asked.append(url)
        if "openf1" in url:
            if boom:
                raise RuntimeError("OpenF1 down")
            return sessions if "sessions?" in url else open_rows if "session_key=11408" in url else []
        return {"MRData": {"RaceTable": {"Races": [copy.deepcopy(jolpica_race)]}}}
    return get, asked


check("clock: 87.47s is 1:27.470, a race of 8428.77s is 2:20:28", openf1.clock(87.47) == "1:27.470" and openf1.clock(59.5) == "59.500" and openf1.clock(8428.772, hours=True) == "2:20:28")
get, asked = fake_get(QUALI)
api = jolpica.Api(get_json=get, pause=0, backup=openf1.Source(get_json=get, pause=0))
q = api.qualifying(2026, 20)["QualifyingResults"]
check("Jolpica's blank qualifying is filled from OpenF1 by car number: Norris 1:30.939 / 1:29.207 / 1:27.470", (q[0]["Q1"], q[0]["Q2"], q[0]["Q3"]) == ("1:30.939", "1:29.207", "1:27.470"), q[0])
check("a driver out in Q1 has only their Q1 time (no 'None')", (q[2]["Q1"], q[2]["Q2"], q[2]["Q3"]) == ("1:41.564", "", ""), q[2])
check("the right weekend's session is used (the qualifying of the race's own weekend, not last week's)", any("session_key=11408" in u for u in asked) and not any("session_key=11200" in u for u in asked), asked)
check("the pole line is whole again: time and gap to P2", f1.quali_summary(q) == "Pole: X Norris (McLaren), 1:27.470, 0.204s ahead of X Russell.", f1.quali_summary(q))
check("and the table has its times", "1:27.470" in f1.qualifying_table(q) and "not published" not in f1.qualifying_table(q))
check("what was filled is noted for the run log", api.filled == ["Brazilian Grand Prix qualifying: 3 times from OpenF1"], api.filled)
full = copy.deepcopy(QUALI)
full["QualifyingResults"][0].update(Q1="1:30.9", Q2="1:29.2", Q3="1:27.4")
get2, asked2 = fake_get(full)
api2 = jolpica.Api(get_json=get2, pause=0, backup=openf1.Source(get_json=get2, pause=0))
api2.qualifying(2026, 20)
check("Jolpica with its times: OpenF1 is never asked", not any("openf1" in u for u in asked2), asked2)
get3, _ = fake_get(QUALI, boom=True)
api3 = jolpica.Api(get_json=get3, pause=0, backup=openf1.Source(get_json=get3, pause=0))
q3 = api3.qualifying(2026, 20)["QualifyingResults"]
check("OpenF1 down: Jolpica's rows as they were, no error (the table shows the order and the note)", q3[0]["Q3"] == "" and "not published" in f1.qualifying_table(q3))

RACE = {"raceName": "Brazilian Grand Prix", "date": "2026-11-08", "Results": [
    {**drv("1", "NOR", "Norris", "McLaren"), "position": "1", "status": "Finished", "Time": None, "laps": "71", "points": "25", "grid": "1"},
    {**drv("63", "RUS", "Russell", "Mercedes"), "position": "2", "status": "Finished", "Time": None, "laps": "71", "points": "18", "grid": "2"},
    {**drv("5", "BOR", "Bortoleto", "Audi"), "position": "20", "status": "Retired", "Time": None, "laps": "5", "points": "0", "grid": "22"}]}
ORACE = [{"driver_number": 1, "duration": 5600.123, "gap_to_leader": 0}, {"driver_number": 63, "duration": 5601.5, "gap_to_leader": 1.377}, {"driver_number": 5, "duration": None, "gap_to_leader": None, "dnf": True}]
get4, _ = fake_get(RACE, open_rows=ORACE, sessions=[{"session_key": 11408, "session_name": "Race", "date_start": "2026-11-08T17:00:00+00:00"}])
r = jolpica.Api(get_json=get4, pause=0, backup=openf1.Source(get_json=get4, pause=0)).results(2026, 20)["Results"]
check("a race without times: the winner's time and the gaps from OpenF1; a retirement keeps no time", r[0]["Time"] == {"time": "1:33:20"} and r[1]["Time"] == {"time": "+1.377"} and r[2]["Time"] is None, [x["Time"] for x in r])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
