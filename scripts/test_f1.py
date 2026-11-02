"""Offline tests for the F1 block, on saved real Jolpica responses (2026 season). Run: python3 scripts/test_f1.py"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import f1  # noqa: E402

FX = ROOT / "tests" / "fixtures"
L = lambda n: json.loads((FX / n).read_text())["MRData"]  # noqa: E731
SCHED = L("jolpica_schedule_2026.json")["RaceTable"]["Races"]
RACE18 = L("jolpica_results_18.json")["RaceTable"]["Races"][0]
Q18 = L("jolpica_quali_18.json")["RaceTable"]["Races"][0]
Q19 = L("jolpica_quali_19.json")["RaceTable"]["Races"][0]
SPR17 = L("jolpica_sprint_17.json")["RaceTable"]["Races"][0]
DS18 = L("jolpica_dstand_18.json")["StandingsTable"]["StandingsLists"][0]
CS18 = L("jolpica_cstand_18.json")["StandingsTable"]["StandingsLists"][0]
COUNTS = json.loads((FX / "jolpica_counts.json").read_text())
ROWS = RACE18["Results"]
results = []


def shift(ds, rows, label, sign):
    """Standings with this race's points taken off (sign -1) or added (+1): the round before or after."""
    got = {x["Driver"]["driverId"]: float(x["points"]) for x in rows}
    return {**ds, "round": label, "DriverStandings": [{**x, "points": str(int(float(x["points"]) + sign * got.get(x["Driver"]["driverId"], 0)))} for x in ds["DriverStandings"]]}


DS17 = shift(DS18, ROWS, "17", -1)


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


class FakeApi:
    """Answers from the fixtures. results_for / qualifying_for / sprint_for: {round: race dict}; raises for rounds in `broken`."""

    def __init__(self, results_for=None, qualifying_for=None, sprint_for=None, dstand=None, broken=()):
        self.results_for, self.qualifying_for, self.sprint_for = results_for or {}, qualifying_for or {}, sprint_for or {}
        self.dstand = {18: DS18, 17: DS17} if dstand is None else dstand
        self.broken, self.calls, self.log = set(broken), 0, []

    def _hit(self, what, rnd):
        self.calls += 1
        self.log.append((what, rnd))
        if (what, rnd) in self.broken:
            raise RuntimeError("source down")

    def schedule(self, season):
        self._hit("schedule", season)
        return SCHED

    def results(self, season, rnd):
        self._hit("results", rnd)
        return self.results_for.get(int(rnd))

    def qualifying(self, season, rnd):
        self._hit("qualifying", rnd)
        return self.qualifying_for.get(int(rnd))

    def sprint(self, season, rnd):
        self._hit("sprint", rnd)
        return self.sprint_for.get(int(rnd))

    def driver_standings(self, season, rnd):
        self._hit("dstand", rnd)
        return self.dstand.get(int(rnd))

    def constructor_standings(self, season, rnd):
        self._hit("cstand", rnd)
        return {**CS18, "round": str(rnd)} if int(rnd) in self.dstand else None

    def finishes(self, did, pos):
        self._hit("finishes", (did, pos))
        return COUNTS[did]["results"][str(pos)] if did in COUNTS else 99

    def poles(self, did):
        self._hit("poles", did)
        return COUNTS[did]["poles"] if did in COUNTS else 99


# ---- Which sessions are due ----
W = utc(2026, 10, 25, 15, 15)
names = lambda ds: [d["id"] for d in ds]  # noqa: E731
check("the US GP race (ends about 22:30 UTC on 25 Oct) is due in the edition that follows it", names(f1.due_sessions(SCHED, utc(2026, 10, 26, 2, 0), W)) == ["2026-18-race"], names(f1.due_sessions(SCHED, utc(2026, 10, 26, 2, 0), W)))
check("a Saturday qualifying and the Sunday race can both be due after a missed day, in weekend order qualifying then race",
      names(f1.due_sessions(SCHED, utc(2026, 11, 2, 3, 0), utc(2026, 10, 31, 20, 0))) == ["2026-19-qualifying", "2026-19-race"])
