"""Offline tests for the awards table, on saved real ESPN data (NBA 2026, NFL 2025, MLB 2026 so far). Run: python3 scripts/test_awards.py"""
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import awards  # noqa: E402
from kickoff.sources import espn_awards  # noqa: E402

FX = ROOT / "tests" / "fixtures"
REC = json.loads((FX / "espn_awards.json").read_text())
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


def replay(hide=(), counter=None):
    """get_json over the recorded responses; the awards in `hide` come back with no winners yet (not announced)."""
    def get(url):
        if counter is not None:
            counter.append(url)
        j = copy.deepcopy(REC[url])
        m = re.search(r"/awards/(\d+)$", url.split("?")[0])
        if m and m.group(1) in hide:
            j["winners"] = []
        return j
    return get


def src(sport, league, **kw):
    return espn_awards.Source(sport, league, get_json=replay(**kw), pause=0)


text = lambda h: re.sub(r"<[^>]+>", " ", h)  # noqa: E731

# ---- labels ----
check("labels use D's short forms (ROTY, 6MAN, MIP, EC/WC MVP, FINALS MVP, DPOY, TMOTY, OPOY, WP MOTY, COTY, SB MVP, RC Award) and full names for the Gold Glove, Silver Slugger and Platinum Glove awardees and otherwise ESPN's name without the league",
      [awards.label(n) for n in ("Rookie of the Year", "Sixth Man of the Year", "Most Improved Player", "NBA Eastern Conference Finals MVP", "NBA Western Conference Finals MVP", "Finals MVP", "Defensive Player of the Year", "Twyman-Stokes Teammate of the Year Award", "NFL MVP", "NFL Offensive Player of the Year", "NFL Defensive Rookie of the Year", "Walter Payton NFL Man of the Year", "NFL Coach of the Year", "Super Bowl MVP", "Gold Glove", "Silver Slugger", "Roberto Clemente Award", "All-NBA 1st Team", "NBA Cup MVP")]
      == ["ROTY", "6MAN", "MIP", "EC MVP", "WC MVP", "FINALS MVP", "DPOY", "TMOTY", "MVP", "OPOY", "DROY", "WP MOTY", "COTY", "SB MVP", "Golden Glove Awardees", "Silver Slugger Awardees", "RC Award", "All-NBA 1st Team", "Cup MVP"])
check("winner text: one winner with his team, a team of players as a plain list", awards.winner_text(["A B"], "OKC") == "A B (OKC)" and awards.winner_text(["A. B", "C. D"]) == "A. B, C. D")

# ---- the engine ----
it = lambda k, sig, t="x": {"key": k, "label": f"Award {k}", "sig": sig, "text": t}  # noqa: E731
s0, new = awards.update({}, 2026, [it("1", "a"), it("2", "b")])
check("first sight of a sport: existing awards are remembered silently, nothing is news", new == [] and s0["rows"] == [] and set(s0["seen"]) == {"1", "2"})
s1, new = awards.update(s0, 2026, [it("1", "a"), it("2", "b"), it("3", "c", "C")])
check("day 1: the one new award is news and is the only row", [x["key"] for x in new] == ["3"] and [x["key"] for x in s1["rows"]] == ["3"])
s2, new = awards.update(s1, 2026, [it("1", "a"), it("2", "b"), it("3", "c", "C"), it("4", "d", "D")])
check("day 2: the table is cumulative with the newest on top (4 over 3)", [x["key"] for x in new] == ["4"] and [x["key"] for x in s2["rows"]] == ["4", "3"])
s3, new = awards.update(s2, 2026, [it("1", "a"), it("5", "e", "E"), it("6", "f", "F"), it("2", "b"), it("3", "c", "C"), it("4", "d", "D")])
check("two on one day keep ESPN's order, both above the older ones", [x["key"] for x in s3["rows"]] == ["5", "6", "4", "3"], [x["key"] for x in s3["rows"]])
s4, new = awards.update(s3, 2026, [it("5", "e", "E"), it("6", "f", "F"), it("4", "d", "D"), it("3", "c", "C")])
check("nothing new: no news, state unchanged", new == [] and s4 == s3)
s5, new = awards.update(s3, 2026, [it("4", "d2", "D2")])
check("a changed winner list is news again: the row moves to the top with a note", [x["key"] for x in new] == ["4"] and s5["rows"][0]["key"] == "4" and s5["rows"][0]["note"] and [x["key"] for x in s5["rows"]].count("4") == 1, s5["rows"])
s6, new = awards.update(s3, 2027, [it("9", "z", "Z")])
check("a higher season starts afresh: only its own awards, all news", [x["key"] for x in s6["rows"]] == ["9"] and s6["season"] == 2027)
check("ESPN going back a season changes nothing", awards.update(s3, 2025, [it("9", "z")]) == (s3, []))

