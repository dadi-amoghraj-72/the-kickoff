"""Tests for On Today and In The Week Ahead: which upcoming games matter, the sun/moon split in Singapore time and the Monday week. Run: .venv/bin/python scripts/test_ontoday.py"""
import copy
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import daily, fixtures, nba, ontoday  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%MZ")


def future(event, when, state="pre", name="STATUS_SCHEDULED"):
    """A real finished ESPN event turned into a game still to be played at `when`."""
    e = copy.deepcopy(event)
    e["date"] = iso(when)
    e["status"]["type"].update(name=name, state=state, completed=False, description="Scheduled", detail="Scheduled", shortDetail="Scheduled")
    for c in e["competitions"][0]["competitors"]:
        c["score"] = "0"
        c.pop("winner", None)
    e["competitions"][0].pop("details", None)
    return e


class Fake:
    """The Sources interface with canned answers."""

    def __init__(self, football=None, nba_events=(), cricket=(), f1=(), tennis=(), nfl=None, boom=()):
        self.fb, self.nb, self.cr, self.f, self.t, self.nf, self.boom = football or {}, list(nba_events), list(cricket), list(f1), list(tennis), nfl, set(boom)

    def _maybe(self, what):
        if what in self.boom:
            raise RuntimeError(what)

    def football(self, league, d):
        self._maybe("football")
        return [m for m in self.fb.get(league, []) if m["kickoff"][:10] == d.isoformat()]

    def table(self, league):
        return [{"id": "359", "rank": 1}, {"id": "367", "rank": 2}, {"id": "364", "rank": 3}, {"id": "363", "rank": 9}]

    def nba(self, d):
        self._maybe("nba")
        return {"events": [e for e in self.nb if e["_et"] == d.isoformat()]}

    def nfl(self, week=None, season_type=None):
        self._maybe("nfl")
        return self.nf or {"season": {"type": 2}, "week": {"number": 9}, "events": []}

    def mlb(self, d):
        return {"events": []}

    def cricket(self):
        self._maybe("cricket")
        return self.cr

    def f1(self, season):
        return self.f

    def tennis(self, now):
        return self.t


from kickoff.sources import espn  # noqa: E402

pl = json.load(open(FIX / "espn_pl_20261031.json"))["events"]
chelsea_mu = next(e for e in pl if {x["team"]["id"] for x in e["competitions"][0]["competitors"]} == {"363", "360"})
plain = next(e for e in pl if not ({x["team"]["id"] for x in e["competitions"][0]["competitors"]} & {"359", "382", "360", "364", "363", "367", "132", "124", "160", "111", "114", "110", "103", "2572", "83", "86", "1068"}))
now = utc(2026, 11, 5, 0, 0)          # 8am Singapore
end = ontoday.day_end(date(2026, 11, 5))
check("the next edition is 7am Singapore time the next day (23:00 UTC)", end == utc(2026, 11, 5, 23, 0))
check("sun is 7am to 11pm SGT, moon the rest", ontoday.tag(utc(2026, 11, 4, 23, 0)) == "sun" and ontoday.tag(utc(2026, 11, 5, 14, 59)) == "sun" and ontoday.tag(utc(2026, 11, 5, 15, 0)) == "moon"
      and ontoday.tag(utc(2026, 11, 5, 22, 59)) == "moon" and ontoday.tag(utc(2026, 11, 5, 23, 0)) == "sun")
check("times read like 8:30pm and 4am, in Singapore time", ontoday.clock(utc(2026, 11, 5, 12, 30)) == "8:30pm" and ontoday.clock(utc(2026, 11, 5, 20, 0)) == "4am")

# football: listed clubs yes, a game between two unlisted clubs no
fb = {"eng.1": [espn.parse_match(future(chelsea_mu, utc(2026, 11, 5, 12, 30)), "eng.1"), espn.parse_match(future(plain, utc(2026, 11, 5, 12, 30)), "eng.1")]}
got, failed = fixtures.collect(Fake(football=fb), now, end, 3)
texts = [f["text"] for f in got]
check("a thin Premier League day (two matches): both are listed, the unlisted pair too (Everton v Coventry at 4am, D 2026-11-06)", any("Chelsea" in t for t in texts) and any(plain["competitions"][0]["competitors"][0]["team"]["displayName"] in t for t in texts), texts)
def _clone(e, i):
    c = copy.deepcopy(e)
    c["id"] = str(i)
    return c
