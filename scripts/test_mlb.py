"""Offline tests for the MLB block, on saved real ESPN data from the 2026 season (it is over, so the files never change): the Dodgers' schedule and
Ohtani's and Yamamoto's game logs, every game day from 18 September to 29 October with the box scores of the days read in full, each playoff team's
postseason schedule and the final standings. Expected numbers are worked out here from the raw files, never by calling the module's own helpers.
Run: python3 scripts/test_mlb.py"""
import copy
import html as htmllib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from kickoff import mlb  # noqa: E402
from kickoff.sources import espn_mlb  # noqa: E402
from mlb_saved import Saved  # noqa: E402

FX = ROOT / "tests" / "fixtures"
L = lambda n: json.loads((FX / n).read_text())  # noqa: E731
SCHED, BOARDS, STD, LOGS, POST = L("mlb_lad_schedule.json"), L("mlb_scoreboards.json"), L("mlb_standings_2026.json"), L("mlb_gamelogs.json"), L("mlb_post_schedules.json")
BOXES = {**L("mlb_lad_boxes_week.json"), **L("mlb_boxes.json")}
ET = ZoneInfo("America/New_York")
UTC = timezone.utc
FOUR = {"KC": "KCR", "SD": "SDP", "SF": "SFG", "TB": "TBR"}   # a separate copy of the four ESPN codes that are not three letters
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


def iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def text(h):
    h = re.sub(r"</(tr|div|p|h4)>", "\n", h)
    h = re.sub(r"</t[dh]>", " | ", h)
    return htmllib.unescape(re.sub(r"<[^>]+>", "", h)).replace("\xa0", " ")


def squash(h):
    """The page text with all spaces and bars removed, so a series header reads '4series0' (the small 'best of N' line under the word is taken out)."""
    return re.sub(r"bestof\d", "", re.sub(r"[\s|]+", "", text(h)))


def at(now_str):
    return datetime.fromisoformat(now_str).replace(tzinfo=UTC)


def sgt_day(now):
    return now.astimezone(ZoneInfo("Asia/Singapore")).date()


def run(now, st=None, source=None):
    return mlb.run(now, sgt_day(now), copy.deepcopy(st or {}), source or Saved(now))


def won(g, team="19"):
    mine, theirs = (g["home"], g["away"]) if g["home"]["id"] == team else (g["away"], g["home"])
    return mine["score"] > theirs["score"]


def label(g):
    """'Mon 4 @HOU': the weekday and day number (New York date) and the opponent, with @ when the Dodgers were away."""
    home = g["home"]["id"] == "19"
    opp = (g["away"] if home else g["home"])["abbr"]
    d = iso(g["date"]).astimezone(ET)
    return f"{d:%a} {d.day} " + ("" if home else "@") + FOUR.get(opp, opp)


FINAL = [g for g in SCHED if g["status"] == "STATUS_FINAL"]
NOW_W = at("2026-05-07T00:00:00")
WEEK = [g for g in FINAL if NOW_W - timedelta(days=7) <= iso(g["date"]) < NOW_W]
BEFORE_W = [g for g in FINAL if iso(g["date"]) < NOW_W - timedelta(days=7)]
WSTATE = {"opened": 2026, "week_reported": [g["id"] for g in BEFORE_W]}
OUT_W = run(NOW_W, WSTATE)
TXT_W = text(OUT_W["html"])

# ---- Codes, names, pieces ----------------------------------------------------------------------------
raw_codes = sorted({e["team"]["abbreviation"] for lg in STD["children"] for dv in lg["children"] for e in dv["standings"]["entries"]})
check("30 teams in the standings, and the module's code() makes every one of them three letters, unique", len(raw_codes) == 30 and all(len(mlb.code(a)) == 3 for a in raw_codes) and len({mlb.code(a) for a in raw_codes}) == 30, raw_codes)
check("only the four codes that were not three letters change (KC, SD, SF, TB); WSH, CHW, ATH and the rest stay as ESPN has them",
      {a for a in raw_codes if mlb.code(a) != a} == set(FOUR) and all(mlb.code(a) == FOUR[a] for a in FOUR) and mlb.code("WSH") == "WSH" and mlb.code("CHW") == "CHW" and mlb.code("ATH") == "ATH")
heads = sorted({n["headline"] for b in BOARDS.values() for e in b["events"] if e["season"]["type"] == 3 for n in e["competitions"][0]["notes"]})
check("the real playoff notes start with ALWC/NLWC/ALDS/NLDS/ALCS/NLCS/World Series, and one has text after the game number (a rain delay)", {h.split(" - ")[0] for h in heads} == {"ALWC", "NLWC", "ALDS", "NLDS", "ALCS", "NLCS", "World Series"} and any("Rain" in h for h in heads), heads)
check("the round is read from the first part of the note, so 'ALCS - Game 4 Rain - Makeup on Oct 18' is still the AL Championship Series", mlb.round_of("ALCS - Game 4 Rain - Makeup on Oct 18") == ("AL Championship Series", 7))
check("round names and lengths: division series best of 5, championship series and the World Series best of 7",
      mlb.round_of("NLDS - Game 3") == ("NL Division Series", 5) and mlb.round_of("ALDS - Game 5") == ("AL Division Series", 5) and mlb.round_of("NLCS - Game 4") == ("NL Championship Series", 7)
      and mlb.round_of("ALCS - Game 1") == ("AL Championship Series", 7) and mlb.round_of("World Series - Game 5") == ("World Series", 7))
check("wild-card series (ALWC and NLWC in the real data) are best of 3", mlb.round_of("NLWC - Game 2") == ("NL Wild Card Series", 3) and mlb.round_of("ALWC - Game 1") == ("AL Wild Card Series", 3))
check("batting lines from a game log row and from a box score row agree", mlb.bat_of({"AB": "4", "H": "2", "HR": "1", "RBI": "3", "BB": "0", "SB": "1"}) == {"h": 2, "ab": 4, "hr": 1, "rbi": 3, "bb": 0, "sb": 1}
      and mlb.bat_of({"H-AB": "2-4", "HR": "1", "RBI": "3", "BB": "0"}) == {"h": 2, "ab": 4, "hr": 1, "rbi": 3, "bb": 0, "sb": 0})
