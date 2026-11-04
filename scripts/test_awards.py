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
check("labels drop the league name and 'Award'", [awards.label(n) for n in ("NBA Western Conference Finals MVP", "NFL MVP", "Walter Payton NFL Man of the Year", "Twyman-Stokes Teammate of the Year Award", "Gold Glove", "All-NBA 1st Team")]
      == ["Western Conference Finals MVP", "MVP", "Walter Payton Man of the Year", "Teammate of the Year", "Gold Glove", "All-NBA 1st Team"])
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
check("day 1: three awards announced (Sixth Man, All-NBA first team, Western Conference Finals MVP); the Cup MVP is skipped; the table says NBA Awards", "NBA Awards" in t and "Sixth Man of the Year" in t and "All-NBA 1st Team" in t and "Western Conference Finals MVP" in t and "Cup" not in t and "Most Valuable Player" not in t, t)
raw_p = REC[next(u for u in REC if f"/awards/{by_name['Sixth Man of the Year']}" in u)]["winners"][0]["athlete"]["$ref"]
raw_name = REC[raw_p.replace("http://", "https://").split("?")[0]]["displayName"]
check("independent: the Sixth Man's name is the one in the raw athlete record, with his team code", f"{raw_name} (" in t and raw_name, (raw_name, t[:300]))
a1 = REC[next(u for u in REC if f"/awards/{by_name['All-NBA 1st Team']}" in u)]["winners"]
shorts = [REC[w["athlete"]["$ref"].replace("http://", "https://").split("?")[0]]["shortName"] for w in a1]
check("the All-NBA first team is the five raw short names, in ESPN's order", ", ".join(shorts) in re.sub(r"\s+", " ", t), (shorts, t[:400]))
check("day 1 order: the table starts with the awards announced today and not with the older ones (MVP is not shown: it was announced before)", "Most Valuable" not in t and re.sub(r"\s+", " ", t).count("Rookie of the Year") == 0, t)
need = [u for u in calls if "/athletes/" in u or "/teams/" in u]
check("only new awards cost name lookups: 3 awards = at most 5+1+1 athletes and 2 teams", len(need) <= 9, len(need))
html2, st2 = awards.run(src("basketball", "nba", hide=hide2), "NBA Awards", st, 2026)
check("run again with nothing new: no table", html2 == "" and st2 == st)
hide3 = hide2 - {by_name["Defensive Player of the Year"]}
html3, st3 = awards.run(src("basketball", "nba", hide=hide3), "NBA Awards", st2, 2026)
t3 = re.sub(r"\s+", " ", text(html3))
check("day 2: Defensive Player on top, the three from day 1 still below it", t3.index("Defensive Player") < t3.index("Sixth Man") and "All-NBA 1st Team" in t3 and "Western Conference Finals MVP" in t3, t3[:500])
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
check("block: the next day's Rookie of the Year is the news", "Rookie of the Year" in text(b_html2) and "Most Valuable" not in text(b_html2) and b_state2["season"] == 2026, text(b_html2))

# the wrapper: the sport's own html comes after the awards table; the awards state is kept next to the sport's state
orig_block = awards.block
awards.block = lambda league, sport, title, day, state, **kw: orig_block(league, sport, title, day, state, source=src("basketball", "nba", hide=hide_b - {by_name["Rookie of the Year"]}), wiki=NoWiki())
fake_sport = lambda now, day, st: {"html": "<p>GAMES</p>", "state": {"reported": [1]}}
wrapped = daily._with_extras(fake_sport, "nba", "basketball", "NBA")
w_out = wrapped(None, dt.date(2026, 4, 21), {"awards": b_state})
check("the wrapper puts the awards table above the games and keeps both states", w_out["html"].index("NBA Awards") < w_out["html"].index("GAMES") and w_out["state"]["reported"] == [1] and w_out["state"]["awards"]["season"] == 2026 and "Rookie of the Year" in w_out["html"], w_out["html"][:200])
w_quiet = wrapped(None, dt.date(2026, 4, 21), {"awards": w_out["state"]["awards"]})
check("a day with nothing new: only the games, and the awards state unchanged", w_quiet["html"] == "<p>GAMES</p>" and w_quiet["state"]["awards"] == w_out["state"]["awards"])
awards.block = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
w_bad = wrapped(None, dt.date(2026, 4, 21), {"awards": b_state})
check("a failing awards block costs the sport nothing: its games still show and its awards state is kept as it was", w_bad["html"] == "<p>GAMES</p>" and w_bad["state"]["awards"] == b_state and w_bad["state"]["reported"] == [1], w_bad)
awards.block = orig_block

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
