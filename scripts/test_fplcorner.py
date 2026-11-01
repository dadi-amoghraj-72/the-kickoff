"""Offline tests for the FPL corner. Run: .venv/bin/python scripts/test_fplcorner.py"""
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
d = fc.deadline(BOOT, T(2026, 11, 4, 12))
check("within 72 hours of the deadline: the reminder, in Singapore time", d == {"gw": 10, "when": "Saturday 7 November, 2:30am SGT"}, d)
check("more than 72 hours out: no reminder", fc.deadline(BOOT, T(2026, 11, 2, 12)) is None)
check("after the deadline: no reminder", fc.deadline(BOOT, T(2026, 11, 7)) is None)
check("the reminder never shows once there is no next gameweek", fc.deadline({"events": [EVENT9]}, T(2026, 11, 4)) is None)

# ---- Your team ----
line = fc.classic_line(ENTRY, PICKS, HISTORY, LIVE, BY, EVENT9)
check("your team line: name, points vs average, 'so far' while the gameweek runs", "<strong>merino parade fc</strong>" in line and "Gameweek 9 so far: 25 pts (average 31)" in line, line)
check("overall rank with thousands separators and its move", "overall rank 2,729,094, down 629,867" in line, line)
check("captain's points include the multiplier", "captain Haaland 18 pts" in line, line)
check("bench points and a transfer cost are mentioned", "2 on the bench" in line and "4 pt transfer cost" in line)
fin = fc.classic_line(ENTRY, {**PICKS, "active_chip": "wildcard"}, {"current": [{"event": 8, "overall_rank": 3000000}, {"event": 9, "overall_rank": 2729094}]}, LIVE, BY, {**EVENT9, "finished": True})
check("a finished gameweek drops 'so far'; rank improving says 'up'; a chip is named", "so far" not in fin and "up 270,906" in fin and "chip: wildcard" in fin, fin)
check("no history: the rank is given without a move", ", down" not in fc.classic_line(ENTRY, PICKS, {}, LIVE, BY, EVENT9) and "overall rank 2,729,094" in fc.classic_line(ENTRY, PICKS, {}, LIVE, BY, EVENT9))

# ---- Squad alerts ----
al = fc.squad_alerts(PICKS, BY)
check("squad alerts: only your players who are not fit (Saka injured, Doubtful Dan)", [a["name"] for a in al] == ["Bukayo Saka", "Doubtful Dan"], al)
h = fc.alerts_html(al)
check("alerts show FPL's note, and the chance only for a doubt", "Thigh injury - Unknown return date" in h and "(50% chance of playing)" in h and h.count("chance of playing") == 1, h)
check("alerts escape text", "&lt;" in fc.alerts_html([{"name": "<x>", "team": "T", "status": "i", "news": "", "chance": None, "added": None}]))
check("nothing flagged, no alerts block", fc.alerts_html([]) == "")

# ---- Draft league ----
sig, table = fc.draft_table(DRAFT, 186059, 9)
check("draft table: sorted by rank, caption names the league and gameweek", table.index("Oinkata") < table.index("Gabi III") and "Hong Hu Express SuperLiga After Gameweek 9" in table)
check("your Draft team is marked so it shows in bold", table.count("mine") == 1 and table.index("mine") < table.index("Gabi III"), table)
check("the table shows team names only, no managers' names (the site is public)", "Rohan" not in table and "Dadi" not in table and "Manager" not in table)
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

# ---- Transfer hints (a nudge near the deadline) ----
def pick(el, pos, typ):
    return {"element": el, "position": pos, "element_type": typ, "is_captain": False, "multiplier": 1 if pos <= 11 else 0}


HP = {i: player(i, f"Player {i}", f"P{i}", "ARS") for i in range(101, 120)}
SQUAD = {"picks": [pick(101, 1, 1), pick(102, 2, 2), pick(103, 3, 2), pick(104, 4, 3), pick(105, 5, 3), pick(106, 6, 3), pick(107, 7, 4),
                   pick(108, 12, 1), pick(109, 13, 2), pick(110, 14, 3), pick(111, 15, 4)]}