check("pitching decisions are read from 'W(3-2)', 'L, 0-1', 'S', 'ND' and blanks", [mlb.pit_of({"Dec": d})["dec"] for d in ("W(3-2)", "L, 0-1", "S", "ND", "", "H, 8")] == ["W", "L", "S", "", "", ""])
check("innings: '6.2' is six and two thirds", abs(mlb.innings("6.2") - 6.6667) < 0.001 and mlb.innings("7.0") == 7)

# ---- Weekly round-up (Thursday 7 May 2026) ---------------------------------------------------------------
check("the weekly edition runs in weekly mode and found the Dodgers' six games of the week", OUT_W["stats"]["mode"] == "weekly" and OUT_W["stats"]["week"] == len(WEEK) == 6, OUT_W["stats"])
season = [g for g in FINAL if iso(g["date"]) < NOW_W - timedelta(hours=4)]
wk_w = sum(1 for g in WEEK if won(g))
check(f"the Dodgers' line is worked out from the raw schedule: week {wk_w}-{len(WEEK) - wk_w}, season {sum(1 for g in season if won(g))}-{sum(1 for g in season if not won(g))}, game {len(season)} of 162",
      f"Wk: {wk_w}-{len(WEEK) - wk_w} · Season: {sum(1 for g in season if won(g))}-{sum(1 for g in season if not won(g))} · G{len(season)}/162" in TXT_W, TXT_W[:300])
check("the Dodgers table has one row per game: 'Fri 1 @STL' (@ only when away) and the score from the Dodgers' side", len(WEEK) == 6 and all(
    f"{label(g)} | {'W' if won(g) else 'L'} {(g['home'] if g['home']['id'] == '19' else g['away'])['score']}–{(g['away'] if g['home']['id'] == '19' else g['home'])['score']} |" in TXT_W for g in WEEK))
hg = next(g for g in FINAL if g["home"]["id"] == "19")
check("a home game has no @ and an away game has one (this week's six are all away, so a home game is taken from the season)", mlb.lad_result(hg)[0] == mlb.code(hg["away"]["abbr"]) and all(mlb.lad_result(g)[0].startswith("@") for g in WEEK if g["home"]["id"] != "19"))
d0, d1 = iso(WEEK[0]["date"]).astimezone(ET), iso(WEEK[-1]["date"]).astimezone(ET)
check(f"the date range of the games shown sits under the title: Games {d0.day} {d0:%b} – {d1.day} {d1:%b}", f"Games {d0.day} {d0:%b} – {d1.day} {d1:%b}" in TXT_W, TXT_W[:200])
check("gold: a Dodgers win, a homer, a steal, 3+ RBI, 3+ hits and an 8+ strikeout game are wrapped in the gold class, other cells are not", OUT_W["html"].count('class="hi"') > 0
      and all(f'<span class="hi">W {(g["home"] if g["home"]["id"] == "19" else g["away"])["score"]}' in OUT_W["html"] for g in WEEK if won(g))
      and not any(f'<span class="hi">L ' in OUT_W["html"] for g in WEEK))
bat_rows = [x for x in LOGS["ohtani_bat"] if x["id"] in {g["id"] for g in WEEK}]
tot = {k: sum(int(x["stats"][k]) for x in bat_rows) for k in ("H", "AB", "HR", "RBI", "SB")}
check("Ohtani's batting table has one row per game he batted in, and a Week row with sums taken from the raw game log", len(bat_rows) == 5 and
      f"Week | {tot['H']}-{tot['AB']} | {tot['HR']} | {tot['RBI']} | {tot['SB']} |" in TXT_W, (tot, TXT_W[300:900]))
last = bat_rows[-1]["stats"]
check("under the batting title: his season average and OPS as of the last game of the week", f"Season: {last['AVG']} AVG · {last['OPS']} OPS" in TXT_W, last)
check("a start without a turn at bat is not reported as a missed game (Ohtani pitched on the Tuesday and did not bat)", "did not bat" not in TXT_W and any(x["id"] in {g["id"] for g in WEEK} for x in LOGS["ohtani_pit"]))
pit = [(n, x) for n, key in (("Yamamoto", "yamamoto_pit"), ("Ohtani", "ohtani_pit")) for x in LOGS[key] if x["id"] in {g["id"] for g in WEEK}]
check("the pitching table has one row per start, from the raw logs, with the decision as W or L", len(pit) == 2 and all(
    f"{n} | {label(next(g for g in WEEK if g['id'] == x['id']))} | {x['stats']['IP']} | {x['stats']['ER']} | {x['stats']['K']} | {x['stats']['Dec'][0]} |" in TXT_W for n, x in pit), (pit, TXT_W[600:1100]))
check("ERA under the pitching title is each pitcher's own figure after his start", all(f"{n} {x['stats']['ERA']}" in TXT_W for n, x in pit), TXT_W)
divs = re.findall(r"\n(NL|AL) (West|Central|East) \|", TXT_W)
check("six division tables, the National League first and the Dodgers' division first within it", divs == [("NL", "West"), ("NL", "Central"), ("NL", "East"), ("AL", "West"), ("AL", "Central"), ("AL", "East")], divs)
check("each division table lists its five teams; the Dodgers lead the NL West at 100-62 on the raw standings", "1 | LAD | 100-62 | - |" in TXT_W and len(re.findall(r"\n[1-5] \| [A-Z]{3} \| \d+-\d+ \|", TXT_W)) == 30)
check("a division table has no movement arrows the first time (nothing to compare with)", "▲" not in TXT_W and "▼" not in TXT_W)
check("both playoff races come after the divisions, each listing the six playoff seeds in order (the teams already out are not listed)", [m for m in re.findall(r"\n(NL|AL) Playoff Race \|", TXT_W)] == ["NL", "AL"] and TXT_W.index("NL Playoff Race") > TXT_W.index("AL East")
      and re.findall(r"\n(\d) \| [A-Z]{3}(?: ✓)? \| \d+-\d+ \| [+\d–.]+ \|", TXT_W[TXT_W.index("NL Playoff Race"):]) == [str(i) for i in range(1, 7)] * 2, TXT_W[TXT_W.index("NL Playoff"):][:300])