# ---- the NBA, on the real 2026 awards ----
nba_all = [REC[u] for u in REC if re.search(r"/nba/seasons/2026/awards/\d+$", u.split("?")[0])]
ids = {a["id"]: a["name"] for a in nba_all}
by_name = {a["name"]: a["id"] for a in nba_all}
check("the real list has the conference finals MVPs, the Teammate of the Year award and the Cup awards", {"NBA Eastern Conference Finals MVP", "NBA Western Conference Finals MVP", "Twyman-Stokes Teammate of the Year Award", "NBA Cup MVP"} <= set(ids.values()))
hide_all_but_base = {i for i in ids if i not in (by_name["MVP"], by_name["Rookie of the Year"])}
st = {}
html, st = awards.run(src("basketball", "nba", hide=hide_all_but_base), "NBA Awards", st, 2026)
check("first run: the awards that exist are remembered, nothing is shown", html == "" and set(st["seen"]) == {by_name["MVP"], by_name["Rookie of the Year"]} and st["season"] == 2026, st)
hide2 = hide_all_but_base - {by_name["Sixth Man of the Year"], by_name["All-NBA 1st Team"], by_name["NBA Western Conference Finals MVP"], by_name["NBA Cup MVP"]}
calls = []
html, st = awards.run(espn_awards.Source("basketball", "nba", get_json=replay(hide=hide2, counter=calls), pause=0), "NBA Awards", st, 2026)
t = text(html)
check("day 1: three awards announced (6MAN, All-NBA first team, WC MVP); the Cup MVP is skipped; the table says NBA Awards", "NBA Awards" in t and "6MAN" in t and "All-NBA 1st Team" in t and "WC MVP" in t and "Cup" not in t and "Most Valuable Player" not in t, t)
raw_p = REC[next(u for u in REC if f"/awards/{by_name['Sixth Man of the Year']}" in u)]["winners"][0]["athlete"]["$ref"]
raw_name = REC[raw_p.replace("http://", "https://").split("?")[0]]["displayName"]
tn = re.sub(r"\s+", " ", t)
check("independent: the Sixth Man's name is the one in the raw athlete record, with his team code beside it", f"{raw_name} (" in tn and raw_name, (raw_name, tn[:300]))
a1 = REC[next(u for u in REC if f"/awards/{by_name['All-NBA 1st Team']}" in u)]["winners"]
raw_names = [REC[w["athlete"]["$ref"].replace("http://", "https://").split("?")[0]]["displayName"] for w in a1]
raw_teams = [REC[w["team"]["$ref"].replace("http://", "https://").split("?")[0]]["abbreviation"] for w in a1]
check("the All-NBA first team is five lines in ESPN's order, each the full raw name with that season's team: 'Nikola Jokic — DEN' (the count is left out when ESPN's history cannot be read)",
      all(f"{n} — {tm}" in tn for n, tm in zip(raw_names, raw_teams)) and tn.index(raw_names[0]) < tn.index(raw_names[4]) and len(raw_names) == 5, (raw_names, raw_teams))