check("a race that has not finished yet is not due", names(f1.due_sessions(SCHED, utc(2026, 11, 1, 20, 30), utc(2026, 10, 31, 23, 15))) == [])
check("a session already reported is not shown again", names(f1.due_sessions(SCHED, utc(2026, 10, 26, 2, 0), W, reported=["2026-18-race"])) == [])
check("a session before the window comes back only while it is pending, and only for 6 days", names(f1.due_sessions(SCHED, utc(2026, 10, 28, 2, 0), utc(2026, 10, 27, 15, 0))) == []
      and names(f1.due_sessions(SCHED, utc(2026, 10, 28, 2, 0), utc(2026, 10, 27, 15, 0), pending=["2026-18-race"])) == ["2026-18-race"]
      and names(f1.due_sessions(SCHED, utc(2026, 11, 5, 2, 0), utc(2026, 11, 4, 15, 0), pending=["2026-18-race"])) == [])
check("a sprint weekend has qualifying, sprint and race sessions (Singapore, round 17)", names(f1.due_sessions(SCHED, utc(2026, 10, 12, 2, 0), utc(2026, 10, 10, 8, 0))) == ["2026-17-qualifying", "2026-17-sprint", "2026-17-race"],
      names(f1.due_sessions(SCHED, utc(2026, 10, 12, 2, 0), utc(2026, 10, 10, 8, 0))))
check("practice sessions and sprint qualifying are never due", all(d["session"] in ("qualifying", "sprint", "race") for d in f1.due_sessions(SCHED, utc(2026, 12, 20), utc(2026, 1, 1))))