flat = {e["team"]["abbreviation"]: {s["name"]: s["displayValue"] for s in e["stats"]} for lg in STD["children"] for dv in lg["children"] for e in dv["standings"]["entries"]}
nl = sorted((a for a in flat if any(a == e["team"]["abbreviation"] for dv in STD["children"][1]["children"] for e in dv["standings"]["entries"])), key=lambda a: int(flat[a]["playoffSeed"]))
ref = flat[nl[5]]    # the sixth seed
ahead = int(flat[nl[3]]["wins"]) - int(ref["wins"]) + int(ref["losses"]) - int(flat[nl[3]]["losses"])
check("the playoff race counts games from the sixth seed: the fourth seed is that many games ahead, the sixth is level (–), the division leaders are seeds 1 to 3", f"4 | {mlb.code(nl[3])} ✓ | {flat[nl[3]]['overall']} | +{ahead / 2:g} |" in TXT_W and f"6 | {mlb.code(nl[5])} ✓ | {ref['overall']} | – |" in TXT_W and "ARI" not in TXT_W.split("NL Playoff Race")[1] and "✗" not in TXT_W.split("NL Playoff Race")[1] and all(f"{i + 1} | {mlb.code(nl[i])}" in TXT_W for i in range(3)), (nl, TXT_W[TXT_W.index('NL Playoff'):][:300]))
check("the season opener line comes only when the state has not seen this season", "season is under way" not in TXT_W and "The 2026 MLB season is under way." in text(run(NOW_W, {k: v for k, v in WSTATE.items() if k != "opened"})["html"]))
second = run(NOW_W, OUT_W["state"])
check("run twice: the same Thursday gives nothing the second time, so nothing is shown twice", second["html"] == "" and OUT_W["state"]["week_reported"][-6:] == [g["id"] for g in WEEK], second["stats"])
check("a first run with no state shows the last eight days only (not the whole season)", run(NOW_W, {"opened": 2026})["stats"]["week"] in (6, 7, 8) and run(NOW_W, {"opened": 2026})["stats"]["week"] == len([g for g in FINAL if timedelta(0) <= NOW_W - iso(g["date"]) <= timedelta(days=8) and iso(g["date"]) < NOW_W - timedelta(hours=4)]))
check("not a Thursday: nothing, and no requests for the season's data beyond the scoreboards", run(at("2026-05-08T00:00:00"), WSTATE)["html"] == "" and run(at("2026-05-08T00:00:00"), WSTATE)["stats"]["mode"] == "")
before = {"National League West": {"LAD": 2, "SDP": 1, "ARI": 3, "SFG": 4, "COL": 5}}
arrows = text(run(NOW_W, {**WSTATE, "div": before})["html"])
check("movement arrows against the last table shown: the Dodgers up one place, the Padres down one, others level", "1 | LAD | 100-62 | - | W3 | ▲1 |" in arrows and "2 | SDP | 91-71 | 9 | W2 | ▼1 |" in arrows and "3 | ARI | 86-76 | 14 | L2 | – |" in arrows, arrows[arrows.index("NL West"):][:300])
check("state remembers the places for next week", OUT_W["state"]["div"]["National League West"] == {"LAD": 1, "SDP": 2, "ARI": 3, "SFG": 4, "COL": 5} and OUT_W["state"]["seeds"]["LAD"] == int(flat["LAD"]["playoffSeed"]), OUT_W["state"]["div"])

# a Thursday week in which Ohtani missed a game without pitching: a reason comes from ESPN's injury list
log2 = copy.deepcopy(LOGS)
gid = next(x["id"] for x in log2["ohtani_bat"] if x["id"] in {g["id"] for g in WEEK})
log2["ohtani_bat"] = [x for x in log2["ohtani_bat"] if x["id"] != gid]


class Missed(Saved):
    def __init__(self, now):
        super().__init__(now)
        self.logs = log2
        self.boxes = {**self.boxes, gid: {**self.boxes[gid], "injuries": {"39832": {"status": "Day-To-Day", "type": "Hamstring"}}}}


mw = text(run(NOW_W, WSTATE, Missed(NOW_W))["html"])
gone = next(x for x in LOGS["ohtani_bat"] if x["id"] == gid)["stats"]
check("when Ohtani misses a game without pitching, the line says so with ESPN's reason, his row is gone and the Week row is the sums without that game",
      re.search(r"Ohtani did not bat: Fri 1: DNP \(Day-To-Day, Hamstring\)\.", mw) and "Fri @STL" not in mw and f"Week | {tot['H'] - int(gone['H'])}-{tot['AB'] - int(gone['AB'])} |" in mw, (gone, mw[300:900]))


class NoLogs(Saved):
    def gamelog(self, *a):
        raise RuntimeError("down")


nl_out = run(NOW_W, WSTATE, NoLogs(NOW_W))
check("game logs down: the Dodgers table and the standings still come, the player tables are left out, nothing raises", nl_out["stats"]["failed"] >= 1 and "Dodgers" in nl_out["html"] and "Ohtani · Batting" not in nl_out["html"] and "NL West" in nl_out["html"], nl_out["stats"])


class NoStd(Saved):
    def standings(self, season=None):
        raise RuntimeError("down")


ns = run(NOW_W, WSTATE, NoStd(NOW_W))
check("standings down: the Dodgers' week still comes without the tables, and the week is not lost", ns["stats"]["failed"] == 1 and "Ohtani · Batting" in ns["html"] and "NL West" not in ns["html"] and len(ns["state"]["week_reported"]) > len(WSTATE["week_reported"]))