check("day 1 order: the table starts with the awards announced today and not with the older ones (MVP is not shown: it was announced before)", "Most Valuable" not in t and re.sub(r"\s+", " ", t).count("ROTY") == 0, t)
need = [u for u in calls if "/athletes/" in u or "/teams/" in u]
check("only new awards cost name lookups, and no team or athlete is asked for twice: 6 different athletes (Wembanyama won two awards), each team once", len(need) == len(set(need)) and len([u for u in need if "/athletes/" in u]) == 6, (len(need), len(set(need)), [u[-45:] for u in need]))
html2, st2 = awards.run(src("basketball", "nba", hide=hide2), "NBA Awards", st, 2026)
check("run again with nothing new: no table", html2 == "" and st2 == st)
hide3 = hide2 - {by_name["Defensive Player of the Year"]}
html3, st3 = awards.run(src("basketball", "nba", hide=hide3), "NBA Awards", st2, 2026)
t3 = re.sub(r"\s+", " ", text(html3))
check("day 2: Defensive Player on top, the one-winner awards from day 1 still below it; the All-NBA team block is not repeated on a day it is not new", t3.index("DPOY") < t3.index("6MAN") and "WC MVP" in t3 and "All-NBA 1st Team" not in t3, t3[:500])
html_bad, st_bad = awards.run(espn_awards.Source("basketball", "nba", get_json=lambda u: 1 / 0, pause=0), "NBA Awards", st3, 2026)
check("a failing source shows nothing and keeps the state", html_bad == "" and st_bad == st3)

# ---- the NFL: the offseason, and a season that has not been announced yet ----
nfl_src = src("football", "nfl")
got = nfl_src.awards(2025)
check("NFL: the 2025 season's nine awards include the Walter Payton Man of the Year", len(got) == 9 and any(a["name"] == "Walter Payton NFL Man of the Year" for a in got), len(got))
check("NFL in November 2026: ESPN lists no awards for the 2026 season yet", nfl_src.awards(2026) == [])
nh, nst = awards.run(nfl_src, "NFL Awards", {}, 2026)
check("first run in the offseason for the 2026 season: nothing to show, nothing remembered", nh == "" and nst.get("rows") == [] and nst["season"] == 2026 and nst["seen"] == {})
nh2, nst2 = awards.run(nfl_src, "NFL Awards", {}, 2025)
check("first run on a season that has its awards: remembered silently", nh2 == "" and len(nst2["seen"]) == 9)

# ---- the MLB: announced piece by piece right now ----
mlb_src = src("baseball", "mlb")
got = mlb_src.awards(2026)
check("MLB: the 2026 awards announced so far include the Gold Glove (20 winners) and the Roberto Clemente Award", any(a["name"] == "Gold Glove" and len(a["winners"]) == 20 for a in got) and any(a["name"] == "Roberto Clemente Award" for a in got), [a["name"] for a in got])

# ---- D's presentation round (2026-11-04): gold winners, iridescent MVPs, medal tones, blocks, abbreviations ----
check("every MVP is iridescent, whatever its name; other winners are plain gold", [awards.is_mvp(x) for x in ("MVP", "Finals MVP", "Western Conference Finals MVP", "All-Star MVP", "Super Bowl MVP", "Rookie of the Year", "Most Valuable Player")] == [True, True, True, True, True, False, True])
check("medal tones: 1st gold, 2nd silver, 3rd bronze (All-NBA, All-Defensive, All-Rookie alike); anything else gold", [awards.tone_of(x) for x in ("All-NBA 1st Team", "All-NBA 2nd Team", "All-NBA 3rd Team", "All-Defensive 2nd Team", "Coach of the Year")] == ["gold", "silver", "bronze", "silver", "gold"])
rows1 = [{"key": "1", "label": "MVP", "kind": "single", "data": {"name": "Shai Gilgeous-Alexander", "team": "OKC"}, "text": "", "note": ""},
         {"key": "2", "label": "Rookie of the Year", "kind": "single", "data": {"name": "Cooper Flagg", "team": "DAL"}, "text": "", "note": ""},
         {"key": "3", "label": "Defensive Player of the Year", "kind": "single", "data": {"name": "Victor Wembanyama", "team": "SA"}, "text": "", "note": ""}]