fb3 = {"eng.1": [espn.parse_match(future(chelsea_mu, utc(2026, 11, 5, 12, 30)), "eng.1"), espn.parse_match(future(plain, utc(2026, 11, 5, 12, 30)), "eng.1"),
                 espn.parse_match(future(_clone(plain, 9001), utc(2026, 11, 5, 12, 30)), "eng.1"), espn.parse_match(future(_clone(plain, 9002), utc(2026, 11, 5, 14, 0)), "eng.1")]}
got3, _ = fixtures.collect(Fake(football=fb3), now, end, 3)
texts3 = [f["text"] for f in got3]
check("a busy Premier League day (four matches): only a listed club's game is on, the unlisted ones are not", any("Chelsea" in t for t in texts3) and not any(plain["competitions"][0]["competitors"][0]["team"]["displayName"] in t for t in texts3), texts3)
check("the thin-day rule is the Premier League's alone: two unlisted La Liga games are never added", not [f for f in fixtures.collect(Fake(football={"esp.1": [espn.parse_match(future(plain, utc(2026, 11, 5, 12, 30)), "esp.1")]}), now, end, 3)[0] if f["sport"] == "football"])
check("a game already finished or outside the window is not listed", fixtures.collect(Fake(football={"eng.1": [espn.parse_match(chelsea_mu, "eng.1")]}), now, end, 3)[0] == [])

# Champions League: league phase needs a listed club, a knockout game always counts
cl = json.load(open(FIX / "espn_cl_20261021.json"))["events"]
other = next(e for e in cl if not ({x["team"]["id"] for x in e["competitions"][0]["competitors"]} & set(fixtures.clubs.CLUBS)))
ko = json.load(open(FIX / "espn_cl_ko_20260317.json"))["events"]
ko_other = next((e for e in ko if not ({x["team"]["id"] for x in e["competitions"][0]["competitors"]} & set(fixtures.clubs.CLUBS))), ko[0])
fb2 = {"uefa.champions": [espn.parse_match(future(other, utc(2026, 11, 5, 20, 0)), "uefa.champions"), espn.parse_match(future(ko_other, utc(2026, 11, 5, 20, 0)), "uefa.champions")]}
got, _ = fixtures.collect(Fake(football=fb2), now, end, 3)
stages = sorted(f["stage"] for f in got)
check("Champions League: a league-phase game without a listed club is dropped; a knockout game counts whoever plays", stages == ["knockout"] or stages == ["knockout", "regular"] and False, stages)

# NBA: regular season only D's five teams; playoffs all
nbs = json.load(open(FIX / "nba_scoreboards.json"))["2026-11-01"]["events"]


def et_of(when):
    return when.astimezone(fixtures.ET).date().isoformat()


reg = []
for e in nbs:
    f = future(e, utc(2026, 11, 5, 1, 0))
    f["_et"] = et_of(utc(2026, 11, 5, 1, 0))
    reg.append(f)
parsed = [nba.parse_game(e) for e in reg]
codes = {g["away"]["abbr"] for g in parsed} | {g["home"]["abbr"] for g in parsed}
got, _ = fixtures.collect(Fake(nba_events=reg), now, end, 3, mine_nba=set(nba.FIRST))
mine_games = [g for g in parsed if {g["away"]["abbr"], g["home"]["abbr"]} & set(nba.FIRST)]
check("NBA regular season: only games of D's five teams are On Today", len([f for f in got if f["sport"] == "nba"]) == len(mine_games), (len(got), len(mine_games)))
po = []
for e in nbs:
    f = future(e, utc(2026, 11, 5, 1, 0))
    f["_et"] = et_of(utc(2026, 11, 5, 1, 0))
    f["season"] = {"type": 3, "year": 2026}
    po.append(f)
got, _ = fixtures.collect(Fake(nba_events=po), now, end, 3, mine_nba=set())
check("NBA playoffs: every game counts, not only D's teams", len([f for f in got if f["sport"] == "nba"]) == len(po) and all(f["stage"] == "playoff" for f in got if f["sport"] == "nba"))