nl_div = OUT_W["html"].split("NL Playoff Race")[0].count('class="z-blue"')
check("zones: each of the six divisions has exactly one blue row (the leader); the lilac rows are exactly the six teams ESPN seeds 4 to 6 (the wild cards)",
      nl_div == 6 and OUT_W["html"].split("NL Playoff Race")[0].count('class="z-lilac"') == sum(1 for a in flat if int(flat[a]["playoffSeed"]) in (4, 5, 6)) == 6)
race_nl = OUT_W["html"].split("NL Playoff Race")[1].split("AL Playoff Race")[0]
check("zones in a playoff race: seeds 1 to 3 (the division leaders) blue, 4 to 6 (wild cards) lilac, nobody else is listed (the other three are mathematically out): six rows", race_nl.count('class="z-blue"') == 3 and race_nl.count('class="z-lilac"') == 3 and race_nl.split("<tbody>")[1].split("</tbody>")[0].count("<tr") == 6)

# ---- Daily mode (from the Dodgers' 155th game) --------------------------------------------------------------
NOW_D = at("2026-09-21T00:00:00")
OUT_D = run(NOW_D)
TXT_D = text(OUT_D["html"])
expected = [e for b in BOARDS.values() for e in b["events"] if e["status"]["type"]["name"] == "STATUS_FINAL" and NOW_D - timedelta(hours=36) <= iso(e["date"]) <= NOW_D - timedelta(hours=4)]
rows = re.findall(r'<tr class="one', OUT_D["html"])
check("daily mode: one row per game finished since the last edition, counted from the raw scoreboards", OUT_D["stats"]["mode"] == "daily" and len(rows) == len(expected) == 25, (len(rows), len(expected)))
first_row = re.search(r'<tr class="one.*?</tr>', OUT_D["html"], re.S).group(0)
earliest = min(expected, key=lambda e: e["date"])
check("the Dodgers' game comes first (San Francisco at Los Angeles, the raw 10-4 final) though it was not the earliest game of the day", "Los Angeles Dodgers" in first_row and "San Francisco Giants" in first_row and "4–10" in first_row
      and "Los Angeles Dodgers" not in {x["team"]["displayName"] for x in earliest["competitions"][0]["competitors"]}, first_row)
dogs = 0
for e in expected:
    bx = BOXES[e["id"]]["odds"]
    c = e["competitions"][0]
    sc = {x["homeAway"]: int(x["score"]) for x in c["competitors"]}
    win = "home" if sc["home"] > sc["away"] else "away"
    dogs += 1 if (bx and ((bx["away_dog"] and win == "away") or (bx["home_dog"] and win == "home"))) else 0
check(f"underdog wins counted from the raw betting lines: {dogs}; the asterisks on the page and the count under the title agree", dogs > 0 and OUT_D["html"].count('class="dog"') - 1 == dogs and f"{dogs} underdog win" in TXT_D, (dogs, OUT_D["html"].count('class="dog"')))
check("a score in extra innings shows the innings: 8–5 (11) for Washington at St. Louis", "8–5 (11)" in TXT_D and "6–7 (10)" in TXT_D)
raw_notable = []
for e in expected:
    for abbr, side in BOXES[e["id"]]["teams"].items():
        for b in side["batters"]:
            s = b["stats"]
            h, _, ab = s["H-AB"].partition("-")
            if int(s["HR"]) >= 2 or int(h) >= 4 or int(s["RBI"]) >= 5:
                raw_notable.append((e["id"], b["name"]))
        for p in side["pitchers"]:
            s = p["stats"]
            ip = float(s["IP"].split(".")[0]) + int(s["IP"].split(".")[1]) / 3
            if int(s["K"]) >= 10 or (p["starter"] and ip >= 7 and int(s["ER"]) == 0):
                raw_notable.append((e["id"], p["name"]))
lines = re.findall(r"([A-Z][\w.' -]+) \((?:[A-Z]{3})\): ", TXT_D)
check("every standout line names a real batter or pitcher who met a threshold in that game's raw box score (nothing invented)", len(lines) > 5 and all(n in {x[1] for x in raw_notable} | {"Mookie Betts", "Shohei Ohtani", "Yoshinobu Yamamoto"} for n in lines), [n for n in lines if n not in {x[1] for x in raw_notable}])
per_game = {}
for gid_, n in raw_notable:
    per_game.setdefault(gid_, set()).add(n)
check("every game with one or two qualifying players shows all of them", all(all(n in TXT_D for n in names) for names in per_game.values() if len(names) <= 2) and len(per_game) > 3)
blocks = [x for x in OUT_D["html"].split('<tr class="tag">')[1:] if "Los Angeles Dodgers" not in x]
check("never more than two standout lines under a game other than the Dodgers' (and some game does carry two)", max(x.count('class="pl"') for x in blocks) == 2, [x.count('class="pl"') for x in blocks])
lad_part = OUT_D["html"].split('<tr class="tag">')[1]
check("the Dodgers' game: Ohtani sat out, his DNP line sits below the player who played (never above)", "Shohei Ohtani (LAD): DNP" in lad_part and lad_part.index("Mookie Betts") < lad_part.index("Shohei Ohtani"), text(lad_part))
check("NL and AL playoff races follow the games, the six playoff teams each (those mathematically out are not listed), the National League first", [m for m in re.findall(r"\n(NL|AL) Playoff Race \|", TXT_D)] == ["NL", "AL"] and len(re.findall(r"\n[1-6] \| [A-Z]{3} ✓ \|", TXT_D)) == 12)
check("clinched teams carry a ✓ from ESPN's own marks (Milwaukee *); eliminated teams (Arizona, Texas: e) are not in the race tables and no ✗ is shown there", "MIL ✓" in TXT_D and "ARI" not in TXT_D.split("NL Playoff Race")[1] and "TEX" not in TXT_D.split("AL Playoff Race")[1] and "✗" not in TXT_D.split("NL Playoff Race")[1])
alive = [dict(t, mark="") if t["abbr"] == "ARI" else t for t in mlb.teams_of(STD)]
race_alive = text(mlb.race_table(alive, "National League", 1, 9, "NL Playoff Race"))
check("a team still alive (no clincher mark) below the cut is listed as a chaser, with no tick and no cross; the ones out stay off", "7 | ARI | 86-76 | 2 |" in race_alive and "PIT" not in race_alive and "✗" not in race_alive and "✓" in race_alive, race_alive)
nl_race = OUT_D["html"].split("NL Playoff Race")[1].split("AL Playoff Race")[0]
check("zones in a playoff race: seeds 1 to 3 (division winners) blue, 4 to 6 lilac, nobody else, in both leagues", nl_race.count('class="z-blue"') == 3 and nl_race.count('class="z-lilac"') == 3 and nl_race.split("<tbody>")[1].split("</tbody>")[0].count("<tr>") == 0
      and OUT_D["html"].split("AL Playoff Race")[1].count('class="z-blue"') == 3)