th = awards.table_html("NBA Awards", rows1)
check("the MVP winner carries the iridescent class and the others plain gold; the team code sits beside each name", '<span class="wn mvp">Shai Gilgeous-Alexander</span> <span class="tc">(OKC)</span>' in th and '<span class="wn">Cooper Flagg</span>' in th and th.count("wn mvp") == 1, th)
check("the winners' column is the wide one (31% labels / 69% winners, D's phone check) now that labels are short forms", '<col style="width:31%"><col style="width:69%">' in th)
team_row = {"key": "t", "label": "All-NBA 2nd Team", "kind": "team", "data": {"tone": "silver", "players": [{"name": "Kevin Durant", "team": "HOU", "count": 15}, {"name": "Kawhi Leonard", "team": "LAC", "count": None}]}, "text": "", "note": ""}
tb = awards.table_html("NBA Awards", [team_row])
check("a team row is a full-width block with one line per player: the name in the tone colour, the count in brackets only when known, then '— TEAM'", 'colspan="2"' in tb and '<span class="wn silver">Kevin Durant</span> <span class="ct">(15)</span> <span class="tc">— HOU</span>' in tb and '<span class="wn silver">Kawhi Leonard</span> <span class="tc">— LAC</span>' in tb and tb.count('class="pl"') == 2, tb)
check("blocks are left out unless asked for (a day they are not new)", awards.table_html("NBA Awards", rows1 + [team_row], show_blocks=False).count("Kevin Durant") == 0 and awards.table_html("NBA Awards", rows1 + [team_row]).count("Kevin Durant") == 1)
check("abbreviations: initial and surname, hyphenated first names as 'K-A.', two players who would clash keep their full names",
      awards.abbreviate(["Victor Wembanyama", "Karl-Anthony Towns", "Jalen Johnson", "Jaylen Johnson", "Luka Dončić"]) == {"Victor Wembanyama": "V. Wembanyama", "Karl-Anthony Towns": "K-A. Towns", "Jalen Johnson": "Jalen Johnson", "Jaylen Johnson": "Jaylen Johnson", "Luka Dončić": "L. Dončić"})
check("numbered positions: a repeat is numbered, a single position is not, APU reads Utility", awards.numbered([("QB", "A"), ("WR", "B"), ("WR", "C"), ("APU", "D")]) == [("QB", "A"), ("WR 1", "B"), ("WR 2", "C"), ("Utility", "D")])
asg = awards.wiki_items("nba", 2026, type("W", (), {"wikitext": lambda self, page: (FX / "wiki_nba_asg_2026.txt").read_text() if "All-Star" in page else ""})())
east = next(i for i in asg if i["key"] == "wiki:asg:East")
ah = awards.table_html("NBA Awards", [{**east, "note": ""}])
check("an All-Star block has Starters and Reserves columns, one player a line, abbreviated, with (Out) after the injured Giannis and (In) after the replacement Ingram",
      "Starters" in ah and "Reserves" in ah and "G. Antetokounmpo <span class=\"fl\">(Out)</span>" in ah and "B. Ingram <span class=\"fl\">(In)</span>" in ah and ah.count('class="pl"') == 13 and "K-A. Towns" in ah, ah[:700])
ap_item = awards.wiki_items("nfl", 2025, type("W", (), {"wikitext": lambda self, page: (FX / "wiki_all_pro_2025.txt").read_text() if "All-Pro" in page else ""})())
ap_h = awards.table_html("NFL Awards", [{**next(i for i in ap_item if i["key"] == "wiki:ap:first:Offense"), "note": ""}])
check("an All-Pro block is a Position / Player table: one row each, 'WR 1' to 'WR 3', 'Utility', full names in gold", ap_h.count("<tr><td class=\"pp\">") == 13 and "<td class=\"pp\">Utility</td><td><span class=\"wn\">Christian McCaffrey</span> <span class=\"tc\">(SF)</span>" in ap_h and "(LAR)" in ap_h and "WR 3" in ap_h, ap_h[:500])