G = lambda pts, mins: {"points": pts, "minutes": mins}  # noqa: E731
TREND = {7: {101: G(3, 90), 102: G(1, 60), 103: G(6, 90), 104: G(2, 90), 105: G(8, 90), 106: G(7, 90), 107: G(1, 0), 109: G(2, 90), 110: G(9, 90), 111: G(0, 0)},
         8: {101: G(3, 90), 102: G(1, 70), 103: G(5, 90), 104: G(2, 90), 105: G(6, 90), 106: G(5, 90), 107: G(0, 0), 109: G(2, 90), 110: G(8, 90), 111: G(0, 0)},
         9: {101: G(3, 90), 102: G(0, 0), 103: G(7, 90), 104: G(2, 90), 105: G(9, 90), 106: G(6, 90), 107: G(9, 90), 109: G(2, 90), 110: G(7, 90), 111: G(0, 0)}}
hints = fc.transfer_hints(SQUAD, TREND, HP)
outs = [h for h in hints if h["kind"] == "out"]
swaps = [h for h in hints if h["kind"] == "swap"]
check("a starter with 2 points in 2 appearances (1.0 a game) is a 'move out?' candidate", any(h["player"]["id"] == 102 and h["points"] == 2 and h["apps"] == 2 for h in outs), hints)
check("a starter averaging 2.0 over three appearances (104: 2, 2, 2) is flagged; one averaging 6 is not", any(h["player"]["id"] == 104 for h in outs) and not any(h["player"]["id"] == 103 for h in outs), outs)
check("a starter who barely played (107: one appearance) is not flagged: injuries are covered elsewhere", not any(h["player"]["id"] == 107 for h in outs), outs)
check("the quietest (fewest points) comes first", outs[0]["player"]["id"] == 102 and outs[0]["points"] <= outs[-1]["points"], outs)
check("a bench midfielder with 24 points against the worst starting midfielder's 6 is a swap (gap 18)",
      any(h["player"]["id"] == 110 and h["over"]["id"] == 104 and (h["points"], h["over_points"], h["gap"]) == (24, 6, 18) for h in swaps), swaps)
check("a bench defender with 6 points against a starter's 8 is not", not any(h["player"]["id"] == 109 for h in swaps), swaps)
check("the bench goalkeeper is never suggested", not any(h["player"]["id"] == 108 for h in hints))
check("a bench forward with 0 points is not a swap", not any(h["player"]["id"] == 111 for h in swaps))
check("at most three hints, with 'move out' ahead of swaps", len(hints) <= 3 and [h["kind"] for h in hints] == sorted((h["kind"] for h in hints), key=lambda k: k != "out"), [h["kind"] for h in hints])
check("a tight squad with nothing to flag gives no hints", fc.transfer_hints(SQUAD, {7: {102: G(8, 90)}, 8: {102: G(8, 90)}}, HP) == [])
hh = fc.hints_html(hints, [7, 8, 9])
check("hints read: name, team, the point totals and 'last 3 gameweeks', labelled a nudge not advice",
      "Transfer hints" in hh and "not advice" in hh and "last 3 gameweeks" in hh and "Move out?" in hh and "P" in hh, hh[:300])
check("no hints, no block", fc.hints_html([], [7]) == "")
calls = []
SQ_PICKS = {**PICKS, **SQUAD, "entry_history": PICKS["entry_history"]}
BY2 = {**BY, **HP}
PL2 = PLAYERS + list(HP.values())
fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 2, 9), trend_fn=lambda: calls.append(1) or TREND)
check("far from the deadline, the hints are not worked out at all (no wasted requests)", calls == [])
html_near, _ = fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 4, 9), trend_fn=lambda: TREND)
check("within 72 hours of the deadline the corner includes the hints", "Transfer hints" in html_near)
html_none, _ = fc.build(BOOT, PL2, ENTRY, SQ_PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 4, 9), trend_fn=lambda: {})
check("if the gameweek data is unavailable the corner still builds without hints", "Transfer hints" not in html_none and "merino parade fc" in html_none)