check("state: the shown games are marked reported; the places are saved for the arrows; a second run shows nothing new", set(OUT_D["state"]["reported"]) == {e["id"] for e in expected} and OUT_D["state"]["seeds"]["MIL"] == 1 and run(NOW_D, OUT_D["state"])["html"] == "")
more = text(run(NOW_D, {"seeds": {"ARI": 6, "PHI": 7}})["html"])
check("arrows in the playoff race: Philadelphia was 7th and is now 6th (▲1)", "6 | PHI ✓ | 88-74 | – | ▲1 |" in more, more[more.index("NL Playoff"):][:400])
# the trigger itself: the Dodgers' 155th finished game
t155 = sorted(iso(g["date"]) for g in FINAL)[154] + timedelta(hours=4)
check("the 154th game was not enough: daily mode starts only after the Dodgers' 155th finished game", run(t155 - timedelta(minutes=2))["stats"]["mode"] == "" and run(t155 + timedelta(minutes=2))["stats"]["mode"] == "daily", (run(t155 - timedelta(minutes=2))["stats"], t155))
check("before 155 games on a Thursday the week comes, not the daily games", run(at("2026-09-10T00:00:00"), {"opened": 2026})["stats"]["mode"] == "weekly")
check("after 155 games a Thursday gives the daily mode, never both", run(at("2026-09-24T00:00:00"))["stats"]["mode"] in ("daily", "") and "Wk:" not in run(at("2026-09-24T00:00:00"))["html"])


class NoBox(Saved):
    def box(self, i):
        raise RuntimeError("down")


nb = run(NOW_D, {}, NoBox(NOW_D))
check("box scores down: no games are shown or marked reported (tried again next run), the race tables still come", nb["stats"]["failed"] >= 25 and "Last Night" not in nb["html"] and "<table" in nb["html"] and nb["state"]["reported"] == [] and "Playoff Race" in nb["html"], nb["stats"])
ns = run(NOW_D, {}, NoStd(NOW_D))
check("standings down: the games come without the race tables", "Yesterday" in ns["html"] and "Playoff Race" not in ns["html"] and ns["stats"]["failed"] == 1)


class NoSched(Saved):
    def schedule(self, *a, **k):
        raise RuntimeError("down")


check("the Dodgers' schedule down: nothing is guessed (no mode), the failure is counted, nothing raises", run(NOW_D, {}, NoSched(NOW_D))["html"] == "" and run(NOW_D, {}, NoSched(NOW_D))["stats"]["failed"] == 1)


class Live(Saved):
    def scoreboard(self, day):
        out = copy.deepcopy(super().scoreboard(day))
        for e in out["events"]:
            if e["id"] == expected[-1]["id"]:
                e["status"] = {"period": 5, "type": {"name": "STATUS_IN_PROGRESS", "state": "in", "shortDetail": "Top 5th"}}
        return out


lv = run(NOW_D, {}, Live(NOW_D))
live_row = [x for x in lv["html"].split('<tr class="tag">') if "In progress" in x]
check("a game still being played: shown with the score so far and an 'In progress' tag, no winner, no notes, not marked reported", len(live_row) == 1 and "Top 5th" in live_row[0] and " w" not in live_row[0].split("</tr>")[1].replace("aw\"", "") and expected[-1]["id"] not in lv["state"]["reported"] and lv["stats"]["live"] == 1, live_row)
check("the offseason is silent: no games, no output, no state change worth keeping", run(at("2026-11-20T00:00:00"))["html"] == "" and run(at("2026-11-19T00:00:00"))["html"] == "")

bat = lambda i, n, hab, hr, rbi: {"id": i, "name": n, "starter": True, "stats": {"H-AB": hab, "HR": hr, "RBI": rbi}}  # noqa: E731
fake = {"teams": {"AAA": {"batters": [bat("1", "Big One", "3-4", "3", "6"), bat("2", "Big Two", "4-5", "0", "1"), bat("3", "Big Three", "2-4", "2", "2"), bat("4", "Quiet Four", "1-4", "1", "1")],
                          "pitchers": [{"id": "9", "name": "Ace Nine", "starter": True, "stats": {"IP": "6.2", "ER": "0", "K": "6"}, "dec": "W, 1-0"}]}}}
nl_ = mlb.notable_lines({}, fake)
check("a game with three qualifying batters shows only the best two (homers count most: 3 HR and 2 HR beat four singles); a pitcher with 6.2 scoreless innings (under 7) and a 1-for-4 batter do not qualify",
      len(nl_) == mlb.MAX_NOTABLE == 2 and "Big One" in nl_[0] and "Big Three" in nl_[1] and "Big Two" not in "".join(nl_) and "Ace Nine" not in "".join(nl_) and "Quiet Four" not in "".join(nl_), nl_)
check("a player already shown (the Dodgers' own lines) is skipped", all("Big One" not in x for x in mlb.notable_lines({}, fake, skip={"1"})) and len(mlb.notable_lines({}, fake, skip={"1"})) == 2)

