"""Tests for D's review of 22 Nov 2026: Arsenal Women's Champions League and the League Cup (from the quarter-finals) in On Today, Test standouts judged on
the day, ice hockey under World Cups, Other Sports never telling a result twice, Major Injuries wording, the player of the match's main performance first,
the league's country in the headlines, every top-20 international, the 6:55 schedule and one Story Of The Day.
Run: .venv/bin/python scripts/test_morning9.py"""
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import around, cricket, events, fixtures, international  # noqa: E402
from kickoff.sources import espn  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


NOW = datetime(2026, 11, 18, 23, 0, tzinfo=timezone.utc)
plain = lambda h: re.sub(r"<[^>]+>", "", h)  # noqa: E731


def match(mid, home, away, hid, aid, when, stage="", completed=False):
    return {"id": mid, "home": {"id": hid, "name": home}, "away": {"id": aid, "name": away}, "kickoff": when.strftime("%Y-%m-%dT%H:%MZ"), "stage": stage,
            "completed": completed, "goals": [], "reds": []}


# 1. On Today: Arsenal Women's Champions League night and the League Cup from the quarter-finals
class Src:
    def __init__(self, by_league):
        self.by_league = by_league

    def football(self, lg, d):
        return [m for m in self.by_league.get(lg, []) if espn.parse_time(m["kickoff"]).date() == d]

    def table(self, lg):
        return []


later = NOW + timedelta(hours=5)
src = Src({espn.WOMENS_CL: [match("1", "Arsenal", "OL Lyonnes", "19973", "x1", later, "league-phase"), match("2", "Barcelona", "Servette", "x2", "x3", later, "league-phase")],
           espn.LEAGUE_CUP: [match("3", "Fulham", "Newcastle United", "x4", "x5", later, "quarterfinals"), match("4", "Brentford", "Swansea City", "x6", "x7", later, "fourth-round")]})
texts = [f["text"] for f in fixtures.football(src, NOW, NOW + timedelta(hours=24), 3) if f["sport"] == "football"]
check("Arsenal Women's Champions League game is in On Today; another club's is not", "Women's Champions League: Arsenal v OL Lyonnes" in texts and not any("Servette" in t for t in texts), texts)
check("a League Cup quarter-final is in, whoever plays; a fourth-round tie without Arsenal is not", "League Cup: Fulham v Newcastle United" in texts and not any("Swansea" in t for t in texts), texts)
check("a League Cup quarter-final is a knockout (it can make Don't Miss and the headlines)", events.football_stage("League Cup", {"stage": "quarterfinals"}) == "knockout"
      and events.football_stage("League Cup", {"stage": "final"}) == "final" and events.football_stage("League Cup", {"stage": "fourth-round"}) == "regular")

# 3. Test standouts: the day's
day1 = [{"runs": 250, "wickets": 5, "batting": [{"name": "Brendan Taylor", "r": 119, "b": 217}], "bowling": [{"name": "Naseer Khan", "w": 3, "r": 80}]}]
day2 = [{"runs": 339, "wickets": 10, "batting": [{"name": "Brendan Taylor", "r": 130, "b": 240}], "bowling": [{"name": "Naseer Khan", "w": 7, "r": 151}]},
        {"runs": 159, "wickets": 6, "batting": [], "bowling": []}]
taylor = {"kind": "century", "name": "Brendan Taylor", "team": "Zimbabwe", "against": "Afghanistan", "runs": 130, "balls": 240, "fours": 15, "sixes": 1, "not_out": False}
naseer = {"kind": "five-for", "name": "Naseer Khan", "team": "Afghanistan", "against": "Zimbabwe", "wickets": 7, "runs_conceded": 151, "overs": 44, "economy": 3.4}
got = cricket.day_standouts([taylor, naseer], day2, cricket.snapshot(day1))
check("Taylor's 119 becoming 130 (11 that day) is not a standout of the day", "Brendan Taylor" not in [o["name"] for o in got], got)
check("Naseer's 4 of the day's 5 wickets (and his five-for) is, and says so", [o["name"] for o in got] == ["Naseer Khan"] and "4 wickets today" in plain(cricket.standout_html(got[0])), got)
t200 = {**taylor, "runs": 205, "balls": 330}
d2b = [{**day2[0], "runs": 420, "batting": [{"name": "Brendan Taylor", "r": 205, "b": 330}]}] + day2[1:]
g2 = cricket.day_standouts([t200], d2b, cricket.snapshot(day1))
check("Taylor going on to 205 is: a double hundred reached that day, '86 runs today'", len(g2) == 1 and "86 runs today" in plain(cricket.standout_html(g2[0])), g2)
check("the first morning of a Test (nothing saved yet): every standout is new, with no 'today' note", [o.get("today") for o in cricket.day_standouts([taylor], day2, [])] == [None]
      and "today" not in plain(cricket.standout_html(cricket.day_standouts([taylor], day2, [])[0])))