# the blocks are shown on the day they land and on the final awards day (the MVP), not between
hide4 = {i for i in ids if i not in (by_name["Sixth Man of the Year"],)}
_, sx = awards.run(src("basketball", "nba", hide=hide4), "NBA Awards", {}, 2026)
h_a, sx = awards.run(src("basketball", "nba", hide=hide4 - {by_name["All-NBA 1st Team"]}), "NBA Awards", sx, 2026)
check("the morning the All-NBA team lands: its block is in the table", "All-NBA 1st Team" in text(h_a))
h_b, sx = awards.run(src("basketball", "nba", hide=hide4 - {by_name["All-NBA 1st Team"], by_name["Rookie of the Year"]}), "NBA Awards", sx, 2026)
check("a later morning (Rookie of the Year lands): the one-winner rows are listed, the All-NBA block is not repeated", "ROTY" in text(h_b) and "All-NBA 1st Team" not in text(h_b) and "6MAN" not in text(h_b))
h_c, sx = awards.run(src("basketball", "nba", hide=hide4 - {by_name["All-NBA 1st Team"], by_name["Rookie of the Year"], by_name["MVP"]}), "NBA Awards", sx, 2026)
check("the MVP morning is the final awards day: the full list returns, the All-NBA block included", "All-NBA 1st Team" in text(h_c) and "MVP" in text(h_c) and "wn mvp" in h_c)

# ---- All-NBA selection counts: ESPN's lists back to 1947, checked against Wikipedia's independent 'most selections' table ----
HIST = json.loads((FX / "espn_allnba_history.json").read_text())


class HistSource:
    """winners(season, award id) from the saved lists; a season in `broken` raises."""
    def __init__(self, broken=()):
        self.asked, self.broken = [], set(broken)

    def winners(self, season, award_id):
        self.asked.append(season)
        if season in self.broken:
            raise RuntimeError("down")
        return HIST.get(str(season), {}).get(award_id) or []


hs = HistSource()
counts, cache = awards.allnba_counts(hs, 2026, {})
WIKI = (FX / "wiki_all_nba_team.txt").read_text()
KNOWN = {"1966": ("LeBron", "James"), "215": ("Tim", "Duncan"), "110": ("Kobe", "Bryant"), "4145": ("Kareem", "Abdul-Jabbar"), "614": ("Shaquille", "O'Neal"), "501": ("Karl", "Malone"), "3202": ("Kevin", "Durant")}
raw_total = lambda f, l: int(re.search(r"sortname\|%s\|%s\}\}[^\n]*\n[^\d\n]*(\d+)" % (re.escape(f), re.escape(l)), WIKI).group(1))  # noqa: E731
check("independent: ESPN's history reproduces Wikipedia's career All-NBA totals for LeBron, Duncan, Kobe, Kareem, Shaq, Malone and Durant", all(counts[i] == raw_total(*n) for i, n in KNOWN.items()), {n[1]: (counts.get(i), raw_total(*n)) for i, n in KNOWN.items()})
check("the count includes the current season (Durant's 2026 second-team selection is in his 12)", counts["3202"] == 12 and "3202" in HIST["2026"]["45"])
check("history covers the 80 seasons from 1947 and is cached for the next time", len(cache["seasons"]) == 80 and "1947" in cache["seasons"], len(cache["seasons"]))
hs2 = HistSource()
counts2, cache2 = awards.allnba_counts(hs2, 2026, cache)
check("with the history cached only the current season is asked for again (three lists)", hs2.asked == [2026, 2026, 2026] and counts2 == counts, hs2.asked)
bad_counts, bad_cache = awards.allnba_counts(HistSource(broken={1990}), 2026, {})
check("a season that cannot be read means no counts at all (never a count that is too low), and the cache is untouched", bad_counts is None and bad_cache == {})