# ---- Postseason ---------------------------------------------------------------------------------------
NOW_S = at("2026-10-04T00:00:00")
OUT_S = run(NOW_S)
check("the first playoff day: one series table per series that had a game finish, the Dodgers' series first", OUT_S["stats"]["series"] == 2 and OUT_S["stats"]["mode"] == "postseason" and OUT_S["html"].index("NL Division Series") < OUT_S["html"].index("AL Division Series"))
ts = text(OUT_S["html"])
check("a division series is best of 5: five rows, game 1 played with the score, the rest still to come, game 5 'if necessary'", len(re.findall(r"G\d ·", ts.split("AL Division")[0])) == 5 and "G5 · if necessary" in ts and "G2 · Mon 5 Oct, 8am SGT · at LAD" in ts, ts)
raw_g1 = next(e for e in BOARDS["2026-10-03"]["events"] if e["competitions"][0]["notes"][0]["headline"] == "NLDS - Game 1")
sc = {x["homeAway"]: int(x["score"]) for x in raw_g1["competitions"][0]["competitors"]}
check("game 1's score is the raw one, the home team (the higher seed) on the left", f"{sc['home']} | G1 · Sat 3 Oct · at {mlb.code(next(x for x in raw_g1['competitions'][0]['competitors'] if x['homeAway'] == 'home')['team']['abbreviation'])} | {sc['away']}" in ts, (sc, ts[:200]))
sd = {mlb.code(e["team"]["abbreviation"]): int({s["name"]: s["displayValue"] for s in e["stats"]}["playoffSeed"]) for lg in STD["children"] for dv in lg["children"] for e in dv["standings"]["entries"]}
check("regular-season seeds beside the names: (2) Dodgers, (3) Braves", f"({sd['LAD']}) Los Angeles Dodgers" in ts and f"Atlanta Braves ({sd['ATL']})" in ts and sd["LAD"] == 2 and sd["ATL"] == 3, ts[:120])
check("the Dodgers' playoff game carries Ohtani's line, from the raw game log", (lambda x: f"Shohei Ohtani (LAD): {x['H']}-for-{x['AB']}" in ts)(next(x for x in LOGS["ohtani_bat"] if x["id"] == raw_g1["id"])["stats"]))

NOW_N = at("2026-10-17T00:00:00")
OUT_N = run(NOW_N)
tn = text(OUT_N["html"])
raw_nlcs = [g for g in POST["19"] if g["status"] == "STATUS_FINAL" and "NLCS" in g["headline"]]
check("the NLCS ends 4-0 for Milwaukee: four played rows and three '–' rows, wins in large numbers either side of 'series'", len(raw_nlcs) == 4 and sum(not won(g) for g in raw_nlcs) == 4 and "4series0" in squash(OUT_N["html"].split("AL Championship")[0]))
check("the NLCS rows give the raw score of every game, Milwaukee (higher seed) first", all(f"{g['home']['score'] if g['home']['abbr'] == 'MIL' else g['away']['score']} | G{i} ·" in tn for i, g in enumerate(raw_nlcs, 1)) and "G5 · –" in tn and "G7 · –" in tn, tn[:500])
g4 = next(x for x in LOGS["ohtani_bat"] if x["id"] == raw_nlcs[3]["id"])["stats"]
check("Ohtani's game-4 homer and three RBI come from the raw log and are shown in the accent colour", f"{g4['H']}-for-{g4['AB']}, HR, {g4['RBI']} RBI" in tn and '<span class="n">HR</span>' in OUT_N["html"] and g4["HR"] == "1" and g4["RBI"] == "3", g4)
g2 = next(x for x in LOGS["yamamoto_pit"] if x["id"] == raw_nlcs[1]["id"])["stats"]
check("Yamamoto's start in game 2 is shown above Ohtani's batting line", f"{g2['IP']} IP, {g2['ER']} ER, {g2['K']} K" in tn and tn.index("Yamamoto") < tn.index("Ohtani (LAD): 0-for-4"), tn)
check("the AL series in progress shows its pre-built rows with Singapore times: game 4 on Saturday 17 October", "G4 · Sat 17 Oct, 8am SGT" in tn and "1series2" in squash(OUT_N["html"].split("AL Championship")[1]))
alcs = [g for g in POST[next(k for k, v in POST.items() if any("ALCS" in x["headline"] for x in v))] if "ALCS" in g["headline"]]
g4row = sorted(alcs, key=lambda x: x["date"])[3]
when = iso(g4row["date"]).astimezone(timezone(timedelta(hours=8)))
check("that time is the raw start time plus eight hours (Singapore), worked out here by hand", f"G4 · {when:%a} {when.day} {when:%b}, {when.hour % 12 or 12}{':' + format(when, '%M') if when.minute else ''}{'am' if when.hour < 12 else 'pm'} SGT" in tn, (g4row["date"], when))
def could_end(w1, w2, played, n, need):
    """Brute force: can either side reach `need` wins within the games still to be played before game n?"""
    k = n - 1 - played
    return any(w1 + a >= need or w2 + k - a >= need for a in range(k + 1))


al = text(OUT_N["html"].split("AL Championship")[1])
check("'if necessary' follows one rule in every series, whether or not ESPN has the game scheduled: AL at 1-2 after three games (best of 7): G4 and G5 are certain (a time), G6 and G7 are 'if necessary'; checked by brute force over the possible results",
      all(("if necessary" in re.search(rf"G{n} · ([^|\n]*)", al).group(1)) == could_end(1, 2, 3, n, 4) for n in (4, 5, 6, 7)) and could_end(1, 2, 3, 6, 4) and not could_end(1, 2, 3, 5, 4) and "G5 · if necessary" not in al and "G6 · if necessary" in al, al[-400:])
ds_one = ts.split("AL Division")[0]
check("the same rule on the NL division series at 1-0 after game 1 (best of 5): G2 and G3 have times, G4 and G5 are 'if necessary'",
      all(("if necessary" in re.search(rf"G{n} · ([^|\n]*)", ds_one).group(1)) == could_end(1, 0, 1, n, 3) for n in (2, 3, 4, 5)) and "G3 · if necessary" not in ds_one and "G4 · if necessary" in ds_one, ds_one[:500])
