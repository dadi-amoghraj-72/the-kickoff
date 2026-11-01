"""Offline tests for injuries and returns. Run: python3 scripts/test_injuries.py"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kickoff import injuries as inj  # noqa: E402

TODAY = date(2026, 11, 2)
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


def P(pid, name="Some Player", team="ARS", status="a", news="", added=None, chance=None, minutes=700, starts=8, played=9, pos=1):
    return {"id": pid, "name": name, "web_name": name.split()[-1], "team": team, "team_name": team, "team_position": pos,
            "team_played": played, "status": status, "news": news, "news_added": added, "chance_next": chance,
            "minutes": minutes, "starts": starts}


# ---- Games played come from finished fixtures (the teams list says 0) ----
from kickoff.sources import fpl  # noqa: E402
fx = [{"finished": True, "team_h": 1, "team_a": 2}, {"finished": True, "team_h": 2, "team_a": 3}, {"finished": False, "team_h": 1, "team_a": 3}]
check("games played are counted from finished fixtures only", fpl.games_played(fx) == {1: 1, 2: 2, 3: 1}, fpl.games_played(fx))
boot = {"teams": [{"id": 1, "short_name": "AAA", "name": "A", "position": 3, "played": 0}],
        "elements": [{"id": 5, "first_name": "Al", "second_name": "Bee", "web_name": "Bee", "team": 1, "status": "a", "news": "", "news_added": None,
                      "chance_of_playing_next_round": None, "minutes": 600, "starts": 7}]}
check("players carry their team's games played from the fixtures", fpl.players(boot, [{"finished": True, "team_h": 1, "team_a": 9}])[0]["team_played"] == 1)

# ---- Who is a key player ----
check("700 minutes in 9 games (78 a game) is a key player", inj.is_key(P(1)))
check("596 minutes but 7 starts in 9 games (a regular who missed time) is key", inj.is_key(P(1, minutes=596, starts=7)))
check("a squad player is not key", not inj.is_key(P(1, minutes=300, starts=3)))
check("a regular at a side outside the top six is not key", not inj.is_key(P(1, team="BRE", pos=12)))
check("a regular at a big-six club is key even if the club is 9th", inj.is_key(P(1, team="MUN", pos=9)))
check("a team that has played nothing has no key players", not inj.is_key(P(1, played=0)))

# ---- Return dates ----
d = lambda news, added: inj.return_date(P(1, news=news, added=added))  # noqa: E731
check("'Expected back 15 Nov' is read as a date", d("Hamstring injury - Expected back 15 Nov", "2026-10-20T10:00:00Z") == date(2026, 11, 15))
check("'Suspended until 29 Nov' is read as a date", d("Suspended until 29 Nov", "2026-10-27T10:00:00Z") == date(2026, 11, 29))
check("a date in January after a December note rolls into next year", d("Expected back 5 Jan", "2026-12-20T10:00:00Z") == date(2027, 1, 5))
check("'Unknown return date' gives None", d("Thigh injury - Unknown return date", "2026-10-21T10:00:00Z") is None)

# ---- What is worth reporting ----
out = lambda **k: inj.reportable_out(P(1, **k), TODAY)  # noqa: E731
check("injured with no return date is reported", out(status="i", news="Thigh injury - Unknown return date", added="2026-10-21T10:00:00Z"))
check("injured and out 20 more days is reported", out(status="i", news="Knee - Expected back 22 Nov", added="2026-10-30T10:00:00Z"))
check("injured but back in 5 days is not", not out(status="i", news="Knock - Expected back 7 Nov", added="2026-10-30T10:00:00Z"))
check("a suspension is reported whatever its length", out(status="s", news="Suspended until 8 Nov", added="2026-11-01T10:00:00Z"))
check("doubtful players are not 'out'", not out(status="d", chance=25))
check("doubtful at 25% and 50% is reported, at 75% or unknown is not",
      inj.reportable_doubt(P(1, status="d", chance=25)) and inj.reportable_doubt(P(1, status="d", chance=50))
      and not inj.reportable_doubt(P(1, status="d", chance=75)) and not inj.reportable_doubt(P(1, status="d", chance=None)))

# ---- Once, not daily ----
saka = lambda **k: P(7, "Bukayo Saka", status="i", news="Thigh injury - Unknown return date", added="2026-10-31T10:00:00Z", **k)  # noqa: E731
items, mem = inj.detect([saka()], {}, TODAY)
check("first run: news from the last week is shown", [(i["name"], i["kind"]) for i in items] == [("Bukayo Saka", "out")], items)
old = P(8, "Old Injury", status="i", news="Back injury - Unknown return date", added="2026-07-23T10:00:00Z")
items, mem2 = inj.detect([old], {}, TODAY)
check("first run: older news is remembered but not shown", items == [] and "8" in mem2 and mem2["8"]["reported"] is False, (items, mem2))
items, mem = inj.detect([saka()], {}, TODAY)
items2, mem_b = inj.detect([saka()], mem, date(2026, 11, 3))
check("the next morning the same injury is not repeated", items2 == [] and mem_b["7"]["reported"] is True, items2)
items3, _ = inj.detect([saka()], mem_b, date(2026, 11, 10))
check("nor a week later", items3 == [])
new_inj = P(9, "New Hurt", team="MCI", status="i", news="Calf - Unknown return date", added="2026-11-02T08:00:00Z")
items4, mem_c = inj.detect([saka(), new_inj], mem_b, date(2026, 11, 3))
check("a new injury on a later day is shown, once", [i["name"] for i in items4] == ["New Hurt"], items4)
back = P(7, "Bukayo Saka", status="a", news="", added="2026-11-20T10:00:00Z")
items5, mem_d = inj.detect([back, new_inj], mem_c, date(2026, 11, 21))
check("when a reported player is fit again, his return is shown", [(i["name"], i["kind"]) for i in items5] == [("Bukayo Saka", "returning")], items5)
items6, _ = inj.detect([back, new_inj], mem_d, date(2026, 11, 22))
check("and the return is shown once", items6 == [])
quiet = P(10, "Brief Knock", status="i", news="Knock - Expected back 5 Nov", added="2026-11-01T10:00:00Z")
_, mem_e = inj.detect([quiet], mem_c, date(2026, 11, 2))
items7, _ = inj.detect([P(10, "Brief Knock")], mem_e, date(2026, 11, 6))
check("a short knock is never shown, and neither is his return", items7 == [], items7)
bench = P(11, "Squad Man", status="i", news="Ankle - Unknown return date", added="2026-11-02T08:00:00Z", minutes=100, starts=1)
check("injured squad players are ignored", inj.detect([bench], mem_c, TODAY)[0] == [])
gone = P(12, "Departed", status="u", news="Has joined Al Hilal permanently", added="2026-09-04T10:00:00Z")
check("'unavailable' (players who left) is ignored", inj.detect([gone], mem_c, TODAY)[0] == [])
doubt = P(13, "In Doubt", team="LIV", status="d", news="Illness - 50% chance of playing", added="2026-11-02T08:00:00Z", chance=50)
items8, mem_f = inj.detect([doubt], mem_c, date(2026, 11, 2))
check("a 50% doubt is shown as a doubt", [(i["kind"], i["chance"]) for i in items8] == [("doubt", 50)], items8)
items9, _ = inj.detect([P(13, "In Doubt", team="LIV")], mem_f, date(2026, 11, 3))
check("a doubt who then recovers is shown as back", [i["kind"] for i in items9] == ["returning"], items9)

# ---- The block ----
shown = [{"kind": "returning", "name": "Back <b>", "team": "ARS", "team_name": "Arsenal", "detail": "", "back": None, "chance": None, "minutes": 1},
         {"kind": "doubt", "name": "D", "team": "LIV", "team_name": "Liverpool", "detail": "Illness", "back": None, "chance": 50, "minutes": 1},
         {"kind": "out", "name": "O", "team": "MCI", "team_name": "Manchester City", "detail": "Calf - Unknown return date", "back": None, "chance": None, "minutes": 1},
         {"kind": "suspended", "name": "S", "team": "AVL", "team_name": "Aston Villa", "detail": "Suspended until 21 Nov", "back": None, "chance": None, "minutes": 1}]
h = inj.html(shown)
check("block order: out, suspended, doubt, then returns", h.index(">O<") < h.index(">S<") < h.index(">D<") < h.index("Back &lt;b&gt;"))
check("block escapes text and names its source", "&lt;b&gt;" in h and "<b>" not in h and "official player status" in h)
check("a doubt shows its chance", "(50% chance of playing)" in h)
check("Arsenal's items can be left out of the football block (they go in the Arsenal section)", "Back" not in inj.html(shown, exclude_team="ARS"))
check("nothing to show, no block", inj.html([]) == "" and inj.html(shown[:1], exclude_team="ARS") == "")

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