class SrcWithHistory(espn_awards.Source):
    def winners(self, season, award_id):
        return HIST.get(str(season), {}).get(award_id) or []


hide5 = {i for i in ids if i != by_name["Sixth Man of the Year"]}
_, sh = awards.run(src("basketball", "nba", hide=hide5), "NBA Awards", {}, 2026)
sh_src = SrcWithHistory("basketball", "nba", get_json=replay(hide=hide5 - {by_name["All-NBA 1st Team"]}), pause=0)
h_cnt, sh = awards.run(sh_src, "NBA Awards", sh, 2026)
jokic_seasons = sum(1 for y, d in HIST.items() if int(y) <= 2026 and "3112335" in {i for w in d.values() for i in w})
jokic_line = re.search(r"Nikola Jokic</span> <span class=\"ct\">\((\d+)\)</span> <span class=\"tc\">— DEN", h_cnt)
check("end to end: the All-NBA first team shows each player's career count in brackets (Jokic's matches a count made straight from the raw lists)", jokic_line and int(jokic_line.group(1)) == jokic_seasons and jokic_seasons >= 8, (jokic_line and jokic_line.group(0), jokic_seasons))
check("the history is kept in the state so tomorrow does not fetch it again", len(sh["allnba"]["seasons"]) == 80)

# ---- MLB (round 2): the 2025 awards on real data: pairs for the two-league awards, league blocks for the Gold Glove and Silver Slugger ----
mlb_all = [REC[u] for u in REC if re.search(r"/mlb/seasons/2025/awards/\d+$", u.split("?")[0])]
mby = {a["name"]: a["id"] for a in mlb_all}
raw_team = lambda w: REC[w["team"]["$ref"].replace("http://", "https://").split("?")[0]]["abbreviation"]  # noqa: E731
raw_ath = lambda w: REC[w["athlete"]["$ref"].replace("http://", "https://").split("?")[0]]["displayName"]  # noqa: E731
mhide = {i for n, i in mby.items() if n not in ("ROTY_PLACEHOLDER",)}
_, ms = awards.run(src("baseball", "mlb", hide=mhide), "MLB Awards", {}, 2025)
show = mhide - {mby["MVP"], mby["Cy Young"], mby["Gold Glove"], mby["World Series MVP"], mby["Roberto Clemente Award"]}
mh, ms = awards.run(src("baseball", "mlb", hide=show), "MLB Awards", ms, 2025)
mt = re.sub(r"\s+", " ", text(mh))
mvp_raw = next(a for a in mlb_all if a["name"] == "MVP")["winners"]
mvp_pairs = sorted((awards.MLB_LEAGUE[raw_team(w)], raw_ath(w), raw_team(w)) for w in mvp_raw)
check("MLB MVP is a pair, AL then NL, each winner with his club's code (checked against the raw winners and the league map)", all(f"{n} ({t})" in mt for _, n, t in mvp_pairs) and mt.index(mvp_pairs[0][1]) < mt.index(mvp_pairs[1][1]) and mvp_pairs[0][0] == "AL" and mvp_pairs[1][0] == "NL", (mvp_pairs, mt[:300]))
check("the pair rows use the short labels MVP, Cy Young, WS MVP and RC Award", all(x in mt for x in ("MVP", "Cy Young", "WS MVP", "RC Award")) and "Most Valuable" not in mt, mt[:200])
check("MVPs are iridescent (MVP and WS MVP), the Cy Young is plain gold", mh.count("wn mvp") >= 3, mh.count("wn mvp"))
gg_raw = next(a for a in mlb_all if a["name"] == "Gold Glove")["winners"]
gg_al = sorted(raw_ath(w) for w in gg_raw if awards.MLB_LEAGUE[raw_team(w)] == "AL")
gg_nl = sorted(raw_ath(w) for w in gg_raw if awards.MLB_LEAGUE[raw_team(w)] == "NL")
ms_rows = {r_["label"]: r_ for r_ in ms["rows"]}
gg_row = ms_rows["Golden Glove Awardees"]
check("the Gold Glove is a league block: the 20 winners split into AL and NL exactly as the raw teams say", gg_row["kind"] == "league" and sorted(p["name"] for p in gg_row["data"]["AL"]) == gg_al and sorted(p["name"] for p in gg_row["data"]["NL"]) == gg_nl and len(gg_al) + len(gg_nl) == 20, (len(gg_al), len(gg_nl)))
check("the Gold Glove block is shown on the morning it lands (a block), with 'American League' and 'National League' columns and each player's club", "American League" in mh and "National League" in mh and "Golden Glove Awardees" in mh and mh.count('class="pl"') == 20, mh.count('class="pl"'))
ms2_hide = show - {mby["Silver Slugger"]}
mh2, ms2 = awards.run(src("baseball", "mlb", hide=ms2_hide), "MLB Awards", ms, 2025)
check("a later morning (Silver Slugger lands): its block is in, the Gold Glove block is not repeated, the pair rows stay", "Silver Slugger Awardees" in text(mh2) and "Golden Glove Awardees" not in text(mh2) and "Cy Young" in text(mh2), ("Silver S" in text(mh2), "Golden G" in text(mh2), "Cy Young" in text(mh2), re.sub(r"\s+", " ", text(mh2))[-250:]))