# ---- Tables, against the saved US GP ----
tbl = f1.results_table("Race", ROWS)
cells = lambda html: [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>.*?</td>", html)]  # noqa: E731
c = cells(tbl)
check("the race table has all 22 drivers, 5 columns each (P, Driver, +/-, Gap, Pts)", len(c) == 22 * 5 and tbl.count("<tr>") == 22 + 1, len(c))
check("points in the table add up to the 101 the top ten scored", sum(int(c[i * 5 + 4]) for i in range(22)) == 101, sum(int(c[i * 5 + 4]) for i in range(22)))
check("winner row: K. Antonelli, level, race time to the second, 25 points; second row is a gap", c[:5] == ["1", "K. Antonelli", "–", "1:35:16", "25"] and c[5:7] == ["2", "C. Leclerc"] and c[8:10] == ["+13.078", "18"], c[:10])
check("lapped cars show laps down, retirements show DNF", c[11 * 5 + 3] == "+1 lap" and c[19 * 5 + 3] == "DNF" and c[21 * 5 + 3] == "DNF", [c[i * 5 + 3] for i in (11, 19, 21)])
check("driver tables use three-letter team codes (RB is Racing Bulls; unknown teams get their first three letters)", f1.abbr("RB F1 Team") == "RB" and f1.abbr("Red Bull") == "RBR" and f1.abbr("Aston Martin") == "AMR" and f1.abbr("Haas F1 Team") == "HAA" and f1.abbr("Zeta Racing") == "ZET")
check("short_name: initial and surname; a double given name uses the last part (Andrea Kimi is K.); no names falls back to the code; accents kept", f1.short_name({"givenName": "Max", "familyName": "Verstappen"}) == "M. Verstappen" and f1.short_name({"givenName": "Andrea Kimi", "familyName": "Antonelli"}) == "K. Antonelli" and f1.short_name({"code": "XYZ"}) == "XYZ" and f1.short_name({"givenName": "Nico", "familyName": "Hülkenberg"}) == "N. Hülkenberg")
check("team names are short ('RB F1 Team' is Racing Bulls, '... F1 Team' loses the suffix)", f1.team("RB F1 Team") == "Racing Bulls" and f1.team("Haas F1 Team") == "Haas" and f1.team("Aston Martin") == "Aston Martin")
check("the number columns are right-aligned like every other table", tbl.count('<th class="n">') == 4 and tbl.count('<td class="n">') == 22 * 4)
qt = cells(f1.qualifying_table(Q18["QualifyingResults"]))
check("qualifying table: pole is ANT, Q3, 1:34.035; a Q1 exit shows its Q1 time (Bottas 22nd); 4 columns each", qt[:4] == ["1", "K. Antonelli", "Q3", "1:34.035"] and qt[-4:] == ["22", "V. Bottas", "Q1", "1:37.523"] and len(qt) == 22 * 4, (qt[:4], qt[-4:]))
check("Lawson, 10th with no Q3 time, shows his Q2 time marked Q2 (so 9th Lindblad's slower Q3 lap does not look out of order)", qt[9 * 4:9 * 4 + 4] == ["10", "L. Lawson", "Q2", "1:35.058"], qt[36:40])
check("the tables use the compact style", f1.qualifying_table(Q18["QualifyingResults"]).startswith('<div class="pts f1">') and tbl.startswith('<div class="pts f1') and f1.driver_standings_table(DS18, 18).startswith('<div class="pts f1">'))
ds = f1.driver_standings_table(DS18, 18)
check("driver standings: top 10, leader Antonelli on 365", ds.count("<tr>") == 11 and cells(ds)[:4][1] == "K. Antonelli" and cells(ds)[3] == "365" and "top 10" in ds, cells(ds)[:4])
lawson = lambda html: cells(html)[cells(html).index("L. Lawson") + 1]  # noqa: E731
check("a driver listed under two teams in the standings (Lawson) shows the team from the race: Racing Bulls, not Red Bull", lawson(f1.driver_standings_table(DS18, 18, teams={x["Driver"]["driverId"]: x["Constructor"]["name"] for x in ROWS})) == "RB"
      and lawson(ds) in ("RB", "RBR"))
cs = f1.constructor_standings_table(CS18, 18)
check("constructor standings: all 11 teams, Mercedes first on 607", cs.count("<tr>") == 12 and cells(cs)[:3] == ["1", "Mercedes", "607"], cells(cs)[:3])

# ---- Round-up lines ----
check("race line: winner, start, margin, fastest lap, retirements", f1.race_summary(ROWS) == "Antonelli (Mercedes) won from pole, 13.078s ahead of Leclerc. Fastest lap: Leclerc, 1:37.976. 3 did not finish.", f1.race_summary(ROWS))
check("qualifying line: pole, time, margin to P2 (94.214 - 94.035 = 0.179)", f1.quali_summary(Q18["QualifyingResults"]) == "Pole: Antonelli (Mercedes), 1:34.035, 0.179s ahead of Verstappen.", f1.quali_summary(Q18["QualifyingResults"]))
check("seconds() reads lap times and gaps", f1.seconds("1:34.035") == 94.035 and f1.seconds("+13.078") == 13.078 and abs(f1.seconds("+1:19.183") - 79.183) < 1e-9 and f1.seconds("DNF") is None and f1.seconds(None) is None)

# ---- Standouts ----
mk = lambda pos, grid, status="Finished", code="X": {"position": str(pos), "grid": str(grid), "status": status, "laps": "50", "Driver": {"givenName": "Gi", "familyName": code, "driverId": code.lower(), "code": code},  # noqa: E731
                                                       "Constructor": {"name": "Haas F1 Team"}}
pm = lambda i: c[i * 5 + 2]  # noqa: E731
check("arrows in the table: gained places ▲, lost places ▼, retirements –", all(pm(i) == "–" for i in (19, 20, 21)) and pm(0) == "–" and
      {x["Driver"]["code"]: pm(i) for i, x in enumerate(ROWS)}["BOR"] == "▲8", [pm(i) for i in range(22)])
check("every arrow equals grid minus finish, checked against the saved results", all(
      (pm(i) == "–") == (f1.places_gained(x) in (None, 0)) and (f1.places_gained(x) is None or f1.places_gained(x) == int(x["grid"]) - int(x["position"])) for i, x in enumerate(ROWS)))
check("moved(): up, down, level, pit lane, out", f1.moved(mk(3, 9)) == "▲6" and f1.moved(mk(9, 3)) == "▼6" and f1.moved(mk(4, 4)) == "–" and f1.moved(mk(5, 0)) == "–" and f1.moved(mk(6, 2, "Retired")) == "–")
bm = f1.biggest_mover(ROWS)
check("the real US GP's Biggest Mover is Bortoleto, 21st to 13th (▲8)", len(bm) == 1 and bm[0].startswith("Biggest Mover: Gabriel Bortoleto") and "P21 on the grid to P13 (▲8)" in bm[0], bm)
check("Biggest Mover needs 4 places; picks the largest; ignores retirements", f1.biggest_mover([mk(5, 8)]) == [] and f1.biggest_mover([mk(5, 9)]) != [] and "P20" in f1.biggest_mover([mk(5, 9), mk(8, 20)])[0] and f1.biggest_mover([mk(6, 20, "Retired")]) == [])
rs = lambda *xs: [dict(mk(1, 1, code="W"), laps="50")] + list(xs)  # noqa: E731
early = f1.big_moments(rs(dict(mk(20, 17, "Retired", "STR"), laps="5"), dict(mk(21, 19, "Retired", "ALO"), laps="5")))
check("two drivers of one team out after 5 laps: one Big Moment line, no cause claimed", early == ["Big Moment: STR and ALO (both Haas) out after 5 laps."], early)
check("a lap-1 retirement says lap 1", f1.big_moments(rs(dict(mk(22, 9, "Retired", "ABC"), laps="0"))) == ["Big Moment: ABC (Haas) out on lap 1."] or f1.big_moments(rs(dict(mk(22, 9, "Retired", "ABC"), laps="0"))) == ["Big Moment: ABC out on lap 1."])
check("a top-5 starter retiring mid-race is a Big Moment; a back-marker retiring mid-race is not; neither is a classified lapped finisher",
      len(f1.big_moments(rs(dict(mk(20, 3, "Retired", "TOP"), laps="31")))) == 1 and f1.big_moments(rs(dict(mk(20, 15, "Retired", "BAK"), laps="31"))) == []
      and f1.big_moments(rs(dict(mk(20, 3, "Lapped", "LAP"), laps="49"))) == [] and f1.big_moments(rs(dict(mk(20, 3, "Disqualified", "DSQ"), laps="0"))) == [])
check("never more than two Big Moment lines", len(f1.big_moments(rs(*[dict(mk(10 + i, 2, "Retired", f"R{i}"), laps=str(i * 6)) for i in range(1, 6)]))) <= 2)
check("labels are bold in the page", "<strong>Biggest Mover:</strong>" in f1._list(bm) and "<strong>Big Moment:</strong>" in f1._list(early))
fin = lambda did, pos: {("a", 1): 1, ("b", 2): 1, ("b", 1): 0, ("b", 3): 0, ("c", 3): 4, ("c", 1): 2, ("c", 2): 0}[(did, pos)]  # noqa: E731
top3 = [{**mk(1, 1, code="A"), "Driver": {"familyName": "A", "driverId": "a", "code": "A"}}, {**mk(2, 2), "Driver": {"familyName": "B", "driverId": "b", "code": "B"}},
        {**mk(3, 3), "Driver": {"familyName": "C", "driverId": "c", "code": "C"}}]
got = f1.firsts(top3, fin)
check("first win for a driver whose only win is this one; first podium for a P2 with no other podium; nothing for a P3 who has stood there four times",
      len(got) == 2 and "A (Haas): first Grand Prix win" in got[0] and "B (Haas): first podium finish" in got[1], got)
asked = []
f1.firsts(ROWS, lambda d, p: asked.append((d, p)) or COUNTS[d]["results"][str(p)])
check("for experienced drivers one call each is enough (3 calls for the whole podium)", len(asked) == 3, asked)
check("the real US podium (Antonelli, Leclerc, Verstappen) has no firsts", f1.firsts(ROWS, lambda d, p: COUNTS[d]["results"][str(p)]) == [])
q = Q18["QualifyingResults"]
clear = [dict(q[0], Q3="1:33.800"), dict(q[1], Q3="1:34.214")] + q[2:]
check("a pole 0.300s clear or more is called out (0.414 here); the real 0.179 is not", len(f1.quali_standouts(clear, lambda d: 5)) == 1 and "0.414s over Verstappen" in f1.quali_standouts(clear, lambda d: 5)[0]
      and f1.quali_standouts(q, lambda d: 5) == [])
check("a first pole is called out", f1.quali_standouts(q, lambda d: 1) == ["Antonelli (Mercedes): first pole position."], f1.quali_standouts(q, lambda d: 1))

# ---- The whole block ----
SGT_MORNING = utc(2026, 10, 26, 2, 0)
api = FakeApi(results_for={18: RACE18}, qualifying_for={18: Q18})
out = f1.run(SGT_MORNING, W, {}, api)
check("the US GP race edition: heading, race line, race table, both standings, no waiting note", "<h3>United States Grand Prix</h3>" in out["html"] and "won from pole" in out["html"]
      and "<caption>Race</caption>" in out["html"] and "Drivers&#x27; standings after round 18: top 10" in out["html"].replace("'", "&#x27;") and "Constructors" in out["html"] and "Not published" not in out["html"], out["html"][:400])
check("it is remembered as reported, nothing is pending", out["state"]["reported"] == ["2026-18-race"] and out["state"]["pending"] == {}, out["state"])
check("calls: schedule, results, 3 podium checks, 3 standings (this round, the one before, constructors) = 8", api.calls == 8, api.log)
check("and tomorrow it is not shown again", f1.run(utc(2026, 10, 27, 2, 0), utc(2026, 10, 26, 15, 15), out["state"], api)["html"] == "")

# The real situation on 2 November 2026: Mexico City's race is over but its results are not published yet
RAW_NOW, RAW_W = utc(2026, 11, 2, 3, 0), utc(2026, 10, 31, 23, 15)
pend = f1.run(RAW_NOW, RAW_W, {}, FakeApi())
check("race over but no results yet: no table, a clear note, and it stays pending", "Mexico City Grand Prix race" in pend["html"] and "<table" not in pend["html"]
      and list(pend["state"]["pending"]) == ["2026-19-race"] and pend["state"]["reported"] == [], pend)
DS19 = shift(DS18, ROWS, "19", 1)  # round 19 really adds this race's points on top of round 18
later = f1.run(utc(2026, 11, 3, 3, 0), utc(2026, 11, 2, 15, 15), pend["state"], FakeApi(results_for={19: {**RACE18, "round": "19", "raceName": "Mexico City Grand Prix"}}, dstand={18: DS18, 19: DS19}))
check("the next edition picks the pending race up as soon as it is published, and clears the pending entry", "<caption>Race</caption>" in later["html"] and "Mexico City Grand Prix" in later["html"]
      and later["state"]["pending"] == {} and later["state"]["reported"] == ["2026-19-race"], later["state"])
stale = f1.run(utc(2026, 11, 10, 3, 0), utc(2026, 11, 9, 15, 15), {"pending": {"2026-19-race": "2026-11-01T22:30:00+00:00"}}, FakeApi())
check("a session still unpublished after 6 days is given up on, quietly", stale["state"]["pending"] == {} and stale["html"] == "", stale)
mixed = f1.run(utc(2026, 11, 2, 3, 0), utc(2026, 10, 31, 20, 0), {}, FakeApi(qualifying_for={19: Q19}, results_for={}))
check("qualifying published but race not: the qualifying table shows, the race waits (Mexico City today)", "<caption>Qualifying</caption>" in mixed["html"] and "Pole:" in mixed["html"]
      and "Mexico City Grand Prix race" in mixed["html"] and mixed["state"]["reported"] == ["2026-19-qualifying"], mixed["state"])
down = f1.run(SGT_MORNING, W, {}, FakeApi(results_for={18: RACE18}, broken=[("results", 18)]))
check("a source failure on one session is kept pending, counted, and does not raise", down["stats"]["failed"] == 1 and "2026-18-race" in down["state"]["pending"] and "Not published" in down["html"], down["stats"])
wrong = f1.run(SGT_MORNING, W, {}, FakeApi(results_for={18: RACE18}, dstand={17: DS17}))
check("standings labelled for another round are not shown as if current", "Drivers" not in wrong["html"] and "not up to date at the source" in wrong["html"], wrong["html"][-300:])
# What the source did on 2 Nov 2026: standings already labelled round 19, but still holding round 18's totals
MEX = {**RACE18, "round": "19", "raceName": "Mexico City Grand Prix"}
lag = f1.run(utc(2026, 11, 2, 3, 0), utc(2026, 10, 31, 23, 15), {}, FakeApi(results_for={19: MEX}, dstand={18: DS18, 19: {**DS18, "round": "19"}}))
check("round-19 label with round-18 points: the race table shows, the standings are withheld with a note, and they are queued",
      "<caption>Race</caption>" in lag["html"] and "Drivers" not in lag["html"] and "not up to date at the source" in lag["html"] and "2026-19-standings" in lag["state"]["pending"]
      and "2026-19-race" in lag["state"]["reported"], lag["state"])
check("the stale standings are not retried in the same run (calls stay low)", lag["stats"]["calls"] <= 9, lag["stats"])
caught = f1.run(utc(2026, 11, 3, 3, 0), utc(2026, 11, 2, 15, 15), lag["state"], FakeApi(results_for={19: MEX}, dstand={18: DS18, 19: DS19}))
check("when the source catches up, the next edition shows just the standings, under the race's name, and clears the queue",
      "Mexico City Grand Prix" in caught["html"] and "Drivers" in caught["html"] and "<caption>Race</caption>" not in caught["html"] and caught["state"]["pending"] == {}
      and "2026-19-standings" in caught["state"]["reported"], caught["state"])
still = f1.run(utc(2026, 11, 3, 3, 0), utc(2026, 11, 2, 15, 15), lag["state"], FakeApi(results_for={19: MEX}, dstand={18: DS18, 19: {**DS18, "round": "19"}}))
check("if it is still stale, nothing is shown but a muted line, and it stays queued", "Drivers" not in still["html"] and "Mexico City Grand Prix standings" in still["html"] and "2026-19-standings" in still["state"]["pending"], still["html"])
check("standings_match: exact points added passes, one driver off by a point fails, no previous round fails", f1.standings_match(DS18, DS17, ROWS) and not f1.standings_match(DS18, DS18, ROWS)
      and not f1.standings_match(DS18, None, ROWS) and not f1.standings_match(DS18, shift(DS17, [dict(ROWS[0], points="1")], "17", 1), ROWS))
sprint_w = [dict(x, points="1") for x in ROWS[:2]]
with_sprint = shift(shift(DS17, ROWS, "18", 1), sprint_w, "18", 1)  # round 18 = round 17 + the race + a sprint
check("on a sprint weekend the sprint's points count too: standings that include them match, and fail when the sprint is left out",
      f1.standings_match(with_sprint, DS17, ROWS, sprint_w) and not f1.standings_match(with_sprint, DS17, ROWS), "sprint")
sprint = f1.run(utc(2026, 10, 11, 2, 0), utc(2026, 10, 10, 8, 0), {}, FakeApi(sprint_for={17: SPR17}))
sc = cells(sprint["html"][sprint["html"].index("<caption>Sprint"):sprint["html"].index("</table>", sprint["html"].index("<caption>Sprint"))])
check("a sprint is shown as its own table with points 8 to 1 adding to 36; the qualifying that is not published waits (the race is not over yet)",
      sum(int(sc[i * 5 + 4]) for i in range(len(sc) // 5)) == 36 and sprint["stats"]["shown"] == 1 and sprint["stats"]["waiting"] == 1 and "Singapore Grand Prix qualifying" in sprint["html"],
      (sprint["stats"], sprint["html"][-200:]))
check("in the whole block the standings use the race's teams for each driver", lawson(out["html"][out["html"].index("Drivers"):]) == "RB")
check("no sessions in the window means no F1 block", f1.run(utc(2026, 10, 30, 2, 0), utc(2026, 10, 29, 15, 15), {}, FakeApi())["html"] == "")

# A whole sprint weekend through run(): Singapore, round 17 (real race and sprint results)
RACE17 = L("jolpica_results_17.json")["RaceTable"]["Races"][0]
spr_rows = SPR17["SprintResults"]
DS16 = DS18
DS17b = shift(shift(DS16, RACE17["Results"], "17", 1), spr_rows, "17", 1)
sw = f1.run(utc(2026, 10, 12, 2, 0), utc(2026, 10, 11, 12, 0), {}, FakeApi(results_for={17: RACE17}, sprint_for={17: SPR17}, dstand={16: DS16, 17: DS17b}))
check("sprint weekend: the race's standings include the sprint's points and are accepted", "Drivers" in sw["html"] and "2026-17-standings" not in sw["state"]["pending"] and "2026-17-race" in sw["state"]["reported"], sw["state"])
nosprint = f1.run(utc(2026, 10, 12, 2, 0), utc(2026, 10, 11, 12, 0), {}, FakeApi(results_for={17: RACE17}, sprint_for={}, dstand={16: DS16, 17: DS17b}))
check("if the sprint's points cannot be found, those standings do not add up and are held back", "Drivers" not in nosprint["html"] and "2026-17-standings" in nosprint["state"]["pending"], nosprint["state"])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
