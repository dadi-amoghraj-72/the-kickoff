"""Offline tests for Grand Slam tennis, on saved real ESPN data (the 2026 Australian Open and Roland-Garros).
Run: python3 scripts/test_tennis.py"""
import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import tennis  # noqa: E402
from kickoff.sources import espn_tennis  # noqa: E402

FX = ROOT / "tests" / "fixtures"
AO = json.loads((FX / "espn_tennis_ao.json").read_text())["events"][0]
RG = json.loads((FX / "espn_tennis_rg.json").read_text())["events"][0]
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def notes_of(event):
    return {c["id"]: c["notes"][0]["text"] for g in event["groupings"] for c in g["competitions"] if c.get("notes")}


MS = {"ao": tennis.matches_of(AO), "rg": tennis.matches_of(RG)}

# ---- Reading the real data ----
for key in ("ao", "rg"):
    ms = MS[key]
    per = {s: sum(1 for m in ms if m["stage"] == s) for s in tennis.ORDER}
    check(f"{key}: every singles round has the right number of finished matches (128, 64, 32, 16, 8, 4, 2 across both draws)",
          per == {"R1": 128, "R2": 64, "R3": 32, "R4": 16, "QF": 8, "SF": 4, "F": 2}, per)
    check(f"{key}: no qualifying match and no doubles match is read", all(m["stage"] in tennis.ORDER and m["draw"] in tennis.DRAW for m in ms))

# Independent cross-check: the score rebuilt from the set data must equal the score ESPN writes in its notes line
bad, seedmap = [], {}
for key, ev in (("ao", AO), ("rg", RG)):
    notes = notes_of(ev)
    for m in MS[key]:
        tail = re.sub(r"^.*?\([A-Z]{2,3}\)\s+bt\s+(?:\(\d+\)\s+)?.+?\s+\([A-Z]{2,3}\)", "", notes[m["id"]]).strip()
        tail = re.sub(r"\((\d+)-(\d+)\)", lambda k: f"({min(int(k.group(1)), int(k.group(2)))})", tail)  # (7-3) -> (3): the loser's points
        tail = re.sub(r"\s+\(", "(", tail)
        tail = re.sub(r"\s*0-0 ret", " ret", tail).strip()   # ESPN writes a set that never started as 0-0
        if (tail or "w/o") != (tennis.score(m).replace(" ret.", " ret")) and not (tail == "w/o" and tennis.score(m) == "w/o"):
            bad.append((tail, tennis.score(m)))
        if m["winner"]["name"].split()[-1] not in notes[m["id"]].split(" bt ")[0]:
            bad.append(("winner", m["id"]))
        for p in (m["winner"], m["loser"]):
            if p["seed"] is not None:
                seedmap.setdefault((key, m["draw"], p["seed"]), set()).add(p["id"])
check("every score rebuilt from the set data equals the score in ESPN's own notes line (all 508 matches)", not bad, bad[:4])
check("each seed number belongs to one player only, in every draw (no seed read from the wrong place)", all(len(v) == 1 for v in seedmap.values()) and len(seedmap) >= 62, len(seedmap))
check("seeds run 1 to 32 in both draws", {s for (_, d, s) in seedmap if d == "mens-singles"} <= set(range(1, 33)) and {s for (_, d, s) in seedmap if d == "womens-singles"} <= set(range(1, 33)))
finals = {(k, m["draw"]): m for k in MS for m in MS[k] if m["stage"] == "F"}
f = finals[("ao", "mens-singles")]
check("the 2026 Australian Open men's final: (1) Alcaraz beat (4) Djokovic 2-6 6-2 6-3 7-5", tennis.name(f["winner"]) == "(1) C. Alcaraz" and tennis.name(f["loser"]) == "(4) N. Djokovic" and tennis.score(f) == "2-6 6-2 6-3 7-5", (tennis.name(f["winner"]), tennis.score(f)))
f = finals[("rg", "mens-singles")]
check("a tie-break shows the loser's points: the Roland-Garros men's final had 6-7(5)", "6-7(5)" in tennis.score(f), tennis.score(f))
f = finals[("rg", "womens-singles")]
check("an unseeded finalist has no seed number", f["loser"]["seed"] is None and tennis.name(f["loser"]) == f["loser"]["short"], tennis.name(f["loser"]))
ret = next(m for m in MS["ao"] if m["status"] == "retired" and m["stage"] == "R1" and m["loser"]["seed"] == 7)
check("a retirement says so, and the set that never started is not shown (3-6 6-4 6-4 ret.)", tennis.score(ret) == "3-6 6-4 6-4 ret." and ret["loser"]["seed"] == 7, tennis.score(ret))
wo = next(m for m in MS["ao"] if m["status"] == "walkover")
check("a walkover has no score and is marked w/o", tennis.score(wo) == "w/o" and wo["sets"] == [], tennis.score(wo))
check("stage_reached: the finished Slam reached the final; an event with only first-round matches started reached R1",
      tennis.stage_reached(AO) == "F" and tennis.stage_reached({"groupings": [{"grouping": {"slug": "mens-singles"}, "competitions": [c for c in AO["groupings"][0]["competitions"] if c["round"]["displayName"] == "Round 1"]}]}) == "R1")