# F1: every session in the window
sched = json.load(open(FIX / "jolpica_schedule_2026.json"))["MRData"]["RaceTable"]["Races"]
got, _ = fixtures.collect(Fake(f1=sched), utc(2026, 10, 31, 12, 0), utc(2026, 11, 1, 23, 0), 5)
check("F1: qualifying and the race of the weekend are both listed, with their names", [f["text"] for f in got if f["sport"] == "f1"] == ["F1: Mexico City Grand Prix · Qualifying", "F1: Mexico City Grand Prix · Race"])

# cricket: India men yes, an unrelated bilateral no, India women no
drafts = [{"id": "e1", "name": "India vs New Zealand, 2nd ODI, India tour of New Zealand 2026", "teams": ["India", "New Zealand"], "matchType": "odi", "dateTimeGMT": "2026-11-05T02:00:00", "matchStarted": False, "matchEnded": False},
          {"id": "e2", "name": "Sri Lanka vs West Indies, 1st ODI, WI tour", "teams": ["Sri Lanka", "West Indies"], "matchType": "odi", "dateTimeGMT": "2026-11-05T03:00:00", "matchStarted": False, "matchEnded": False},
          {"id": "e3", "name": "India Women vs Australia Women, 1st ODI, Aus tour", "teams": ["India Women", "Australia Women"], "matchType": "odi", "dateTimeGMT": "2026-11-05T04:00:00", "matchStarted": False, "matchEnded": False}]
got, _ = fixtures.collect(Fake(cricket=drafts), now, end, 3)
cr = [f["text"] for f in got if f["sport"] == "cricket"]
check("cricket: every international of the test-playing nations is on (India men's, Sri Lanka v West Indies, the women's ODI too), in time order", len(cr) == 3 and "India v New Zealand" in cr[0] and "Sri Lanka v West Indies" in cr[1] and "Women's international" in cr[2], cr)
ipl = [{"id": "e4", "name": "Royal Challengers Bengaluru vs Mumbai Indians, 12th Match, Indian Premier League 2027", "teams": ["Royal Challengers Bengaluru", "Mumbai Indians"], "matchType": "t20", "dateTimeGMT": "2027-04-05T14:00:00", "matchStarted": False, "matchEnded": False},
       {"id": "e5", "name": "Delhi Capitals vs Gujarat Titans, 13th Match, Indian Premier League 2027", "teams": ["Delhi Capitals", "Gujarat Titans"], "matchType": "t20", "dateTimeGMT": "2027-04-05T14:00:00", "matchStarted": False, "matchEnded": False}]
got, _ = fixtures.collect(Fake(cricket=ipl), utc(2027, 4, 5, 0, 0), utc(2027, 4, 6, 0, 0), 3)
_cg = [f for f in got if f["sport"] == "cricket"]
check("IPL: every game is on (the one league kept, D, 2026-11-05) and D's team scores higher", len(_cg) == 2 and max(_cg, key=lambda f: f["score"])["mine"] is True, [(f["text"], f["score"]) for f in _cg])

# tennis: late rounds only
slam = {"name": "Australian Open", "major": True, "groupings": [{"grouping": {"slug": "mens-singles"}, "competitions": [
    {"round": {"displayName": "Quarterfinal"}, "date": "2027-01-27T03:00Z", "status": {"type": {"state": "pre"}}},
    {"round": {"displayName": "Quarterfinal"}, "date": "2027-01-27T08:00Z", "status": {"type": {"state": "pre"}}},
    {"round": {"displayName": "Round 3"}, "date": "2027-01-27T02:00Z", "status": {"type": {"state": "pre"}}}]}]}
got, _ = fixtures.collect(Fake(tennis=[slam]), utc(2027, 1, 27, 0, 0), utc(2027, 1, 27, 23, 0), 2)
tn = [f for f in got if f["sport"] == "tennis"]
check("tennis: the quarter-finals are one line at the first match's time; round 3 is not listed", len(tn) == 1 and "quarter-finals" in tn[0]["text"] and tn[0]["when"] == utc(2027, 1, 27, 3, 0))

# golf: a men's major that starts in the window
import json as _json  # noqa: E402
_gb = _json.loads((ROOT / "tests" / "fixtures" / "golf_masters_2025.json").read_text())
class _G(Fake):  # noqa: E302
    def golf(self, tour):
        return _gb if tour == "pga" else {"events": []}