quiet = [{"runs": 289, "wickets": 9, "batting": [{"name": "Brendan Taylor", "r": 119, "b": 217}, {"name": "Tail", "r": 30, "b": 50}], "bowling": [{"name": "Naseer Khan", "w": 3, "r": 80}]}]
check("a day without a standout performance: no Standouts for that Test", cricket.day_standouts([{**taylor, "runs": 119, "balls": 217}], quiet, cricket.snapshot(day1)) == [])

gill_prev = [{"runs": 368, "wkts": 10, "bat": {}, "bowl": {}}, {"runs": 239, "wkts": 1, "bat": {"KL Rahul": 93}, "bowl": {}}]
gill_now = [{"runs": 368, "wickets": 10, "batting": [], "bowling": []},
            {"runs": 486, "wickets": 4, "batting": [{"name": "KL Rahul", "r": 136, "b": 290}, {"name": "Shubman Gill", "r": 98, "b": 150}, {"name": "Rishabh Pant", "r": 55, "b": 70}],
             "bowling": []}]
cands = [{"kind": "century", "name": "KL Rahul", "team": "India", "runs": 136, "balls": 290, "fours": 9, "sixes": 2, "not_out": False},
         {"kind": "fifty", "name": "Shubman Gill", "team": "India", "runs": 98, "balls": 150, "fours": 12, "sixes": 0, "not_out": True},
         {"kind": "fifty", "name": "Rishabh Pant", "team": "India", "runs": 55, "balls": 70, "fours": 6, "sixes": 1, "not_out": False}]
check("22 Nov: Gill's 98 in a day of 247 is a standout though not a hundred; Rahul's hundred (43 that day) too; Pant's 55 (22% of the day) is not",
      [o["name"] for o in cricket.day_standouts(cands, gill_now, gill_prev)] == ["KL Rahul", "Shubman Gill"], cricket.day_standouts(cands, gill_now, gill_prev))

# 4. Ice hockey goes under World Cups
mk = lambda t, x: {"title": t, "text": x, "link": t, "source": "The Guardian", "published": NOW - timedelta(hours=3)}  # noqa: E731
sp = {c["title"][:10]: c["sport"] for c in around.candidates([mk("US beat Canada to win women's ice hockey world championship", "6-2 in the final in Denmark."),
                                                               mk("India win Hockey Asia Cup final", "India beat China in the hockey Asia Cup final.")], NOW)}
check("ice hockey is World Cups, field hockey stays Field hockey", sp.get("US beat Ca") == "worldcups" and sp.get("India win ") == "hockey", sp)

# 5. Other Sports: what was told goes to Claude, which drops a result already reported
seen_payload = {}


def fake_call(client, system, schema, payload, model=None):
    seen_payload["p"] = payload
    seen_payload["s"] = system
    return {"items": []}, {"input": 1, "output": 1}


real = around.notes.call_json
around.notes.call_json = fake_call
around.classify(object(), [{**mk("Littler beats Greaves", "Defending champion Luke Littler beat Beau Greaves 5-2."), "sport": "darts"}],
                ["Luke Littler opened his Grand Slam of Darts campaign by beating Beau Greaves."])
around.notes.call_json = real
check("Claude sees the last week's lines and the rule: the same result again is 'none', a new result with the same people is new",
      "already_reported:\n- Luke Littler opened" in seen_payload["p"] and "SAME result" in seen_payload["s"] and "new result involving the same people" in seen_payload["s"])

# 7. Major Injuries
inj = events.football_injuries([{"kind": "suspended", "name": "Igor Thiago Nascimento Rodrigues", "web_name": "Thiago", "team": "BRE", "detail": "Suspended until 5 Dec"},
                                {"kind": "out", "name": "Ezri Konsa Ngoyo", "web_name": "Konsa", "team": "ARS", "detail": "Knee injury"}])
check("'Igor Thiago (BRE): suspended until 5 Dec' (the name a fan knows, the status once)", inj[1]["text"] == "Igor Thiago (BRE): suspended until 5 Dec", inj)
check("'Ezri Konsa (ARS): out, Knee injury'", inj[0]["text"] == "Ezri Konsa (ARS): out, Knee injury", inj)
check("a single name stays single (Gabriel)", events.short_name("Gabriel dos Santos Magalhães", "Gabriel") == "Gabriel")