# ---- Which matches are shown ----
for key in ("ao", "rg"):
    ms = MS[key]
    early = [m for m in ms if m["stage"] in ("R1", "R2", "R3")]
    late = [m for m in ms if m["stage"] not in ("R1", "R2", "R3")]
    check(f"{key}: rounds 1-3 show exactly the matches with a seeded player; the last 16 onwards show all {len(late)}",
          sorted(m["id"] for m in ms if tennis.shown(m)) == sorted(m["id"] for m in [m for m in early if m["winner"]["seed"] or m["loser"]["seed"]] + late), (len(early), len(late)))
    check(f"{key}: a round-1 to 3 match between two unseeded players is hidden", any(not tennis.shown(m) for m in early))
NOW_END = utc(2026, 2, 1, 12, 0)
shown_all = tennis.pick(MS["ao"], NOW_END, [])
check("only matches started within the last 3 days are picked (the final days of the tournament)", shown_all and all(NOW_END - m["date"] <= timedelta(days=3) for m in shown_all) and {m["stage"] for m in shown_all} <= {"R4", "QF", "SF", "F"}, {m["stage"] for m in shown_all})
ear = tennis.pick(MS["ao"], utc(2026, 1, 19, 12, 0), [])
all_r1 = [m for m in MS["ao"] if m["stage"] == "R1" and tennis.shown(m)]
check("matches that have not started yet are never picked: at noon (UTC) on the second day only first-round matches played so far, not all of them", ear and {m["stage"] for m in ear} == {"R1"} and len(ear) < len(all_r1)
      and all(m["date"] <= utc(2026, 1, 19, 12, 0) for m in ear), (len(ear), len(all_r1)))
check("reported matches are not picked again", tennis.pick(MS["ao"], NOW_END, [m["id"] for m in shown_all]) == [])
check("ordering: the final first, then semi-finals; best seed first inside a round", [m["stage"] for m in shown_all][:2] == ["F", "F"] and [m["stage"] for m in shown_all] == sorted([m["stage"] for m in shown_all], key=lambda s: -tennis.ORDER.index(s)))

# ---- Standouts, each checked a second way ----
every = [m for k in MS for m in MS[k]]
indep = sorted(m["id"] for k, ev in (("ao", AO), ("rg", RG)) for m in MS[k] if (lambda n: n and n.group(2) and int(n.group(2)) <= 10)(re.match(r"^(?:\((\d+)\)\s+)?.+?\s+\([A-Z]{2,3}\)\s+bt\s+(?:\((\d+)\)\s+)?", notes_of(ev)[m["id"]])))
check("top-10 seeds out: the matches picked (loser seed 1 to 10) are the same ones found by reading ESPN's notes a second way", sorted(m["id"] for m in every if m["loser"]["seed"] and m["loser"]["seed"] <= 10) == indep, len(indep))
line = tennis.seeds_out([next(m for m in every if m["loser"]["seed"] == 1 and m["status"] == "final")])[0]
check("a top-seed-out line names the seed, who beat him, the round and the score", line.startswith("Top Seed Out: (1) ") and " beaten by " in line and " in the " in line and line.endswith("."), line)
check("a seed 11 or lower going out is not a standout", tennis.seeds_out([m for m in every if m["loser"]["seed"] and m["loser"]["seed"] > 10]) == [])
retline = tennis.seeds_out([ret])[0]
check("a retirement line says retired against, with the score and ret.", "retired against" in retline and "3-6 6-4 6-4 ret." in retline, retline)
fixed = tennis.seeds_out([{**wo, "loser": {**wo["loser"], "seed": 4}}])[0]
check("a walkover line has no score and ends with the round", "withdrew before facing" in fixed and "w/o" not in fixed and fixed.endswith("round."), fixed)