got, _ = fixtures.collect(_G(), utc(2025, 4, 7, 0, 0), utc(2025, 4, 14, 0, 0), 0)
gf = [f for f in got if f["sport"] == "golf"]
check("golf: the Masters' start is a fixture for the week (In The Week Ahead), the day only, no time zone label", len(gf) == 1 and gf[0]["text"] == "Golf: Masters Tournament starts" and gf[0]["stage"] == "final", gf)
check("golf: a major that has already started, or starts after the window, is not listed", [f for f in fixtures.collect(_G(), utc(2025, 4, 11, 0, 0), utc(2025, 4, 14, 0, 0), 0)[0] if f["sport"] == "golf"] == [])

# games already under way are On Today too (D, 2026-11-05): a D's-team NBA game that tipped off before the edition, marked live and shown as "Under way"
lv = []
for e in nbs:
    f = future(e, utc(2026, 11, 4, 23, 30), state="in", name="STATUS_IN_PROGRESS")
    f["_et"] = et_of(utc(2026, 11, 4, 23, 30))
    lv.append(f)
got, _ = fixtures.collect(Fake(nba_events=lv), now, end, 3, mine_nba=set(nba.FIRST))
_lg = [f for f in got if f["sport"] == "nba"]
check("NBA under way: a game of D's teams that has started is listed with 'Under way' (others are not, as before)", len(_lg) == len(mine_games) and all("live" in f["flags"] and f["when"] == now and "Under way" in ontoday._line(f) for f in _lg), len(_lg))
got, _ = fixtures.collect(Fake(nba_events=[{**e, "status": {**e["status"], "type": {**e["status"]["type"], "state": "post", "name": "STATUS_FINAL"}}} for e in lv]), now, end, 3, mine_nba=set(nba.FIRST))
check("a game that has finished is never listed as under way", [f for f in got if f["sport"] == "nba"] == [])

# UFC cards and the badminton finals day (D, 2026-11-05)
_ufc = {"events": [{"id": "1", "name": "UFC 330: Jones vs. Miocic", "date": "2027-01-17T01:00Z", "status": {"type": {"state": "pre"}}, "competitions": [{"date": "2027-01-17T01:00Z"}, {"date": "2027-01-17T04:00Z"}]},
                   {"id": "2", "name": "PFL 3: A vs. B", "date": "2027-01-17T02:00Z", "status": {"type": {"state": "pre"}}, "competitions": [{"date": "2027-01-17T02:00Z"}]},
                   {"id": "3", "name": "UFC Fight Night: C vs. D", "date": "2027-01-10T01:00Z", "status": {"type": {"state": "post"}}, "competitions": [{"date": "2027-01-10T03:00Z"}]}]}
_wk = "{{Infobox badminton tournament\n| dates = 12–19 January 2027\n}}\n"
class _U(Fake):  # noqa: E302
    def ufc(self):
        return _ufc

    def wikitext(self, title):
        return _wk if title == "2027 India Open (badminton)" else ""
got, _ = fixtures.collect(_U(), utc(2027, 1, 16, 0, 0), utc(2027, 1, 18, 0, 0), 5)
uf = [f for f in got if f["sport"] == "ufc"]
check("UFC: a card still to come is one line at the main event's time; PFL and a finished card are not listed", len(uf) == 1 and uf[0]["text"] == "UFC 330: Jones vs. Miocic (main event)" and uf[0]["when"] == utc(2027, 1, 17, 4, 0), uf)
check("UFC: the main event at 4am UTC reads 12pm in Singapore", ">12pm<" in ontoday._line(uf[0]), ontoday._line(uf[0]))
got, _ = fixtures.collect(_U(), utc(2027, 1, 18, 20, 0), utc(2027, 1, 19, 23, 0), 1)
bd_ = [f for f in got if f["sport"] == "badminton"]
check("badminton: only the finals day of the event, the day alone (no time), listed on its last day", len(bd_) == 1 and bd_[0]["text"] == "Badminton: India Open finals day" and "dateonly" in bd_[0]["flags"] and "All day" in ontoday._line(bd_[0]) and "am" not in ontoday._line(bd_[0]).split("</span>")[0], bd_)
check("badminton: not listed on the other days of the event", [f for f in fixtures.collect(_U(), utc(2027, 1, 14, 0, 0), utc(2027, 1, 15, 0, 0), 3)[0] if f["sport"] == "badminton"] == [])

