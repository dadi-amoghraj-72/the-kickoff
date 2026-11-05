"""Tests for golf: the standings worked out from ESPN's rounds, the men's top 25 with D's players, the women's weekend top 10, the final in gold, the start note and the Big Stuff winner line.
Real 2025 boards (the Masters, the Evian Championship) as ESPN gives them once finished; a board "in the middle of the event" is made from them by emptying the later rounds. Run: .venv/bin/python scripts/test_golf.py"""
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import golf  # noqa: E402

FX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
masters, evian, players = load("golf_masters_2025.json"), load("golf_evian_2025.json"), load("golf_players_2025.json")
utc = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731
text = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&#x27;", "'")  # noqa: E731


def upto(board, n, partial=0):
    """The board as it stood after round n: later rounds emptied (and `partial` players half way through round n+1)."""
    b = copy.deepcopy(board)
    e = b["events"][0]
    for i, c in enumerate(e["competitions"][0]["competitors"]):
        for l in c["linescores"]:
            if l["period"] > n:
                if partial and l["period"] == n + 1 and i < partial and l["holes"] > 0:
                    l["holes"] = 9
                else:
                    l["holes"], l["value"], l["displayValue"] = 0, 0, "-"
    e["status"]["type"].update(state="in", completed=False, name="STATUS_IN_PROGRESS")
    return b


def with_end(board, when):
    b = copy.deepcopy(board)
    b["events"][0]["endDate"] = when
    return b


# ---- reading ESPN's numbers ---------------------------------------------------------------------------
check("scores against par: E is 0, -6 and +1 are numbers, '-' and '' are nothing", golf.par("E") == 0 and golf.par("-6") == -6 and golf.par("+1") == 1 and golf.par("-") is None and golf.par("") is None and golf.par(None) is None)
check("and are shown the way golfers write them", golf.show(0) == "E" and golf.show(-6) == "-6" and golf.show(2) == "+2")
ps = golf.people(masters["events"][0])
check("the 2025 Masters field is read: 95 players, McIlroy first and a playoff", len(ps) == 95 and ps[0]["name"] == "Rory McIlroy" and ps[0]["playoff"] and ps[0]["total"] == -11)
check("all four rounds are finished", golf.finished_rounds(ps) == 4)
for n in (1, 2, 3):
    check(f"after emptying the rounds past {n}: round {n} is the latest finished", golf.finished_rounds(golf.people(upto(masters, n)["events"][0])) == n)
check("half way through round 3 (ten players on the course): round 2 is still the latest finished", golf.finished_rounds(golf.people(upto(masters, 2, partial=10)["events"][0])) == 2)
wd = upto(masters, 3, partial=1)
for c in wd["events"][0]["competitions"][0]["competitors"][:1]:
    c["linescores"][2]["holes"] = 9                               # one player stopped in round 3 (a withdrawal) while round 4 has begun for others
for c in wd["events"][0]["competitions"][0]["competitors"][1:6]:
    c["linescores"][3]["holes"] = 4
check("a player who stopped part-way does not hold the round back once the next round has begun", golf.finished_rounds(golf.people(wd["events"][0])) == 3)

# ---- standings, cross-checked against the raw rounds ----------------------------------------------------
raw = masters["events"][0]["competitions"][0]["competitors"]
cum2 = {c["athlete"]["displayName"]: sum(golf.par(l["displayValue"]) for l in c["linescores"] if l["period"] <= 2) for c in raw if len([l for l in c["linescores"] if l["period"] <= 2 and l["holes"] == 18]) == 2}
best = min(cum2.values())
st2 = golf.standing(golf.people(upto(masters, 2)["events"][0]), 2)
check("after round 2 the leader and his total match a separate sum of the raw rounds (Rose, -8)", st2[0]["cum"] == best == -8 and st2[0]["p"]["name"] == "Justin Rose", (st2[0]["p"]["name"], best))
check("everyone still in is ranked: 95 players after round 2, ties share a position (T3)", len(st2) == 95 and [x["rank"] for x in st2[:4]] == [1, 2, 3, 3])
check("the cut: after round 3 only the 53 players who made it remain (counted separately from the raw rounds)", len(golf.standing(golf.people(upto(masters, 3)["events"][0]), 3)) == 53)
check("pos(): a tie is T3, alone is 3", golf.pos(3, 2) == "T3" and golf.pos(3, 1) == "3")