def by_notes(ev, key):
    """Comebacks found from the notes text alone: the winner's games are listed first, so he lost sets 1 and 2 and won 3 sets of 5."""
    out = []
    for m in MS[key]:
        text = notes_of(ev)[m["id"]]
        sets = re.findall(r"(\d+)-(\d+)", re.sub(r"\(\d+-\d+\)", "", re.split(r"\([A-Z]{2,3}\)", text)[-1]))
        if m["draw"] == "mens-singles" and "ret" not in text and len(sets) == 5 and int(sets[0][0]) < int(sets[0][1]) and int(sets[1][0]) < int(sets[1][1]) \
                and sum(int(a) > int(b) for a, b in sets) == 3:
            out.append(m["id"])
    return out


for key, ev in (("ao", AO), ("rg", RG)):
    mine = sorted(m["id"] for m in MS[key] if tennis.comebacks([m]))
    check(f"{key}: comebacks from two sets down (men, best of five) equal those found a second way from the notes text ({len(mine)})", mine == sorted(by_notes(ev, key)), (mine, by_notes(ev, key)))
check("a comeback line says who came back from two sets down against whom, and the round", all("came back from two sets down to beat" in c for k in MS for c in tennis.comebacks(MS[k])))
three_set = [m for m in MS["ao"] if m["draw"] == "womens-singles"]
check("women play best of three, so a women's match is never a two-sets-down comeback", tennis.comebacks(three_set) == [])
ms_ret = copy.deepcopy(next(m for m in MS["ao"] if tennis.comebacks([m])))
ms_ret["status"] = "retired"
check("a match that ends in a retirement is not a comeback", tennis.comebacks([ms_ret]) == [])

champs = tennis.milestones([m for m in MS["ao"] if m["stage"] == "F"], AO)
check("the Australian Open final gives a title line for each draw", len([c for c in champs if "title" in c]) == 2 and any("Alcaraz wins the Australian Open men's singles title, beating" in c.replace("Carlos ", "") or "Carlos Alcaraz wins the Australian Open men's singles title, beating Novak Djokovic" in c for c in champs), champs)
synth = {"id": "x", "stage": "R4", "status": "final", "draw": "mens-singles", "winner": {"name": "Q Player", "qualifier": True, "seed": None}, "loser": {"name": "Other", "qualifier": False, "seed": 3}, "sets": []}
champs_by_draw = {p["displayName"]: p["type"]["slug"] for p in AO["previousWinners"] if p["type"]["slug"] in tennis.DRAW}
expected = [m for m in MS["ao"] if champs_by_draw.get(m["loser"]["name"]) == m["draw"]]
dc = [c for c in tennis.milestones(MS["ao"], AO) if "defending champion" in c]
check("defending champions are named when they lose in their own draw (from the event's previous winners)", len(dc) == len(expected) and all(c.startswith("Milestone: defending champion ") for c in dc), (dc, len(expected)))
dsynth = {"name": "US Open", "previousWinners": [{"displayName": "Old Champ", "type": {"slug": "mens-singles"}}]}
lost_champ = {**synth, "stage": "R3", "loser": {"name": "Old Champ", "qualifier": False, "seed": 2}, "winner": {"name": "W", "qualifier": False, "seed": None}}
check("exact wording, and a women's champion losing in the men's draw name is not matched", tennis.milestones([lost_champ], dsynth) == ["Milestone: defending champion Old Champ is out in the third round."]
      and tennis.milestones([{**lost_champ, "draw": "womens-singles"}], dsynth) == [])