# ---- The rule as D first asked for it: under 2 points in each of the last 3 gameweeks ----
QUIET = {"picks": [pick(101, 1, 1), pick(120, 2, 3), pick(121, 3, 3), pick(122, 4, 3), pick(123, 12, 3)]}
HQ = {**HP, 120: player(120, "Never Plays", "Plays", "ARS"), 121: player(121, "One Cameo", "Cameo", "LIV"), 122: player(122, "Injured Starter", "Inj", "ARS", status="i"),
      123: player(123, "Bench Guy", "Bench", "ARS")}
QT = {7: {120: G(0, 0), 121: G(0, 0), 122: G(0, 0)}, 8: {120: G(0, 0), 121: G(1, 31), 122: G(0, 0)}, 9: {120: G(0, 0), 121: G(0, 0), 122: G(1, 0)}}
qh = fc.transfer_hints(QUIET, QT, HQ)
check("a starter with 0, 0, 0 points (no minutes at all) is flagged: the Tzolis case", any(h["player"]["id"] == 120 and h["reason"] == "quiet" for h in qh), qh)
check("a starter with 0, 1, 0 points and a 31-minute cameo is flagged: the Szoboszlai case", any(h["player"]["id"] == 121 and h["weekly"] == [0, 1, 0] for h in qh), qh)
check("an injured starter is left to the squad alerts, not hinted", not any(h["player"]["id"] == 122 for h in qh))
check("a quiet starter reads as the three weekly scores", "0, 1, 0 points in the last 3 gameweeks" in fc.hints_html(qh, [7, 8, 9]), fc.hints_html(qh, [7, 8, 9]))
check("two gameweeks of data are not enough for the 'under 2 in each of 3' rule", not any(h.get("reason") == "quiet" for h in fc.transfer_hints(QUIET, {7: QT[7], 8: QT[8]}, HQ)))
check("quiet players come ahead of merely low-scoring ones", [h["reason"] for h in hints if h["kind"] == "out"] == sorted((h["reason"] for h in hints if h["kind"] == "out"), key=lambda r: r != "quiet"), [h.get("reason") for h in hints])

# ---- The whole corner ----
html, st = fc.build(BOOT, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 4, 9))
check("the corner has a heading, the deadline, your team, your squad, the draft table",
      html.startswith("<h3>FPL Corner</h3>") and "Deadline:" in html and "merino parade fc" in html and "Your squad:" in html and "Hong Hu" in html, html[:200])
check("the first build records the draft table and the watch items it showed", "draft" in st and st.get("watch_seen", {}).get("3") == "2026-11-03T09:00:00Z", st)
html2, st2 = fc.build(BOOT, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, st, T(2026, 11, 4, 9))
check("next time: the draft table is skipped when nothing changed; your team line stays", "Hong Hu" not in html2 and "merino parade fc" in html2)
quiet, _ = fc.build(BOOT, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, None, 186059, {}, T(2026, 11, 2, 9))
check("far from the deadline, only squad news from the last 36 hours is shown (Dan's, not Saka's)", "Doubtful Dan" in quiet and "Bukayo Saka" not in quiet, quiet)
done = {**BOOT, "events": [{**EVENT9, "finished": True}, EVENT10]}
fin_html, fin_st = fc.build(done, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, {}, T(2026, 11, 3, 9))
check("a finished gameweek shows its top scorers", "Gameweek 9 Top Scorers" in fin_html and "Top Scorer" in fin_html)
again, _ = fc.build(done, PLAYERS, ENTRY, PICKS, HISTORY, LIVE, DRAFT, 186059, fin_st, T(2026, 11, 4, 9))
check("and only once", "Top Scorers" not in again)
partial, _ = fc.build(BOOT, PLAYERS, None, None, None, None, DRAFT, 186059, {}, T(2026, 11, 2, 9))
check("if your team's data is unavailable, the rest still appears", "Hong Hu" in partial and "merino" not in partial)
empty, _ = fc.build(BOOT, [player(1, "A", "A")], None, None, None, None, None, 186059, {}, T(2026, 11, 2, 9))
check("nothing to say means no corner at all", empty == "", empty)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
