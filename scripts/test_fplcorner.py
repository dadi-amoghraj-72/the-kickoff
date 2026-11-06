"""Offline tests for the FPL corner. Run: .venv/bin/python scripts/test_fplcorner.py"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kickoff import fplcorner as fc  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


T = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731


def player(pid, name, web, team="ARS", status="a", news="", added=None, chance=None, owned=1.0):
    return {"id": pid, "name": name, "web_name": web, "team": team, "status": status, "news": news, "news_added": added,
            "chance_next": chance, "owned": owned}


PLAYERS = [player(1, "Erling Haaland", "Haaland", "MCI", owned=60), player(2, "Bukayo Saka", "Saka", status="i", news="Thigh injury - Unknown return date",
                                                                       added="2026-10-21T10:00:00Z", owned=30),
           player(3, "Matty Cash", "Cash", "AVL", status="s", news="Suspended until 21 Nov", added="2026-11-03T09:00:00Z", owned=20),
           player(4, "Doubtful Dan", "Dan", "LIV", status="d", news="Illness", added="2026-11-03T09:00:00Z", chance=50, owned=3),
           player(5, "Gone Guy", "Guy", "AVL", status="u", news="Has joined Getafe on loan", added="2026-09-01T10:00:00Z", owned=2),
           player(6, "Fit Fred", "Fred", "TOT"), player(7, "Top Scorer", "Scorer", "BHA"), player(8, "Second", "Second", "BRE"), player(9, "Third", "Third", "CHE")]
BY = {p["id"]: p for p in PLAYERS}
EVENT9 = {"id": 9, "is_current": True, "is_next": False, "finished": False, "deadline_time": "2026-10-31T11:00:00Z", "average_entry_score": 31}
EVENT10 = {"id": 10, "is_current": False, "is_next": True, "finished": False, "deadline_time": "2026-11-06T18:30:00Z", "average_entry_score": 0}
BOOT = {"events": [EVENT9, EVENT10]}
ENTRY = {"name": "merino parade fc"}
PICKS = {"active_chip": None, "entry_history": {"event": 9, "points": 25, "overall_rank": 2729094, "points_on_bench": 2, "event_transfers_cost": 4},
         "picks": [{"element": 1, "is_captain": True, "multiplier": 2}, {"element": 2, "is_captain": False, "multiplier": 1},
                   {"element": 4, "is_captain": False, "multiplier": 1}, {"element": 6, "is_captain": False, "multiplier": 1}]}
HISTORY = {"current": [{"event": 8, "overall_rank": 2099227}, {"event": 9, "overall_rank": 2729094}]}
LIVE = {1: 9, 2: 0, 4: 2, 6: 3, 7: 15, 8: 12, 9: 11}
DRAFT = {"league": {"name": "Hong Hu Express SuperLiga"},
         "league_entries": [{"id": 10, "entry_id": 100, "entry_name": "Oinkata", "player_first_name": "Rohan"},
                            {"id": 11, "entry_id": 186059, "entry_name": "Gabi III", "player_first_name": "Dadi"}],
         "standings": [{"league_entry": 11, "rank": 2, "event_total": 25, "total": 307}, {"league_entry": 10, "rank": 1, "event_total": 62, "total": 435}]}

# ---- FPL's real timestamp formats ----
check("times with and without fractions of a second are both read",
      fc.parse_time("2026-10-24T17:00:09.115906Z") == T(2026, 10, 24, 17, 0, 9, 115906) and fc.parse_time("2026-11-06T18:30:00Z") == T(2026, 11, 6, 18, 30))
check("a missing time is None", fc.parse_time(None) is None and fc.parse_time("") is None)
check("recent news with a fractional-second timestamp is recognised", fc.is_recent("2026-11-03T09:00:09.115906Z", T(2026, 11, 3, 12)) and not fc.is_recent("2026-10-24T17:00:09.115906Z", T(2026, 11, 3, 12)))

# ---- Deadline reminder ----
FRIDAY = T(2026, 11, 5, 23, 15)     # the Friday 7:15am Singapore edition: 19 hours and 15 minutes before the deadline (Saturday 2:30am SGT = 18:30 UTC on Friday)
d = fc.deadline(BOOT, FRIDAY)
check("within 24 hours of the deadline (the Friday morning edition): the reminder, in Singapore time", d == {"gw": 10, "when": "Sat 7 Nov, 2:30am SGT"}, d)
check("more than 24 hours out (the Thursday morning edition, 43 hours before) and the Wednesday one: no reminder", fc.deadline(BOOT, T(2026, 11, 4, 23, 15)) is None and fc.deadline(BOOT, T(2026, 11, 3, 23, 15)) is None)
check("the edition after the deadline (Saturday 7:15am Singapore time, 23:15 UTC on Friday) is past it, so exactly one edition falls inside the 24 hours", fc.deadline(BOOT, T(2026, 11, 6, 23, 15)) is None and fc.deadline(BOOT, T(2026, 11, 6, 18, 31)) is None)
check("after the deadline: no reminder", fc.deadline(BOOT, T(2026, 11, 7)) is None)
check("the reminder never shows once there is no next gameweek", fc.deadline({"events": [EVENT9]}, T(2026, 11, 4)) is None)

# ---- Your team ----
import re as _re  # noqa: E402
tx = lambda h: _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", h)).strip()  # noqa: E731
box = fc.classic_box(ENTRY, PICKS, HISTORY, LIVE, BY, EVENT9)
check("your team box: the team, the gameweek's points against the average ('so far' while it runs), the overall rank with its move arrow, captain with his points, bench points",
      tx(box) == "Team merino parade fc Gameweek 9 so far 25 pts (AVG: 31) Overall rank 2,729,094 ▼629,867 Captain 18 pts Haaland Bench 2 pts Transfer cost -4 pts", tx(box))
check("it is the shared summary box (labels, gold figures), not a paragraph of white text", box.startswith('<ul class="roundup">') and box.count('class="n"') == 4 and "<p>" not in box, box[:120])
fin = fc.classic_box(ENTRY, {**PICKS, "active_chip": "wildcard"}, {"current": [{"event": 8, "overall_rank": 3000000}, {"event": 9, "overall_rank": 2729094}]}, LIVE, BY, {**EVENT9, "finished": True})
check("a finished gameweek drops 'so far'; a rank that improved shows ▲ with the places gained; a chip is named", "so far" not in tx(fin) and "▲270,906" in tx(fin) and "Chip wildcard" in tx(fin), tx(fin))
nohist = fc.classic_box(ENTRY, PICKS, {}, LIVE, BY, EVENT9)
check("no history: the rank is given without a move arrow", "▼" not in nohist and "▲" not in nohist and "2,729,094" in nohist)
check("no transfer cost and no chip: those two rows are left out", "Transfer cost" not in fc.classic_box(ENTRY, {**PICKS, "entry_history": {**PICKS["entry_history"], "event_transfers_cost": 0}}, HISTORY, LIVE, BY, EVENT9) and "Chip" not in box)

# ---- Squad alerts ----
al = fc.squad_alerts(PICKS, BY)
check("squad alerts: only your players who are not fit (Saka injured, Doubtful Dan, who FPL calls Dan), shown by FPL's short name (web_name: Saka, not Bukayo Saka)", [a["name"] for a in al] == ["Saka", "Dan"], al)
h = fc.alerts_html(al)
check("alerts show FPL's note, and the chance only for a doubt", "Thigh injury - Unknown return date" in h and "(50% chance of playing)" in h and h.count("chance of playing") == 1, h)
check("a chance already in FPL's note is not repeated",
      fc.alerts_html([{"name": "A", "team": "T", "status": "d", "news": "Calf injury - 50% chance of playing", "chance": 50, "added": None}]).count("chance of playing") == 1)
check("alerts escape text", "&lt;" in fc.alerts_html([{"name": "<x>", "team": "T", "status": "i", "news": "", "chance": None, "added": None}]))
check("nothing flagged, no alerts block", fc.alerts_html([]) == "")

# ---- Draft league ----
sig, table = fc.draft_table(DRAFT, 186059, 9)
check("draft table: sorted by rank, caption names the league and gameweek", table.index("Oinkata") < table.index("Gabi III") and "Hong Hu Express SuperLiga After Gameweek 9" in table)
check("your Draft team is marked so it shows in bold", table.count("mine") == 1 and table.index("mine") < table.index("Gabi III"), table)
check("the table shows team names only, no managers' names (the site is public)", "Rohan" not in table and "Dadi" not in table and "Manager" not in table)
check("the draft table shows rank movement from last gameweek's rank (up, down or level)",
      "▲" in fc.draft_table({**DRAFT, "standings": [{"league_entry": 11, "rank": 1, "last_rank": 3, "event_total": 5, "total": 9}, {"league_entry": 10, "rank": 2, "last_rank": 1, "event_total": 5, "total": 8}]}, 1, 9)[1]
      and "▼" in fc.draft_table({**DRAFT, "standings": [{"league_entry": 11, "rank": 1, "last_rank": 3, "event_total": 5, "total": 9}, {"league_entry": 10, "rank": 2, "last_rank": 1, "event_total": 5, "total": 8}]}, 1, 9)[1]
      and "–" in fc.draft_table({**DRAFT, "standings": [{"league_entry": 11, "rank": 1, "last_rank": 1, "event_total": 5, "total": 9}, {"league_entry": 10, "rank": 2, "last_rank": 2, "event_total": 5, "total": 8}]}, 1, 9)[1])
check("the signature changes when a total changes", fc.draft_table({**DRAFT, "standings": [{**DRAFT["standings"][0], "total": 310}, DRAFT["standings"][1]]}, 186059, 9)[0] != sig)

# ---- Top scorers and the watch list ----
ts = fc.top_scorers(LIVE, BY, n=3)
check("top scorers: best first, three of them, with rank, name, team and points", ts == [[1, "Top Scorer", "BHA", 15], [2, "Second", "BRE", 12], [3, "Third", "CHE", 11]], ts)
tie = fc.top_scorers({7: 10, 8: 10, 9: 10}, BY, n=3)
check("tied scores are ordered by the short name FPL shows (Scorer, Second, Third), so the output is stable", [t[1] for t in tie] == ["Top Scorer", "Second", "Third"], tie)
NOW = T(2026, 11, 3, 12)
w = fc.watch_items(PLAYERS, {}, NOW)
check("watch: heavily owned players with new news (Cash, 20% owned) - but not Saka (old news) or Dan (3% owned)", [x["name"] for x in w] == ["Matty Cash"], w)
check("watch: shown once", fc.watch_items(PLAYERS, {"3": "2026-11-03T09:00:00Z"}, NOW) == [])
_cash = next(p_["id"] for p_ in PLAYERS if p_["name"] == "Matty Cash")
check("watch: a player already in D's own squad is left out (his news is in the Injuries list above, D 2026-11-05); another squad member changes nothing",
      fc.watch_items(PLAYERS, {}, NOW, exclude={_cash}) == [] and [x["name"] for x in fc.watch_items(PLAYERS, {}, NOW, exclude={999999})] == ["Matty Cash"])

# ---- The three FPL lists (D, 2026-11-04): Bench Swaps, Underperforming Players, Potential Pick Ups - averages over the last 3 gameweeks ----
def pick(el, pos, typ):
    return {"element": el, "position": pos, "element_type": typ, "is_captain": False, "multiplier": 1 if pos <= 11 else 0}


def pl(pid, name, typ, status="a", minutes=900, team="XXX"):
    return {"id": pid, "name": name, "web_name": name, "team": team, "status": status, "news": "", "news_added": None, "chance_next": None, "owned": 5.0, "type": typ, "cost": 60, "minutes": minutes}


HP = {i: player(i, f"Player {i}", f"P{i}", "ARS") for i in range(101, 120)}
SQUAD = {"picks": [pick(101, 1, 1), pick(102, 2, 2), pick(103, 3, 2), pick(104, 4, 3), pick(105, 5, 3), pick(106, 6, 3), pick(107, 7, 4),
                   pick(108, 12, 1), pick(109, 13, 2), pick(110, 14, 3), pick(111, 15, 4)]}
G = lambda pts, mins: {"points": pts, "minutes": mins}  # noqa: E731
TREND = {7: {101: G(3, 90), 102: G(1, 60), 103: G(6, 90), 104: G(2, 90), 105: G(8, 90), 106: G(7, 90), 107: G(1, 0), 109: G(2, 90), 110: G(9, 90), 111: G(0, 0)},
         8: {101: G(3, 90), 102: G(1, 70), 103: G(5, 90), 104: G(2, 90), 105: G(6, 90), 106: G(5, 90), 107: G(0, 0), 109: G(2, 90), 110: G(8, 90), 111: G(0, 0)},
         9: {101: G(3, 90), 102: G(0, 0), 103: G(7, 90), 104: G(2, 90), 105: G(9, 90), 106: G(6, 90), 107: G(9, 90), 109: G(2, 90), 110: G(7, 90), 111: G(0, 0)}}
rv = fc.transfer_review(SQUAD, TREND, HP, [])
ids = lambda rows: [x["player"]["id"] for x in rows]  # noqa: E731
check("underperforming: starters averaging 2.5 or less a gameweek over 3 (102: 2 points = 0.7, 104: 6 points = 2.0), the lowest first", ids(rv["outs"]) == [102, 104] and round(rv["outs"][0]["avg"], 2) == 0.67 and rv["outs"][1]["avg"] == 2.0, rv["outs"])
check("a starter at 3.0 (101), 3.3 (107) or 6.0 (103) is not underperforming", not set(ids(rv["outs"])) & {101, 103, 105, 106, 107}, ids(rv["outs"]))
check("the bench is never listed as underperforming (111 scored 0, 108 nothing)", not set(ids(rv["outs"])) & {108, 109, 110, 111})
check("bench swap: the benched midfielder (110, 8.0 a gameweek) over the worst starting midfielder (104, 2.0)", len(rv["swaps"]) == 1 and rv["swaps"][0]["player"]["id"] == 110 and rv["swaps"][0]["over"]["id"] == 104 and (rv["swaps"][0]["avg"], rv["swaps"][0]["over_avg"]) == (8.0, 2.0), rv["swaps"])
check("a bench defender 1.3 a gameweek better than his worst starter (109 over 102) is not 'severe' enough; an empty-handed bench keeper or forward is not a swap", ids(rv["swaps"]) == [110])
check("exactly 2.0 better counts (the edge)", ids(fc.transfer_review({"picks": [pick(101, 1, 1), pick(109, 13, 2), pick(102, 2, 2)]}, {7: {102: G(0, 0), 109: G(6, 90)}, 8: {102: G(0, 0), 109: G(0, 90)}, 9: {102: G(0, 0), 109: G(0, 90)}}, HP, [])["swaps"]) == [109])
inj_bench = {**HP, 110: player(110, "Hurt Bench", "HB", "ARS", status="i")}
check("an injured bench player is not suggested", fc.transfer_review(SQUAD, TREND, inj_bench, [])["swaps"] == [])
inj_start = {**HP, 102: player(102, "Hurt Starter", "HS", "ARS", status="s")}
check("a suspended or injured starter is left to the Injuries list, not listed as underperforming", 102 not in ids(fc.transfer_review(SQUAD, TREND, inj_start, [])["outs"]))
check("fewer than 3 gameweeks of data gives nothing at all", fc.transfer_review(SQUAD, {7: TREND[7], 8: TREND[8]}, HP, []) == {"gws": [7, 8], "swaps": [], "outs": [], "pickups": []})
check("the Tzolis case: a fit starter on 0, 0, 0 (never played) is underperforming", ids(fc.transfer_review({"picks": [pick(120, 2, 3)]}, {7: {}, 8: {}, 9: {}}, {120: player(120, "Never Plays", "NP", "ARS")}, [])["outs"]) == [120])

# Pick ups: squad MID average (200: 2 pts, 210: 7 pts over 3 weeks -> 0.7 and 2.3, so 1.5), DEF average 3.0
UPS = {"picks": [pick(200, 5, 3), pick(210, 14, 3), pick(220, 2, 2)]}
CANDS = [pl(200, "Slow Mid", 3), pl(210, "Bench Mid", 3), pl(220, "My Def", 2), pl(301, "Hot Mid", 3), pl(302, "Hotter Mid", 3), pl(303, "Warm Mid", 3), pl(304, "Cooler Mid", 3),
         pl(305, "Injured Mid", 3, status="i"), pl(306, "Cameo Mid", 3), pl(307, "Hot Def", 2), pl(308, "Weak Def", 2), pl(309, "Doubtful Mid", 3, status="d")]
UT = {7: {200: G(1, 90), 210: G(2, 90), 220: G(3, 90), 301: G(8, 90), 302: G(20, 90), 303: G(5, 90), 304: G(2, 90), 305: G(12, 90), 306: G(14, 20), 307: G(8, 90), 308: G(2, 90), 309: G(9, 90)},
      8: {200: G(0, 90), 210: G(3, 90), 220: G(3, 90), 301: G(7, 90), 302: G(18, 90), 303: G(5, 90), 304: G(2, 90), 305: G(10, 90), 306: G(0, 0), 307: G(8, 90), 308: G(2, 90), 309: G(9, 90)},
      9: {200: G(1, 90), 210: G(2, 90), 220: G(3, 90), 301: G(6, 90), 302: G(15, 90), 303: G(4, 90), 304: G(2, 90), 305: G(9, 90), 306: G(0, 0), 307: G(8, 90), 308: G(2, 90), 309: G(9, 90)}}
UH = {c["id"]: c for c in CANDS}
pu = fc.transfer_review(UPS, UT, UH, CANDS)["pickups"]
check("pick ups: two per position at most, defenders before midfielders, best average first: Hot Def (8.0), then Hotter Mid (17.7) and Hot Mid (7.0)", [u["player"]["id"] for u in pu] == [307, 302, 301], [(u["player"]["name"], u["pos"], round(u["avg"], 1)) for u in pu])
check("each carries the squad's average for its position: DEF 3.0, MID 1.5 (all of the squad's midfielders, bench included)", [(u["pos"], round(u["pos_avg"], 2)) for u in pu] == [("DEF", 3.0), ("MID", 1.5), ("MID", 1.5)], pu)
check("not suggested: squad members, the injured and doubtful, a one-appearance cameo, a defender below the squad's 3.0, or a third midfielder", not {200, 210, 220, 305, 306, 308, 309, 303, 304} & {u["player"]["id"] for u in pu})
check("positions the squad has nobody in (GKP, FWD) get no pick ups", {u["pos"] for u in pu} == {"DEF", "MID"})
ph = fc.review_html(fc.transfer_review(UPS, UT, UH, CANDS))
check("Pick Ups are grouped by position (Defenders then Midfielders here; Goalkeepers and Forwards only when the squad has them): a heading with the position and the squad's average for it once",
      "<strong>Potential Pick Ups</strong>" in ph and '<p class="gp"><strong>Defenders</strong> <span class="muted">(my squad avg.: <span class="sq">3.0</span>)</span></p>' in ph and '<p class="gp"><strong>Midfielders</strong> <span class="muted">(my squad avg.: <span class="sq">1.5</span>)</span></p>' in ph
      and ph.index("Defenders") < ph.index("Midfielders") and "Goalkeepers" not in ph and "Forwards" not in ph and "Attackers" not in ph, ph)
check("an entry is the player's short name, his club's code and the figure in gold: 'Hot Def (XXX) [8.0]'", '<li><strong>Hot Def</strong> (XXX) <span class="n">[8.0]</span></li>' in ph, ph)
check("the legend is said once under each title (twice here: Underperforming Players and Potential Pick Ups), never on a row", ph.count("Avg. points per Gameweek, last 3 GWs") == 2 and "<li>" in ph and all("Avg." not in li for li in re.findall(r"<li>.*?</li>", ph)), ph)
check("Forwards is FPL's name for the fourth position (not Attackers)", fc.GROUPS == {"GKP": "Goalkeepers", "DEF": "Defenders", "MID": "Midfielders", "FWD": "Forwards"})
fwd_rv = {"gws": [7, 8, 9], "swaps": [], "outs": [], "pickups": [{"player": pl(900, "Striker", 4), "pos": "FWD", "avg": 9.0, "pos_avg": 4.2}, {"player": pl(901, "Keeper", 1), "pos": "GKP", "avg": 7.0, "pos_avg": 2.8}]}
fh = fc.review_html(fwd_rv)
check("a forward and a goalkeeper: 'Goalkeepers' comes before 'Forwards', in FPL's order", fh.index("Goalkeepers") < fh.index("Forwards") and "Attackers" not in fh)
check("the entries still carry no 'Avg.' wording", "My squad" not in ph and "Transfer Suggestions" not in ph and "Pick-up" not in ph)
check("each group numbers from 1 (two entries in the midfield group: 1 and 2)", ph.count('<ol class="inj tight">') >= 2 and ph.split("Midfielders")[1].count("<li>") == 2, ph)
check("each group numbers from 1 (two entries in the midfield group: 1 and 2)", ph.count('<ol class="inj tight">') >= 2 and ph.split("Midfielders")[1].count("<li>") == 2, ph)
hh = fc.review_html(rv)
check("underperforming: header 'Underperforming Players', one legend line, then 'P102 (ARS) [0.7]' and 'P104 (ARS) [2.0]' (name, club code, figure in square brackets, in red), numbered", "<strong>Underperforming Players</strong></p><p class=\"muted\">Avg. points per Gameweek, last 3 GWs</p>" in hh and '<li><strong>P102</strong> (ARS) <span class="n bad">[0.7]</span></li>' in hh and '<li><strong>P104</strong> (ARS) <span class="n bad">[2.0]</span></li>' in hh and "Move out" not in hh and "Underperformers" not in hh, hh)
check("bench swaps come first, with their own legend: 'P110 (ARS) over P104 (ARS) [8.0] | [2.0]'", hh.index("Bench Swaps") < hh.index("Underperforming Players") and '<strong>P110</strong> (ARS) over <strong>P104</strong> (ARS) <span class="n">[8.0]</span> | <span class="n">[2.0]</span>' in hh and "(bench player | starter)" in hh, hh)
check("the legend is not repeated per row anywhere in the review", all("Avg." not in li for li in re.findall(r"<li>.*?</li>", hh)))
css = (Path(__file__).resolve().parent.parent / "kickoff" / "static" / "style.css").read_text()
check("one font size for everything in the FPL review and Injuries blocks: the wrapper sets headings, group headings, legend and entries to the same 16px", ".fplrev p, .fplrev ol, .fplrev li, .fplrev strong { font-size: 16px; }" in css)
check("an empty list leaves out its heading; nothing at all gives no block", "Potential Pick Ups" not in hh and fc.review_html({"swaps": [], "outs": [], "pickups": []}) == "")
calls = []
SQ_PICKS = {**PICKS, **SQUAD, "entry_history": PICKS["entry_history"]}
PL2 = PLAYERS + list(HP.values())
fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 2, 9), trend_fn=lambda: calls.append(1) or TREND)
check("far from the deadline, the lists are not worked out at all (no wasted requests)", calls == [])
html_near, _ = fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, FRIDAY, trend_fn=lambda: TREND)
check("within 24 hours of the deadline the corner includes the lists", "Underperforming Players" in html_near and "Bench Swaps" in html_near, html_near[:300])
html_none, _ = fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, FRIDAY, trend_fn=lambda: {})
check("if the gameweek data is unavailable the corner still builds without the lists", "Underperforming Players" not in html_none and "merino parade fc" in html_none)

# ---- Demo mode shows everything ----
far = T(2026, 11, 2, 9)
plain, _ = fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, far, trend_fn=lambda: TREND)
demo, _ = fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, far, trend_fn=lambda: TREND, demo=True)
check("normally, four days before the deadline the corner is left out altogether: no reminder, no lists, no heading", plain == "")
check("in demo mode the deadline reminder and the hints appear anyway", "Deadline:" in demo and "Underperforming Players" in demo, demo[:200])

# ---- The whole corner ----
FRESH = [dict(p, news_added="2026-11-05T09:00:00Z") if p["id"] == 3 else p for p in PLAYERS]      # Cash's suspension news is a few hours old on Friday morning
html, st = fc.build(BOOT, FRESH, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, FRIDAY)
check("the Friday corner has a heading, the deadline, your team box, your squad, the draft table", html.startswith("<h3>FPL Corner</h3>") and "Deadline:" in html and "merino parade fc" in html and "Injuries" in html and '<ol class="inj">' in html and "Hong Hu" in html, html[:200])
check("the first build records the draft table and the watch items it showed", "draft" in st and st.get("watch_seen", {}).get("3") == "2026-11-05T09:00:00Z", st)
html2, st2 = fc.build(BOOT, FRESH, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, st, FRIDAY)
check("the Draft table is part of every corner (even when its standings are unchanged since the last time), and so is your team box", "Hong Hu" in html2 and "merino parade fc" in html2)
check("the Draft table has the league's name with the gameweek, your team highlighted, the move arrows and both team names", "Hong Hu Express SuperLiga After Gameweek 9" in html and 'class="mine hl"' in html and "Gabi III" in html and "Oinkata" in html, html[:100])
for quiet_day in (T(2026, 11, 2, 23, 15), T(2026, 11, 3, 23, 15), T(2026, 11, 4, 23, 15), T(2026, 11, 6, 23, 15)):
    q, _ = fc.build(BOOT, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, quiet_day)
    check(f"on the morning of {quiet_day:%a %-d %b} (not within 24 hours of the deadline, no gameweek just finished) the corner is not shown at all, not even a squad news line", q == "", q[:80])
done = {**BOOT, "events": [{**EVENT9, "finished": True, "data_checked": True}, EVENT10]}
fin_html, fin_st = fc.build(done, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 3, 23, 15))
check("the morning after the gameweek's bonus points are final (data_checked) the recap shows once: your box, the Draft table, the gameweek's top scorers; no deadline, no squad alerts, no hints", "Gameweek 9 Top Scorers" in fin_html and "Top Scorer" in fin_html and "Hong Hu" in fin_html and "merino parade fc" in fin_html
      and "Deadline:" not in fin_html and "Injuries" not in fin_html and fin_st.get("recap_gw") == 9, fin_html[:200])
again, _ = fc.build(done, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, fin_st, T(2026, 11, 4, 23, 15))
check("and only once: the next morning it is gone", again == "")
unchecked = {**BOOT, "events": [{**EVENT9, "finished": True, "data_checked": False}, EVENT10]}
check("a finished gameweek whose bonus points are not yet final (data_checked false: the last match was played but FPL is still adding bonus) does not trigger it yet", fc.build(unchecked, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 3, 23, 15))[0] == "")
mid = {**BOOT, "events": [{**EVENT9, "finished": False, "data_checked": False}, EVENT10]}
check("a gameweek still being played does not trigger it", fc.build(mid, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 3, 23, 15))[0] == "")
both, _ = fc.build({**BOOT, "events": [{**EVENT9, "finished": True, "data_checked": True}, EVENT10]}, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, FRIDAY)
check("when the deadline morning is also the first morning after the bonus points are final, one corner has both: the deadline and the top scorers", "Deadline:" in both and "Top Scorers" in both and both.count("<h3>FPL Corner</h3>") == 1)
check("FPL Watch (new injury news on heavily owned players) belongs to the deadline morning only", "FPL Watch" in html and "FPL Watch" not in fin_html)

css2 = (Path(__file__).resolve().parent.parent / "kickoff" / "static" / "style.css").read_text()
check("D's colours: the underperformers' figures and the squad average's number are the same pastel red (and the squad average is bold); the pick-up figures stay gold", ".fplrev .n.bad { color: #f19a9a; }" in css2 and ".fplrev .sq { color: #f19a9a; font-weight: 700; }" in css2 and ".fplrev .n { color: var(--gold)" in css2)
check("every figure is in square brackets, none bare: no span of class n holds a number without them", all(re.fullmatch(r"\[\d+\.\d\]", m) for m in re.findall(r'<span class="n(?: bad)?">(.*?)</span>', ph + hh)) and len(re.findall(r'<span class="n(?: bad)?">', ph + hh)) >= 6, re.findall(r'<span class="n(?: bad)?">(.*?)</span>', ph + hh))

check("D, 2026-11-04: my Draft team (Gabi III) is bold AND gold: its row carries both classes 'mine' and 'hl'; no other row does", len(re.findall(r'<tr class="mine hl">', table)) == 1 and table.index('class="mine hl"') < table.index("Gabi III") and table.count('class="hl"') + table.count("hl\"") == 1, table)
css3 = (Path(__file__).resolve().parent.parent / "kickoff" / "static" / "style.css").read_text()
check("the css that makes the row gold and the team name bold both exist", "tr.hl td { color: var(--gold)" in css3 and "tr.mine td:nth-child(2) { font-weight: 700; }" in css3)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