# cricket in progress: a Test on day three is listed every morning; a Test that ended on day four is not; a league other than the IPL is not
_live = [{"id": "t1", "name": "Bangladesh vs West Indies, 2nd Test, WI tour of Bangladesh 2026", "teams": ["Bangladesh", "West Indies"], "matchType": "test", "dateTimeGMT": "2026-11-03T04:00:00", "matchStarted": True, "matchEnded": False},
         {"id": "t2", "name": "Afghanistan vs Zimbabwe, 1st Test, tour", "teams": ["Afghanistan", "Zimbabwe"], "matchType": "test", "dateTimeGMT": "2026-11-01T04:00:00", "matchStarted": True, "matchEnded": True},
         {"id": "t3", "name": "Sydney Thunder Women vs Perth Scorchers Women, 11th Match, Women's Big Bash League", "teams": ["Sydney Thunder Women", "Perth Scorchers Women"], "matchType": "t20", "dateTimeGMT": "2026-11-05T08:10:00", "matchStarted": False, "matchEnded": False}]
got, _ = fixtures.collect(Fake(cricket=_live), now, end, 3)
_lv = [f for f in got if f["sport"] == "cricket"]
check("cricket (8am Singapore, between days): the Test is listed with the NEXT day and its start time, not 'Under way': day 3 starts at 12pm; the ended Test and the non-IPL league are not listed",
      len(_lv) == 1 and "Bangladesh v West Indies \u00b7 2nd Test \u00b7 Day 3" in _lv[0]["text"] and "live" not in _lv[0]["flags"] and _lv[0]["when"] == utc(2026, 11, 5, 4, 0) and ">12pm<" in ontoday._line(_lv[0]) and "Under way" not in ontoday._line(_lv[0]), [(f["text"], f["flags"], f["when"]) for f in _lv])
got, _ = fixtures.collect(Fake(cricket=_live), utc(2026, 11, 5, 6, 0), utc(2026, 11, 6, 0, 0), 3)
_lv2 = [f for f in got if f["sport"] == "cricket"]
check("cricket (2pm, play on): the same Test is 'Under way' on day 3", len(_lv2) == 1 and "live" in _lv2[0]["flags"] and "Under way" in ontoday._line(_lv2[0]) and "Day 3" in _lv2[0]["text"], [(f["text"], f["flags"]) for f in _lv2])
got, _ = fixtures.collect(Fake(cricket=_live), utc(2026, 11, 5, 20, 0), utc(2026, 11, 6, 0, 0), 3)
check("cricket (play over for the day, next start after the window): nothing is listed", [f for f in got if f["sport"] == "cricket"] == [])
_d = fixtures.multiday_day
_s0 = utc(2026, 11, 5, 3, 30)
check("multi-day days: before the start it is day 1 (not under way); during play under way; after play the next day and its start; after the last day nothing",
      _d(_s0, utc(2026, 11, 5, 2, 0)) == (1, False, _s0) and _d(_s0, utc(2026, 11, 5, 5, 0)) == (1, True, _s0) and _d(_s0, utc(2026, 11, 5, 23, 15)) == (2, False, utc(2026, 11, 6, 3, 30))
      and _d(_s0, utc(2026, 11, 6, 5, 0)) == (2, True, utc(2026, 11, 6, 3, 30)) and _d(_s0, utc(2026, 11, 9, 5, 0)) == (5, True, utc(2026, 11, 9, 3, 30)) and _d(_s0, utc(2026, 11, 9, 23, 0)) is None)
check("the 7:15am Singapore edition of a Test that began the day before reads 'Day 2' with the start at 11:30am Singapore (the 6 November case)",
      ontoday.clock(_d(_s0, utc(2026, 11, 5, 23, 15))[2]) == "11:30am" and _d(_s0, utc(2026, 11, 5, 23, 15))[0] == 2)

# a sport that breaks costs only itself
got, failed = fixtures.collect(Fake(football=fb, boom=("nba", "cricket")), now, end, 3)
check("a failing sport is skipped and reported; the others stay", any(f["sport"] == "football" for f in got), failed)