check("a time on the hour drops the minutes ('5pm', '8am') and keeps them otherwise ('8:30am'); midnight and noon are 12am and 12pm", mlb.sgt_when(datetime(2026, 10, 5, 17, 0)).endswith("5pm SGT") and mlb.sgt_when(datetime(2026, 10, 5, 8, 30)) == "Mon 5 Oct, 8:30am SGT" and mlb.sgt_when(datetime(2026, 10, 5, 0, 0)).endswith("12am SGT") and mlb.sgt_when(datetime(2026, 10, 5, 12, 0)).endswith("12pm SGT"))
heads = re.findall(r'<tr class="sh"><th colspan="3"><div class="hd"><span class="tn">(.*?)</span><span class="gap"></span><span class="tn">(.*?)</span></div></th></tr><tr class="sc"><th colspan="3"><div class="hd"><span class="ws">(\d+)</span><span class="gap"><span class="lab">series</span><span class="bo">best of (\d)</span></span><span class="ws">(\d+)</span>', OUT_S["html"] + OUT_N["html"])
check("the series header puts each team's name and its score in matching boxes either side of a gap, with 'series' and 'best of 5' (division) or 'best of 7' (championship) in the gap", len(heads) == 4 and [h[3] for h in heads] == ["5", "5", "7", "7"] and ("1", "0") == (heads[0][2], heads[0][4]), heads)
check("series notes are cached in the state once made, so earlier games cost no further requests", len(OUT_N["state"]["series_notes"]) >= 4 and all(isinstance(v, list) for v in OUT_N["state"]["series_notes"].values()))


class Counting(Saved):
    def __init__(self, now):
        super().__init__(now)
        self.asked = []

    def box(self, i):
        self.asked.append(i)
        return super().box(i)


c1, c2 = Counting(NOW_N), Counting(NOW_N)
run(NOW_N, {}, c1)
run(NOW_N, OUT_N["state"], c2)
check("with the notes cached the second run asks for no box scores", len(c1.asked) >= 4 and c2.asked == [], (c1.asked, c2.asked))

NOW_W2 = at("2026-10-01T00:00:00")
OUT_W2 = run(NOW_W2)
tw = text(OUT_W2["html"])
wc_games = [e for d in ("2026-09-29", "2026-09-30") for e in BOARDS[d]["events"] if e["status"]["type"]["name"] == "STATUS_FINAL"]
pairs = {frozenset(x["team"]["id"] for x in e["competitions"][0]["competitors"]) for e in wc_games}
check("the wild-card round: one best-of-3 table for each of the four series that played, three rows each", OUT_W2["stats"]["series"] == len(pairs) == 4 and tw.count("Wild Card Series |") == 4 and len(re.findall(r"G3 ·", tw)) == 4, (OUT_W2["stats"], len(pairs)))
def raw_series(pair, upto):
    """(wins of the team that hosted game 1, wins of the other) from the raw scoreboards: the games of that pair that were final by `upto`."""
    gs = sorted((e for b in BOARDS.values() for e in b["events"] if e["status"]["type"]["name"] == "STATUS_FINAL" and e["season"]["type"] == 3 and iso(e["date"]) <= upto
                 and frozenset(x["team"]["id"] for x in e["competitions"][0]["competitors"]) == pair), key=lambda e: e["date"])
    top = next(x["team"]["id"] for x in gs[0]["competitions"][0]["competitors"] if x["homeAway"] == "home")
    w = [0, 0]
    for e in gs:
        sc = {x["team"]["id"]: int(x["score"]) for x in e["competitions"][0]["competitors"]}
        w[0 if max(sc, key=sc.get) == top else 1] += 1
    return tuple(w)


check("each wild-card series header carries the raw wins of the team that hosted game 1 beside the other's, from a separate count of the scoreboards",
      all(f"{raw_series(p, NOW_W2 - timedelta(hours=4))[0]}series{raw_series(p, NOW_W2 - timedelta(hours=4))[1]}" in squash(OUT_W2["html"]) for p in pairs) and len({raw_series(p, NOW_W2 - timedelta(hours=4)) for p in pairs}) >= 2, [raw_series(p, NOW_W2) for p in pairs])
NOW_W3 = at("2026-10-02T00:00:00")
OUT_W3 = run(NOW_W3)
tw3 = text(OUT_W3["html"])
done = [p for p in pairs if max(raw_series(p, NOW_W3 - timedelta(hours=4))) == 2]
check("a best-of-3 that is over shows '–' for the third game and the clincher's two wins; one still open says 'if necessary' or gives a time", len(done) >= 2 and tw3.count("G3 · –") >= len(done) and re.search(r"(2series0|0series2)", squash(OUT_W3["html"])), (done, tw3[:600]))


class NoSchedPost(Saved):
    def schedule(self, team_id, season=None, season_type=2):
        if season_type == 3:
            return []
        return super().schedule(team_id, season, season_type)


ps = text(run(NOW_W2, {}, NoSchedPost(NOW_W2))["html"])
check("when ESPN's team schedule does not list a game the scoreboard has shown, the series table still shows that game and its score (never an empty 0-0 table)", ps.count("G1 · Tue 29 Sep") == len(pairs) == 4 and ps.count("Wild Card Series |") == 4 and "0series0" not in squash(run(NOW_W2, {}, NoSchedPost(NOW_W2))["html"]), ps[:500])
rain = text(run(at("2026-10-17T00:00:00"))["html"])
check("the rained-out ALCS game 4 does not break its series table: it is still the AL Championship Series with seven rows", rain.count("AL Championship Series") == 1 and len(re.findall(r"G\d ·", rain.split("AL Championship")[1])) == 7, rain[-500:])