q = [m for m in MS["ao"] if m["winner"]["qualifier"]]
check("qualifiers are the players who won a qualifying final", len(q) > 0 and all(m["stage"] in tennis.ORDER for m in q))
qline = tennis.milestones([m for m in MS["ao"] if m["winner"]["qualifier"] and m["stage"] in tennis.REACHES], AO)
check("a qualifier winning round 4, the quarter-finals or the semi-finals is reported as reaching the next stage", all(c.startswith("Milestone: qualifier ") and "reaches the " in c for c in qline if "qualifier" in c))
check("exact wording for a qualifier into the last eight", tennis.milestones([synth], {"name": "US Open", "previousWinners": []}) == ["Milestone: qualifier Q Player reaches the quarter-finals."], tennis.milestones([synth], {"name": "US Open", "previousWinners": []}))
check("no milestone for a qualifier winning in round 1", tennis.milestones([{**synth, "stage": "R1"}], {"name": "US Open", "previousWinners": []}) == [])

# ---- The page ----
sample = [m for m in tennis.pick(MS["rg"], utc(2026, 6, 9, 0, 0), []) if m["stage"] == "F"]
html = tennis.event_html(RG, sample)
check("a table per round and draw with the title as a centred header row, two rows per match", html.count('<th class="tt"') == 2 and html.count('<tr class="w">') == 2 and html.count('<tr class="l">') == 2 and "Men&#x27;s Singles · Final" in html and "Women&#x27;s Singles · Final" in html, html[:300])
men, women = html.split('<div class="tennis">')[1:]
check("men's tables have 5 set columns, women's 3", men.count("<col ") == 6 and women.count("<col ") == 4, (men.count("<col "), women.count("<col ")))
check("the tie-break points sit small on the loser's side of that set only (the 6-7(5) set: 6 over 7 with a small 5 beside the 6)", "6<sup>5</sup>" in men and men.count("<sup>") == 1, men)
check("winner rows are marked for bold, with the seed in brackets", '<tr class="w"><td class="pl">(2) A. Zverev</td>' in men, men[:400])
chk = tennis.stage_table("mens-singles", "R1", [ret, wo])
check("a retirement and a walkover are tagged on the loser's row, in the first empty set cell (a walkover has all five empty)", chk.count('<td class="tag">ret.</td><td class="s"></td></tr>') == 1 and chk.count('<td class="tag">w/o</td>' + '<td class="s"></td>' * 4 + '</tr>') == 1, chk)
full = {**ret, "status": "retired", "sets": [{"w": 6, "l": 4, "tb": None, "won": True}] * 5}
check("a retirement in a full five-set match has no empty cell, so the tag goes after the name", '<span class="muted">ret.</span>' in tennis.stage_table("mens-singles", "R1", [full]) and 'class="tag"' not in tennis.stage_table("mens-singles", "R1", [full]))
evil = {**sample[0], "winner": {**sample[0]["winner"], "short": "<script>alert(1)</script>"}}
check("player names are escaped", "<script>" not in tennis.stage_table("mens-singles", "F", [evil]) and "&lt;script&gt;" in tennis.stage_table("mens-singles", "F", [evil]))
check("the standouts list has bold labels", '<strong>Top Seed Out:</strong>' in tennis._list(["Top Seed Out: x."]) and '<strong>Withdrawal:</strong>' in tennis._list(["Withdrawal: y (BBC Sport)"]))


# ---- Round progress in the title ----
for key in ("ao", "rg"):
    done = tennis.progress_of(MS[key])
    check(f"{key}: in the finished Slam every round of both draws is complete, so the fixed draw sizes (64, 32, 16, 8, 4, 2, 1) match the real data",
          all(done.get((d, st)) == n for d in tennis.DRAW for st, n in tennis.PER_DRAW.items()), done)
NOWP = utc(2026, 1, 27, 6, 0)
raw_done = {}
for g in AO["groupings"]:
    for c in g["competitions"]:
        st = tennis.STAGES.get(c["round"]["displayName"])
        if st and c["status"]["type"]["name"] in tennis.COMPLETED and tennis.utc(c["date"]) <= NOWP:
            raw_done[(g["grouping"]["slug"], st)] = raw_done.get((g["grouping"]["slug"], st), 0) + 1
check("progress at a chosen time equals a count made straight from the raw ESPN data (matches started by then)", tennis.progress_of(MS["ao"], NOWP) == raw_done and 0 < raw_done[("mens-singles", "QF")] < 4, (tennis.progress_of(MS["ao"], NOWP), raw_done))
check("progress text: played while the round is going, complete when all are done", tennis.progress_text("QF", 3) == "3/4 played" and tennis.progress_text("R4", 8) == "8/8 complete" and tennis.progress_text("F", 1) == "1/1 complete")