# html
html = ontoday.today_html([fixtures.fixture("football", "PL", "Premier League: Chelsea v Manchester United", utc(2026, 11, 5, 12, 30), 6),
                           fixtures.fixture("football", "CL", "Champions League: Slavia Prague v Arsenal", utc(2026, 11, 5, 20, 0), 9, True)])
check("On Today: 'While You're Up' with the sun, then 'Overnight' with the moon, times in SGT", html.index("While You") < html.index("Overnight") and "8:30pm" in html and "4am" in html and "☀" in html and "☾" in html, html)
check("a day with nothing in it gives no block", ontoday.today_html([]) == "")
many = [fixtures.fixture("nba", "NBA", f"NBA: game {i}", utc(2026, 11, 5, 1 + i % 10, 0), float(i)) for i in range(20)]
check("On Today never lists more than 12 lines; the cut keeps the highest scores, back in time order", len(ontoday.pick_today(many)) == 12 and min(f["score"] for f in ontoday.pick_today(many)) == 8.0)

# In The Week Ahead
base = utc(2026, 11, 9, 23, 0)
fx = [fixtures.fixture("football", "PL", "Premier League: Arsenal v Tottenham Hotspur", base + timedelta(days=4, hours=12), 12, True, "regular", {"derby", "clash"}),
      fixtures.fixture("football", "PL", "Premier League: Brentford v Fulham", base + timedelta(days=4, hours=12), 4.1, False, "regular", {"derby"}),
      fixtures.fixture("f1", "F1", "F1: Brazilian Grand Prix · Qualifying", base + timedelta(days=3), 9, False, "knockout"),
      fixtures.fixture("f1", "F1", "F1: Brazilian Grand Prix · Race", base + timedelta(days=4), 10, False, "final"),
      fixtures.fixture("nba", "NBA", "NBA: a at b", base + timedelta(days=1), 1.4, False, "regular"),
      fixtures.fixture("nba", "NBA", "NBA: stars", base + timedelta(days=2), 4.2, False, "regular", {"stars"}),
      fixtures.fixture("nba", "NBA", "NBA: Cavaliers at Hawks", base + timedelta(days=1), 6.0, True, "regular")]
w = [f["text"] for f in ontoday.watch_pick(fx)]
check("In The Week Ahead: D's teams, derbies and clashes, the F1 race (not its qualifying) and tracked stars facing each other are in; a plain regular game is not",
      "Premier League: Arsenal v Tottenham Hotspur" in w and "F1: Brazilian Grand Prix · Race" in w and "NBA: stars" in w and not any("Qualifying" in t for t in w) and "NBA: a at b" not in w and "NBA: Cavaliers at Hawks" not in w, w)
check("In The Week Ahead is grouped by day with a small heading each, times in SGT", ontoday.watch_html(fx).count('class="subhead"') == 2 and "In The Week Ahead" in ontoday.watch_html(fx))
check("In The Week Ahead is empty when nothing qualifies", ontoday.watch_html([fixtures.fixture("nba", "NBA", "x", base, 1.0)]) == "")

# the Monday: the week is added, and only on Mondays
mon = ontoday.build(Fake(f1=sched), utc(2026, 10, 25, 23, 15), date(2026, 10, 26), set(), set())
tue = ontoday.build(Fake(f1=sched), utc(2026, 10, 26, 23, 15), date(2026, 10, 27), set(), set())
check("Mondays collect the week ahead (the Mexico City race weekend falls in that week); other days collect nothing", any(f["sport"] == "f1" for f in mon["watch"]) and tue["watch"] == [], [f["text"] for f in mon["watch"]])
check("a Tuesday never has In The Week Ahead", "In The Week Ahead" not in tue["html"])

# the edition
ed = daily.build_edition(utc(2026, 11, 4, 23, 15), date(2026, 11, 5), {}, [], today=lambda n, d, s: {"html": "<h3>x</h3>", "failed": ["nba"]})
check("the edition carries On Today after The Big Stuff, and reports a sport that failed", any(s["id"] == "on-today" for s in ed["edition"]["sections"]) and "on today: nba" in ed["problems"], ed["problems"])
ed2 = daily.build_edition(utc(2026, 11, 4, 23, 15), date(2026, 11, 5), {}, [], today=lambda n, d, s: 1 / 0)
check("a broken On Today never breaks the edition", any("on today" in p for p in ed2["problems"]))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