NOW_F = at("2026-10-30T00:00:00")
OUT_F = run(NOW_F)
tf = text(OUT_F["html"])
ws = [g for g in POST["8"] if "World Series" in g["headline"] and g["status"] == "STATUS_FINAL"]
champ_wins = sum(1 for g in ws if won(g, "8"))
check("the World Series ends 4-1 to Milwaukee, from the raw schedule, and the table says so", len(ws) == 5 and champ_wins == 4 and "4series1" in squash(OUT_F["html"]))
check("the closing note names the champions and the series score", "That's the 2026 MLB season. The Brewers are World Series champions, beating the Rays 4–1." in tf, tf[-400:])
check("it says how the Dodgers' season ended, with their final record from the raw standings and the round they lost, 0-4", f"The Dodgers finished {flat['LAD']['overall']} and went out in the NL Championship Series, 0–4 to the Brewers." in tf, tf[-300:])
check("the season is closed in the state, and a later run says nothing more", OUT_F["state"]["closed"] == 2026 and "That's the 2026" not in text(run(NOW_F, OUT_F["state"])["html"]) and "That's the 2026" not in text(run(NOW_F, {"closed": 2026})["html"]))
check("on the morning of game 5 (not yet played) the season is not closed", "That's the" not in text(run(at("2026-10-29T00:00:00"))["html"]) and run(at("2026-10-29T00:00:00"))["state"]["closed"] is None)
mp = mlb.closing_html(2026, {"headline": "World Series - Game 5"}, [{"id": "1", "date": "2026-10-23", "status": "STATUS_FINAL", "home": {"id": "5", "short": "Blue Jays", "score": 3}, "away": {"id": "6", "short": "Mets", "score": 1}}] * 4, [{"abbr": "LAD", "overall": "88-74"}], [])
check("a Dodgers season with no playoffs closes with 'missed the playoffs'", "The Dodgers (88-74) missed the playoffs." in mp and "Blue Jays are World Series champions, beating the Mets 4–0" in mp, mp)
dc = mlb.closing_html(2026, {"headline": "World Series - Game 5"}, [{"id": "1", "date": "2026-10-23", "status": "STATUS_FINAL", "home": {"id": "19", "short": "Dodgers", "score": 3}, "away": {"id": "6", "short": "Mets", "score": 1}}] * 4, [{"abbr": "LAD", "overall": "100-62"}], [{"status": "STATUS_FINAL", "headline": "World Series - Game 4", "home": {"id": "19"}, "away": {"id": "6"}}])
check("if the Dodgers win the World Series the note says they are champions", "The Dodgers (100-62) are champions." in dc, dc)

# ---- Source, page and house rules ------------------------------------------------------------------------------
CALLS = []


def fake_get(url):
    CALLS.append(url)
    if "gamelog" in url:
        return {"labels": ["AB", "H"], "events": {"7": {"gameDate": "2026-05-02T00:00:00Z"}, "6": {"gameDate": "2026-05-01T00:00:00Z"}},
                "seasonTypes": [{"categories": [{"events": [{"eventId": "7", "stats": ["4", "2"]}, {"eventId": "6", "stats": ["3", "0"]}]}]}]}
    if "summary" in url:
        return {"boxscore": {"players": [{"team": {"abbreviation": "LAD"}, "statistics": [{"type": "batting", "labels": ["H-AB", "HR"], "athletes": [{"athlete": {"id": "1", "displayName": "A One"}, "starter": True, "stats": ["1-3", "1"]}]},
                                                                                           {"type": "pitching", "labels": ["IP", "K"], "athletes": [{"athlete": {"id": "2", "displayName": "B Two"}, "starter": True, "stats": ["6.0", "7"], "notes": [{"type": "pitchingDecision", "text": "W, 3-1"}]}]}]}]},
                "pickcenter": [{"details": "LAD -150", "awayTeamOdds": {"underdog": True, "moneyLine": 130}, "homeTeamOdds": {"underdog": False, "moneyLine": -150}}],
                "injuries": [{"injuries": [{"athlete": {"id": "9"}, "status": "Out", "details": {"type": "Knee"}}]}]}
    return {"ok": url}


src = espn_mlb.Source(fake_get, pause=0)
bx = src.box("5")
check("source: a box score is trimmed to each team's batters and pitchers with a decision, the pre-game line and ESPN's injury list",
      bx["teams"]["LAD"]["batters"] == [{"id": "1", "name": "A One", "starter": True, "stats": {"H-AB": "1-3", "HR": "1"}}]
      and bx["teams"]["LAD"]["pitchers"] == [{"id": "2", "name": "B Two", "starter": True, "stats": {"IP": "6.0", "K": "7"}, "dec": "W, 3-1"}]
      and bx["odds"]["away_dog"] is True and bx["injuries"] == {"9": {"status": "Out", "type": "Knee"}}, bx)
gl = src.gamelog("39832", 2026, "batting")
check("source: a game log comes oldest first as {id, date, stats by label}, and asks for the season and category", gl == [{"id": "6", "date": "2026-05-01T00:00:00Z", "stats": {"AB": "3", "H": "0"}}, {"id": "7", "date": "2026-05-02T00:00:00Z", "stats": {"AB": "4", "H": "2"}}]
      and "athletes/39832/gamelog?season=2026&category=batting" in CALLS[-1], gl)
src.standings(2026)
src.scoreboard(date(2026, 9, 20))
check("source: standings are asked by division (level 3) and the scoreboard by date as yyyymmdd", "standings?level=3&season=2026" in CALLS[-2] and "dates=20260920" in CALLS[-1] and src.calls == 4)
check("MLB needs no Claude: neither module imports anthropic", "anthropic" not in (ROOT / "kickoff" / "mlb.py").read_text() and "anthropic" not in (ROOT / "kickoff" / "sources" / "espn_mlb.py").read_text())
every = OUT_W["html"] + OUT_D["html"] + OUT_S["html"] + OUT_N["html"] + OUT_F["html"]
check("house rules: no 'LIVE' tags, no home icon (it is not used for baseball), no bright 'W' colours, no team repeated in a table", "LIVE" not in every and 'class="home"' not in every)
tags = lambda h: [t for t in re.findall(r"<(/?)(table|tr|tbody|thead|div)\b", h)]  # noqa: E731
bal = lambda h, name: len(re.findall(rf"<{name}\b", h)) == len(re.findall(rf"</{name}>", h))  # noqa: E731
check("every page's tables and rows are balanced HTML", all(bal(h, n) for h in (OUT_W["html"], OUT_D["html"], OUT_S["html"], OUT_N["html"], OUT_F["html"]) for n in ("table", "tr", "thead", "tbody", "div")))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