# ---- the whole block for a morning, and the wrapper the daily run uses ----
import datetime as dt  # noqa: E402
from kickoff import daily  # noqa: E402


class NoWiki:
    def wikitext(self, page):
        return ""


hide_b = {i for i in ids if i not in (by_name["MVP"],)}
b_html, b_state = awards.block("nba", "basketball", "NBA Awards", dt.date(2026, 4, 20), {}, source=src("basketball", "nba", hide=hide_b), wiki=NoWiki())
check("block: the NBA on 20 April 2026 reads the 2026 season; first sight is silent", b_html == "" and b_state["season"] == 2026 and len(b_state["seen"]) == 1)
b_html2, b_state2 = awards.block("nba", "basketball", "NBA Awards", dt.date(2026, 4, 21), b_state, source=src("basketball", "nba", hide=hide_b - {by_name["Rookie of the Year"]}), wiki=NoWiki())
check("block: the next day's Rookie of the Year is the news", "ROTY" in text(b_html2) and "Most Valuable" not in text(b_html2) and b_state2["season"] == 2026, text(b_html2))

# the wrapper: the sport's own html comes after the awards table; the awards state is kept next to the sport's state
orig_block = awards.block
awards.block = lambda league, sport, title, day, state, **kw: orig_block(league, sport, title, day, state, source=src("basketball", "nba", hide=hide_b - {by_name["Rookie of the Year"]}), wiki=NoWiki())
fake_sport = lambda now, day, st: {"html": "<p>GAMES</p>", "state": {"reported": [1]}}
wrapped = daily._with_extras(fake_sport, "nba", "basketball", "NBA")
w_out = wrapped(None, dt.date(2026, 4, 21), {"awards": b_state})
check("the wrapper puts the awards table above the games and keeps both states", w_out["html"].index("NBA Awards") < w_out["html"].index("GAMES") and w_out["state"]["reported"] == [1] and w_out["state"]["awards"]["season"] == 2026 and "ROTY" in w_out["html"], w_out["html"][:200])
w_quiet = wrapped(None, dt.date(2026, 4, 21), {"awards": w_out["state"]["awards"]})
check("a day with nothing new: only the games, and the awards state unchanged", w_quiet["html"] == "<p>GAMES</p>" and w_quiet["state"]["awards"] == w_out["state"]["awards"])
awards.block = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
w_bad = wrapped(None, dt.date(2026, 4, 21), {"awards": b_state})
check("a failing awards block costs the sport nothing: its games still show and its awards state is kept as it was", w_bad["html"] == "<p>GAMES</p>" and w_bad["state"]["awards"] == b_state and w_bad["state"]["reported"] == [1], w_bad)
awards.block = orig_block

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