# ---- the men's table: top 25, D's players below ------------------------------------------------------------
out = golf.run({"pga": upto(masters, 2)}, utc(2025, 4, 12), {})
html = out["blocks"][0]
t = text(html)
check("men's table after round 2: titled with the event and the round, columns Pos Player Rd Total Behind", "Masters Tournament · After round 2" in t and "Pos Player Rd Total Behind" in t, t[:200])
check("the leader's row is gold and has no strokes behind; the next player is one behind", html.count('class="p1"') == 1 and "Justin Rose -1 -8 –" in t and "Bryson DeChambeau -4 -7 1" in t, t[:400])
body_rows = re.findall(r"<tr(?: class=\"([^\"]*)\")?>", html.split("<tbody>")[1])
check("25 rows in the top 25 (the leader's p1) and D's players below them (muted 'also' rows)", sum(1 for c in body_rows if c in ("", "p1")) == 25 and sum(1 for c in body_rows if c == "also") >= 1 and body_rows[:25].count("also") == 0, body_rows)
check("D's players outside the top 25 are listed below it with their real position and strokes behind (Rahm and Spieth T40, Koepka and Mickelson T67, Bhatia T40 at +2 ...)", all(x in t for x in ["T40 Jon Rahm -1 +2 10", "T40 Jordan Spieth +1 +2 10", "T40 Akshay Bhatia +4 +2 10", "T67 Brooks Koepka +3 +5 13", "T67 Phil Mickelson +2 +5 13"]), t[-300:])
check("a player who is not in the field is simply not listed (Tiger Woods was not at the 2025 Masters)", "Woods" not in t)
check("state: round 2 is remembered, so the same board gives nothing the next morning", golf.run({"pga": upto(masters, 2)}, utc(2025, 4, 13), out["state"])["blocks"] == [])
nxt = golf.run({"pga": upto(masters, 3)}, utc(2025, 4, 13), out["state"])
check("and round 3, when finished, gives its own table", len(nxt["blocks"]) == 1 and "After round 3" in text(nxt["blocks"][0]))
under = golf.run({"pga": upto(masters, 2, partial=10)}, utc(2025, 4, 12), {})
check("round 3 under way: the table is still after round 2 and says the next round is under way (it does not move while players are on the course)", "After round 2 (next round under way)" in text(under["blocks"][0]))

# ---- the final ---------------------------------------------------------------------------------------------------
fin = golf.run({"pga": with_end(masters, "2025-04-13T04:00Z")}, utc(2025, 4, 14), {})
ft = text(fin["blocks"][0])
check("the final: McIlroy first (gold) after the playoff, Rose second, Reed third, Scheffler fourth, Im and DeChambeau tied fifth", "1 Rory McIlroy" in ft and "2 Justin Rose" in ft and "3 Patrick Reed" in ft and "4 Scottie Scheffler" in ft and "T5 Sungjae Im" in ft and "T5 Bryson DeChambeau" in ft and fin["blocks"][0].count('class="p1"') == 1, ft[:500])
check("D's players outside the top 25 on the final table: Bhatia T42 at +4 (15 behind); Koepka and Mickelson missed the cut (MC)", "T42 Akshay Bhatia -1 +4 15" in ft and "MC Brooks Koepka +5" in ft and "MC Phil Mickelson +5" in ft, ft[-400:])
check("the winner makes a Big Stuff line", fin["winners"] == ["Golf: Rory McIlroy wins the Masters Tournament (-11)"], fin["winners"])
check("the final is shown once", golf.run({"pga": with_end(masters, "2025-04-13T04:00Z")}, utc(2025, 4, 15), fin["state"])["blocks"] == [])
check("an event that finished a month ago is not news, even on the first run", golf.run({"pga": with_end(masters, "2025-04-13T04:00Z")}, utc(2025, 5, 20), {})["blocks"] == [])
pl = golf.run({"pga": with_end(players, players["events"][0]["endDate"])}, datetime.fromisoformat(players["events"][0]["endDate"].replace("Z", "+00:00")) + (utc(2025, 1, 2) - utc(2025, 1, 1)), {})
check("THE PLAYERS Championship gets the men's treatment under the name 'The Players Championship'", pl["blocks"] and "The Players Championship · Final" in text(pl["blocks"][0]) and pl["winners"][0].startswith("Golf: ") and "The Players Championship" in pl["winners"][0], pl["winners"])