# ---- The whole block, with a fake source ----
class FakeSource:
    def __init__(self, events=None, broken=False, tops=None):
        self.events, self.broken, self.calls, self.tops = events if events is not None else [AO], broken, 0, tops or {}

    def slam_events(self, now):
        self.calls += 1
        if self.broken:
            raise RuntimeError("down")
        return copy.deepcopy(self.events)

    def top10(self, tour):
        self.calls += 1
        return self.tops[tour]


out = tennis.run(NOW_END, {}, FakeSource())
check("run: the finished Slam's last days appear: heading, tables, standouts", "<h3>Australian Open</h3>" in out["html"] and "Final<span class=\"prog\">1/1 complete</span></th>" in out["html"] and "Milestone:" in out["html"] and out["stats"]["shown"] == len(shown_all), out["stats"])
check("run: it reports the Slam's stage and that it is a major event (quarter-finals or later)", out["slams"] == [{"name": "Australian Open", "stage": "F", "major": True}], out["slams"])
check("run: shown matches are remembered, and the next run shows nothing new", len(out["state"]["reported"]) == len(shown_all) and tennis.run(NOW_END, out["state"], FakeSource())["html"] == "")
early = tennis.run(utc(2026, 1, 19, 12, 0), {}, FakeSource())
check("run: on the second day it shows seeded first-round matches only, and the Slam is not yet a major event", early["slams"][0]["stage"] == "R1" and early["slams"][0]["major"] is False and early["stats"]["shown"] > 0
      and "Quarter-finals" not in early["html"] and "First Round" in early["html"], early["slams"])
qual = tennis.run(utc(2026, 1, 14, 12, 0), {}, FakeSource())
check("run: during qualifying week the Slam is running but has no main-draw stage and nothing is shown", qual["slams"] == [{"name": "Australian Open", "stage": None, "major": False}] and qual["html"] == "", qual["slams"])
mid = tennis.run(utc(2026, 1, 21, 12, 0), {}, FakeSource())
second = tennis.run(utc(2026, 1, 23, 12, 0), mid["state"], FakeSource())
check("run: day by day, a later edition shows only matches not shown before", set(mid["state"]["reported"]).isdisjoint(set(second["state"]["reported"]) - set(mid["state"]["reported"])) and second["stats"]["shown"] > 0 and len(second["state"]["reported"]) == len(mid["state"]["reported"]) + second["stats"]["shown"], (mid["stats"], second["stats"]))
down = tennis.run(NOW_END, {"reported": ["keep"]}, FakeSource(broken=True))
check("run: a broken source leaves tennis out, says so, and keeps the state", down["html"] == "" and down["stats"]["failed"] == 1 and down["state"]["reported"] == ["keep"] and down["slams"] == [])
prog = tennis.run(NOWP, {}, FakeSource())
qf_done = raw_done[("mens-singles", "QF")]
check("run: the page titles carry each round's progress, from the same count (the quarter-finals still being played, the last 16 complete)",
      f'Men&#x27;s Singles · Quarter-finals<span class="prog">{qf_done}/4 played</span>' in prog["html"] and 'Fourth Round<span class="prog">8/8 complete</span>' in prog["html"], re.findall(r'colspan="\d">([^<]*)<', prog["html"]))
check("run: no Slam running gives nothing", tennis.run(NOW_END, {}, FakeSource(events=[]))["html"] == "")

# ---- Withdrawals ----
NOW = utc(2026, 1, 5, 12, 0)
item = lambda title, text="", hrs=2, link=None, src="BBC Sport": {"source": src, "title": title, "text": text, "link": link or f"https://x/{title}", "published": NOW - timedelta(hours=hrs)}  # noqa: E731
TOP = lambda: ["Jannik Sinner", "Alexander Zverev", "Carlos Alcaraz"]  # noqa: E731
calls = []
w = tennis.withdrawals([item("Sinner withdraws from Australian Open with injury"), item("Zverev knocked out of Australian Open"), item("Sinner wins Brisbane title"),
                        item("Unknown withdraws from Australian Open"), item("Alcaraz pulls out of US Open", hrs=60), item("Zverev to miss Wimbledon", hrs=5)], NOW, lambda: calls.append(1) or TOP())