# 8. Player of the match: the performance that won it first
mz = {"innings": [{"batting": [{"name": "M", "r": 9, "b": 13, "out": "b X"}], "bowling": []}, {"batting": [], "bowling": [{"name": "M", "o": 17.0, "r": 38, "w": 3}]},
                  {"batting": [{"name": "M", "r": 59, "b": 93, "out": "c Y"}], "bowling": []}, {"batting": [], "bowling": [{"name": "M", "o": 20.0, "r": 55, "w": 3}]}]}
check("Muzarabani: bowling first, then the runs ('3/38 (17 ov) & 3/55 (20 ov) · 9 (13) & 59 (93)')", plain(cricket.potm_figures(mz, "M")) == "3/38 (17 ov) & 3/55 (20 ov) · 9 (13) & 59 (93)",
      plain(cricket.potm_figures(mz, "M")))
bat = {"innings": [{"batting": [{"name": "B", "r": 120, "b": 150, "out": "not out"}], "bowling": [{"name": "B", "o": 3.0, "r": 12, "w": 1}]}]}
check("a hundred and one wicket: batting first", plain(cricket.potm_figures(bat, "B")).startswith("120* (150)"), plain(cricket.potm_figures(bat, "B")))

# 9. The league's country in the headlines (outside England)
fr = {"completed": True, "home": {"id": "a", "name": "Troyes"}, "away": {"id": "b", "name": "Le Havre AC"}, "home_score": 3, "away_score": 1, "goals": [], "reds": [], "stage": ""}
s_ = events.football([("Ligue 1", [fr]), ("Premier League", [{**fr, "home": {"id": "c", "name": "Fulham"}}])], 5)
check("'Ligue 1 (France): Troyes 3–1 Le Havre AC'; the Premier League stays as it is", [x["text"] for x in s_] == ["Ligue 1 (France): Troyes 3–1 Le Havre AC", "Premier League: Fulham 3–1 Le Havre AC"],
      [x["text"] for x in s_])

# 10. Every top-20 international
top30 = {"teams": ["Spain", "Argentina", "England", "France", "Portugal", "Brazil", "Colombia", "Switzerland", "Netherlands", "Belgium", "Italy", "Norway", "Japan", "Morocco",
                   "Germany", "Mexico", "Denmark", "Croatia", "Uruguay", "Ecuador", "Austria", "Paraguay"]}
top = international.top20(top30)
check("the top 20 are the first 20 of the saved list (Ecuador in, Austria out)", "ecuador" in top and "austria" not in top and len(top) == 20)
g = international.headline_games([{**match("5", "Spain", "England", "s", "e", NOW, completed=True), "home_score": 2, "away_score": 3, "goals": [], "reds": []}],
                                 [("Friendly", [{**match("6", "Brazil", "Japan", "b", "j", NOW, completed=True), "home_score": 1, "away_score": 0},
                                                {**match("7", "Austria", "Wales", "a", "w", NOW, completed=True), "home_score": 1, "away_score": 0}])], top30)
check("Key Overnight Scores gets Spain v England (both top 20: a big night) and Brazil v Japan; Austria v Wales (neither) is not",
      [(n, [m["id"] for m in ms], [m["big_intl"] for m in ms]) for n, ms in g] == [("Nations League", ["5"], [True]), ("Friendly", ["6"], [True])], g)
sc = events.football(g, 6)
check("the headline reads 'Nations League: England 3–2 Spain', scored as a big night", sc[0]["text"] == "Nations League: England 3–2 Spain" and sc[0]["stage"] == "top", sc[0])
real_top = international.saved_top20
international.saved_top20 = lambda: top
src2 = Src({"fifa.friendly": [match("8", "Brazil", "Senegal", "b", "s", later), match("9", "Austria", "Wales", "a", "w", later)],
            "uefa.nations": [match("10", "Spain", "England", "s", "e", later)]})
ft = [f["text"] for f in fixtures.internationals(src2, NOW, NOW + timedelta(hours=24), 3)]
international.saved_top20 = real_top
check("On Today: 'Friendly: Brazil v Senegal' and 'Nations League: Spain v England'; not Austria v Wales", sorted(ft) == ["Friendly: Brazil v Senegal", "Nations League: Spain v England"], ft)

# 11. The schedule
wf = (ROOT / ".github/workflows/daily.yml").read_text()
check("the run is scheduled at 6:55am Singapore time (lands about 7:30-7:45)", '- cron: "55 22 * * *"' in wf)
check("the Mac's cricket backup runs at 6:40, before it", "<integer>6</integer><key>Minute</key><integer>40</integer>" in (ROOT / "scripts/com.thekickoff.cricket.plist").read_text())

# 12. One Story Of The Day
check("the section is called Story Of The Day and picks one", "Story Of The Day" in (ROOT / "kickoff/around.py").read_text() and "ONE story" in around.STORY_SYSTEM)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