check("D's players below the table are in order of position, never alphabetical: Bhatia T42, then the missed cuts in his list's order (Koepka, Mickelson)", [x["name"] for x in golf.extras_for(ps, golf.final_rows(ps, 25), 4)] == ["Akshay Bhatia", "Brooks Koepka", "Phil Mickelson"])
_r2 = golf.standing(golf.people(upto(masters, 2)["events"][0]), 2)[:25]
check("and after round 2, position order: T40 (Rahm, Spieth, Bhatia in his list's order), then T67 (Koepka, Mickelson)", [(x["pos"], x["name"]) for x in golf.extras_for(golf.people(upto(masters, 2)["events"][0]), _r2, 2)] == [("T40", "Jon Rahm"), ("T40", "Jordan Spieth"), ("T40", "Akshay Bhatia"), ("T67", "Brooks Koepka"), ("T67", "Phil Mickelson")])

# ---- the women's weekend ------------------------------------------------------------------------------------------
ev = evian["events"][0]
ev_end = ev["endDate"]
for n in (1, 2):
    check(f"women: nothing after round {n}", golf.run({"lpga": upto(evian, n)}, utc(2025, 7, 12), {})["blocks"] == [])
w3 = golf.run({"lpga": upto(evian, 3)}, utc(2025, 7, 13), {})
t3 = text(w3["blocks"][0]) if w3["blocks"] else ""
check("women: Saturday's table has the first 10 only, no D's-players rows, titled Evian Championship", w3["blocks"] and len(re.findall(r"<tr[ >]", w3["blocks"][0].split("<tbody>")[1])) == 10 and "Evian Championship · After round 3" in t3 and 'class="also"' not in w3["blocks"][0], t3[:300])
wf = golf.run({"lpga": with_end(evian, ev_end)}, datetime.fromisoformat(ev_end.replace("Z", "+00:00")) + (utc(2025, 1, 2) - utc(2025, 1, 1)), {})
raw_w = sorted(ev["competitions"][0]["competitors"], key=lambda c: c["order"])
check("women: the final top 10 with the winner (the board's own first) in gold and a Big Stuff line", wf["blocks"] and wf["winners"] and f"1 {raw_w[0]['athlete']['displayName']}" in text(wf["blocks"][0]) and f"2 {raw_w[1]['athlete']['displayName']}" in text(wf["blocks"][0]) and len(re.findall(r"<tr[ >]", wf["blocks"][0].split("<tbody>")[1])) == 10
      and wf["winners"] and wf["winners"][0].startswith(f"Golf: {raw_w[0]['athlete']['displayName']} wins the Evian Championship"), (wf["winners"], text(wf["blocks"][0])[:200]))

# ---- the start note -------------------------------------------------------------------------------------------------
sn = golf.run({"pga": masters}, utc(2025, 4, 7), {})
check("the week before: 'Masters Tournament starts on Thursday 10 April (US time)', once", sn["lines"] == [("Masters Tournament starts on Thursday 10 April (US time)", "golf:start:401703489")] or [t for t, _ in sn["lines"]] == ["Masters Tournament starts on Thursday 10 April (US time)"], sn["lines"])
check("not repeated", golf.run({"pga": masters}, utc(2025, 4, 8), sn["state"])["lines"] == [])
check("three weeks ahead is too early for the start note", golf.run({"pga": masters}, utc(2025, 3, 18), {})["lines"] == [])
check("the women's majors have no start note (D: weekend tables only)", golf.run({"lpga": evian}, utc(2025, 7, 8), {})["lines"] == [])

# ---- odd data -----------------------------------------------------------------------------------------------------------
check("a board with no event of ours, an empty field or junk gives nothing and no error", golf.run({"pga": {"events": []}}, utc(2025, 4, 12), {})["blocks"] == [] and golf.run({"pga": {"events": [{"name": "Masters Tournament"}]}}, utc(2025, 4, 12), {})["blocks"] == [])
check("D's list has the players he named: McIlroy, Woods, DeChambeau, Scheffler, Rahm, Koepka, Schauffele, Morikawa, Fowler, Mickelson, Spieth and Akshay Bhatia", all(n in golf.WATCH for n in ["Rory McIlroy", "Tiger Woods", "Bryson DeChambeau", "Scottie Scheffler", "Jon Rahm", "Brooks Koepka", "Xander Schauffele", "Collin Morikawa", "Rickie Fowler", "Phil Mickelson", "Jordan Spieth", "Akshay Bhatia"]) and len(golf.WATCH) == 12)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