check("withdrawals: a top-10 player's Slam withdrawal headline is reported as written, with its source", [t for t, _ in w] == ["Withdrawal: Sinner withdraws from Australian Open with injury (BBC Sport)", "Withdrawal: Zverev to miss Wimbledon (BBC Sport)"], w)
check("withdrawals: being knocked out, a title, an unknown player and a story older than 36 hours are not withdrawals", len(w) == 2)
calls2 = []
tennis.withdrawals([item("Sinner wins Brisbane title")], NOW, lambda: calls2.append(1) or TOP())
check("withdrawals: the rankings are fetched once for the whole batch, and not at all when no headline looks like a withdrawal", len(calls) == 1 and calls2 == [], (calls, calls2))
check("withdrawals: a story already shown is skipped", tennis.withdrawals([item("Sinner withdraws from Australian Open", link="L1")], NOW, TOP, seen=["L1"]) == [])
fs = FakeSource(events=[], tops={"atp": ["Jannik Sinner"], "wta": ["Aryna Sabalenka"]})
wd = tennis.run(NOW, {}, fs, fetch_news=lambda: [item("Sabalenka withdraws from Australian Open")])
check("run: withdrawals get their own heading and bold label, and are remembered so they are not repeated", "<h3>Grand Slam withdrawals</h3>" in wd["html"] and "<strong>Withdrawal:</strong>" in wd["html"] and wd["stats"]["withdrawals"] == 1
      and tennis.run(NOW, wd["state"], fs, fetch_news=lambda: [item("Sabalenka withdraws from Australian Open")])["html"] == "", wd["html"])
check("run: if the news fails the matches still show", tennis.run(NOW_END, {}, FakeSource(), fetch_news=lambda: 1 / 0)["stats"]["failed"] == 1 and tennis.run(NOW_END, {}, FakeSource(), fetch_news=lambda: 1 / 0)["stats"]["shown"] > 0)

# ---- The source ----
CALLS = []


def fake_get(url):
    CALLS.append(url)
    day = re.search(r"dates=(\d{8})", url).group(1) if "dates=" in url else ""
    if "/atp/scoreboard" in url:
        return {"events": [copy.deepcopy(AO)] if day in ("20260201", "20260202") else [{"id": "9", "name": "Dubai Duty Free Tennis Championships", "major": False, "groupings": []}]}
    if "/wta/scoreboard" in url:
        return {"events": [copy.deepcopy(AO)]}
    if "rankings" in url:
        return {"rankings": [{"ranks": [{"athlete": {"displayName": f"P{i}"}} for i in range(1, 30)]}]}
    raise AssertionError(url)


src = espn_tennis.Source(fake_get)
ev = src.slam_events(utc(2026, 2, 2, 8, 0))
check("source: asks for yesterday and today (UTC) and returns each Slam once, with both draws, without touching the women's endpoint", len(ev) == 1 and ev[0]["name"] == "Australian Open" and src.calls == 2 and all("/atp/" in u for u in CALLS), (len(ev), CALLS))
check("source: a non-major tournament is ignored", espn_tennis.Source(fake_get).slam_events(utc(2026, 3, 1)) == [])
half = copy.deepcopy(AO)
half["groupings"] = [g for g in half["groupings"] if g["grouping"]["slug"] == "mens-singles"]
CALLS.clear()
merged = espn_tennis.Source(lambda u: {"events": [copy.deepcopy(half)]} if "/atp/" in u else {"events": [copy.deepcopy(AO)]}).slam_events(utc(2026, 2, 2, 8, 0))
check("source: if the men's endpoint lacks the women's draw, the women's endpoint fills it in", len(merged) == 1 and {g["grouping"]["slug"] for g in merged[0]["groupings"]} >= {"mens-singles", "womens-singles"}, [g["grouping"]["slug"] for g in merged[0]["groupings"]])
check("source: top 10 returns ten names", espn_tennis.Source(fake_get).top10("atp") == [f"P{i}" for i in range(1, 11)])
check("tennis needs no Claude: neither module imports anthropic", "anthropic" not in (ROOT / "kickoff" / "tennis.py").read_text() and "anthropic" not in (ROOT / "kickoff" / "sources" / "espn_tennis.py").read_text())

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
