"""Offline tests for the Wikipedia honours (All-Pro, Pro Bowl, NBA All-Star selections, Coach of the Year) on saved real pages. Run: python3 scripts/test_honours.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import awards, honours  # noqa: E402

FX = ROOT / "tests" / "fixtures"
AP, PB, ASG, COY = [(FX / n).read_text() for n in ("wiki_all_pro_2025.txt", "wiki_pro_bowl_2026.txt", "wiki_nba_asg_2026.txt", "wiki_nba_coy.txt")]
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


check("initial names: first initial and the rest", [honours.initial_name(n) for n in ("Matthew Stafford", "Amon-Ra St. Brown", "Shai Gilgeous-Alexander", "Kenneth Walker III", "Madonna")]
      == ["M. Stafford", "A. St. Brown", "S. Gilgeous-Alexander", "K. Walker III", "Madonna"])
check("link text: plain, piped and none", [honours.link_text(x) for x in ("[[Josh Allen]], x", "[[James Cook (running back)|James Cook]]", "no link")] == ["Josh Allen", "James Cook", None])
tiny = "{|\n|+Cap\n!Head\n|-\n|a||b\n|-\n|style=\"x\"|c\n|}"
check("the table reader: caption, header and cells, inline '||' and attributes", honours.tables(tiny) == [{"caption": "Cap", "rows": [{"head": True, "cells": ["Head"]}, {"head": False, "cells": ["a", "b"]}, {"head": False, "cells": ["c"]}]}], honours.tables(tiny))

# ---- All-Pro (AP teams) ----
ap = honours.all_pro(AP)
first = [n for u in ap["first"].values() for _, n in u]
second = [n for u in ap["second"].values() for _, n in u]
table_text = "\n".join(l for l in AP.split("\n") if l.startswith("|"))     # the table rows only, not the intro prose
tag_lists = [[t.strip() for t in m.split(",")] for m in re.findall(r"\(([^()]*)\)", table_text)]
raw_first, raw_second = sum(1 for t in tag_lists if "AP" in t), sum(1 for t in tag_lists if "AP-2" in t)
check("independent: the AP first team has as many players as the page has entries tagged AP, the second as many as are tagged AP-2", len(first) == raw_first and len(second) == raw_second and raw_first > 25, (len(first), raw_first, len(second), raw_second))
check("the quarterbacks: Matthew Stafford first team, Drake Maye second", ("QB", "Matthew Stafford") in ap["first"]["Offense"] and ("QB", "Drake Maye") in ap["second"]["Offense"])
check("a player picked only by the PFWA (James Cook at running back) is not on the AP first team, but is on the AP second", "James Cook" not in first and "James Cook" in second)
check("all three units are there for the first team", set(ap["first"]) == {"Offense", "Defense", "Special teams"} and all(ap["first"].values()))
check("a page that is not an All-Pro page gives nothing", honours.all_pro(ASG) == {} and honours.all_pro("") == {})

# ---- NBA All-Star selections ----
a = honours.all_stars(ASG)
east_region = ASG[ASG.index("|+Eastern Conference All-Stars"):ASG.index("|+Western Conference All-Stars")]
raw_east = len(re.findall(r'^\|style="text-align:left"\|', east_region, re.M)) // 2
check("independent: the East selections (starters and reserves) are as many as the page's East table has rows", len(a["East"]["starters"]) + len(a["East"]["reserves"]) == raw_east and raw_east >= 12, (len(a["East"]["starters"]) + len(a["East"]["reserves"]), raw_east))
check("the East starters are Giannis Antetokounmpo, Jaylen Brown, Jalen Brunson, Cade Cunningham, Tyrese Maxey, with the game date", [x["name"] for x in a["East"]["starters"]] == ["Giannis Antetokounmpo", "Jaylen Brown", "Jalen Brunson", "Cade Cunningham", "Tyrese Maxey"] and a["date"] == "February 15, 2026", a["East"]["starters"])
check("the page's notes become flags: Giannis (injured) is Out, Brandon Ingram (his co-replacement for Curry) and Alperen Şengün are In, nobody else is flagged", {x["name"]: x["flag"] for c in ("East", "West") for g in ("starters", "reserves") for x in a[c][g] if x["flag"]} == {"Giannis Antetokounmpo": "out", "Brandon Ingram": "in", "Stephen Curry": "out", "Shai Gilgeous-Alexander": "out", "Alperen Şengün": "in", "De'Aaron Fox": "in"}, {x["name"]: x["flag"] for c in ("East", "West") for g in ("starters", "reserves") for x in a[c][g] if x["flag"]})
raw_flags = len(re.findall(r"\{\{ref\|(?:inj|rep)\d", ASG[ASG.index("|+Eastern"):ASG.index("|+USA Stars")]))
check("independent: as many flags as the raw conference tables have INJ and REP notes", sum(1 for c in ("East", "West") for g in ("starters", "reserves") for x in a[c][g] if x["flag"]) == raw_flags, raw_flags)
check("a page without the conference tables gives nothing", honours.all_stars(AP) == {})

# ---- Pro Bowl ----
p = honours.pro_bowl(PB)
check("Pro Bowl: Josh Allen and Drake Maye are AFC selections; Justin Herbert, who declined, and the alternate Joe Burrow are not counted", "Josh Allen" in p["AFC"] and "Drake Maye" in p["AFC"] and "Justin Herbert" not in p["AFC"] and "Joe Burrow" not in p["AFC"], p["AFC"][:8])
check("Pro Bowl: both conferences have a full roster and the date is read", len(p["AFC"]) > 30 and len(p["NFC"]) > 30 and p["date"] == "February 3, 2026", (len(p["AFC"]), len(p["NFC"]), p["date"]))
check("a page without the conference sections gives nothing", honours.pro_bowl(ASG) == {})

# ---- Coach of the Year ----
check("Coach of the Year: the latest row is 2025-26, Joe Mazzulla, Boston Celtics", honours.coach_of_the_year(COY) == {"season": "2025–26", "coach": "Joe Mazzulla", "team": "Boston Celtics"}, honours.coach_of_the_year(COY))
check("a page without the table gives nothing", honours.coach_of_the_year(AP) is None)


# ---- the awards items built from these pages ----
class Wiki:
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def wikitext(self, page):
        self.asked.append(page)
        if page not in self.pages:
            return ""
        return self.pages[page]


nba_w = Wiki({"NBA Coach of the Year Award": COY, "2026 NBA All-Star Game": ASG})
items = awards.wiki_items("nba", 2026, nba_w)
by = {i["key"]: i for i in items}
check("NBA 2026 (the 2025-26 season): the Coach of the Year and the East and West All-Star selections are items; the coach is Joe Mazzulla of the Boston Celtics", set(by) == {"wiki:coy", "wiki:asg:East", "wiki:asg:West"} and by["wiki:coy"]["data"] == {"name": "Joe Mazzulla", "team": "Boston Celtics"}, [i["key"] for i in items])
check("each All-Star row is its own item, titled 'NBA All-Star Selections — East' / '— West', with Starters and Reserves and the game date", by["wiki:asg:East"]["label"] == "NBA All-Star Selections — East" and by["wiki:asg:East"]["kind"] == "asg" and len(by["wiki:asg:East"]["data"]["starters"]) == 5 and by["wiki:asg:West"]["data"]["sub"] == "Game: 15 Feb (US)", by["wiki:asg:East"]["data"])
check("NBA 2027 (the season that starts in October): last season's coach is not this season's, and there is no 2027 All-Star page yet, so no items", awards.wiki_items("nba", 2027, Wiki({"NBA Coach of the Year Award": COY})) == [])
nfl_w = Wiki({"2025 All-Pro Team": AP, "2026 Pro Bowl Games": PB})
nitems = awards.wiki_items("nfl", 2025, nfl_w)
check("NFL 2025: six All-Pro rows (AP first and second team by unit) and the Pro Bowl; the Pro Bowl page asked for is the following year's", len(nitems) == 7 and "2026 Pro Bowl Games" in nfl_w.asked and sum(1 for i in nitems if i["key"].startswith("wiki:ap:")) == 6, [i["key"] for i in nitems])
off = next(i for i in nitems if i["key"] == "wiki:ap:first:Offense")
check("the All-Pro first-team offense is one row per position: QB, RB, FB, Utility (the source's APU), WR 1-3, TE, then LT, LG, C, RG, RT, each with its player, 13 in all", off["label"] == "All-Pro First Team — Offense" and [r_[0] for r_ in off["data"]["rows"]] == ["QB", "RB", "FB", "Utility", "WR 1", "WR 2", "WR 3", "TE", "LT", "LG", "C", "RG", "RT"] and off["data"]["rows"][0] == ("QB", "Matthew Stafford", "LAR"), off["data"]["rows"])
dfn = next(i for i in nitems if i["key"] == "wiki:ap:first:Defense")
check("the defense: EDGE 1-3, DT 1-2, LB 1-2, CB 1-2 with the slot corner as 'Slot CB', S 1-2: exactly the source's twelve, numbered only where a position repeats", [r_[0] for r_ in dfn["data"]["rows"]] == ["EDGE 1", "EDGE 2", "EDGE 3", "DT 1", "DT 2", "LB 1", "LB 2", "CB 1", "CB 2", "Slot CB", "S 1", "S 2"], [r_[0] for r_ in dfn["data"]["rows"]])
st_ = next(i for i in nitems if i["key"] == "wiki:ap:first:Special teams")
check("special teams: K, P, KR, PR, ST, LS (each once, so no numbers)", [r_[0] for r_ in st_["data"]["rows"]] == ["K", "P", "KR", "PR", "ST", "LS"], st_["data"]["rows"])


class Boom:
    def wikitext(self, page):
        raise OSError("down")


check("Wikipedia down: no items and no error", awards.wiki_items("nba", 2026, Boom()) == [] and awards.wiki_items("nfl", 2025, Boom()) == [])

# ---- replacements: the table says who came in and who went out ----
asg_before = awards.wiki_items("nba", 2026, Wiki({"2026 NBA All-Star Game": ASG}))
st, _ = awards.update({}, 2026, asg_before)
cut = ASG.index("|+Western Conference All-Stars")
swapped = ASG[:cut] + ASG[cut:].replace("[[Kevin Durant]]", "[[Zion Williamson]]", 1)
asg_after = awards.wiki_items("nba", 2026, Wiki({"2026 NBA All-Star Game": swapped}))
st2, new = awards.update(st, 2026, asg_after)
check("a changed page (Durant replaced): only the West row comes back, on top, with no wordy note (the In/Out flags are in the table)", [n["key"] for n in new] == ["wiki:asg:West"] and new[0]["note"] == "" and st2["rows"][0]["key"] == "wiki:asg:West", new)
check("independent: the West list has Zion Williamson and not Kevin Durant now", "Zion Williamson" in new[0]["text"] and "Kevin Durant" not in new[0]["text"])
st3, new3 = awards.update(st2, 2026, asg_after)
check("the same page again: no news", new3 == [])

# ---- which season ----
import datetime as dt  # noqa: E402
S = awards.season_of
check("season_of: NBA 2026-27 is 2027 from August 2026 (and 2026 until July); NFL 2025 until March 2026; MLB 2026 until March 2027",
      S("nba", dt.date(2026, 11, 4)) == 2027 and S("nba", dt.date(2027, 4, 20)) == 2027 and S("nba", dt.date(2026, 7, 31)) == 2026
      and S("nfl", dt.date(2026, 11, 4)) == 2026 and S("nfl", dt.date(2027, 1, 20)) == 2026 and S("nfl", dt.date(2027, 3, 1)) == 2027
      and S("mlb", dt.date(2026, 11, 4)) == 2026 and S("mlb", dt.date(2027, 2, 1)) == 2026 and S("mlb", dt.date(2027, 3, 5)) == 2027)

raw_clubs = {m.group(1) for m in re.finditer(r"\[\[\d{4} ([^\]|]+?) season\|", table_text)}
allp = honours.all_pro(AP)
every = {n for k in ("first", "second") for u in allp[k].values() for _, n in u}
check("independent: every club the page links to has a code, so every All-Pro player (60) gets his team's code, none guessed", raw_clubs <= set(awards.NFL_CODES) and all(awards.NFL_CODES.get(allp["teams"].get(n)) for n in every) and len(every) == 60, (raw_clubs - set(awards.NFL_CODES), len(every)))
check("a few real teams: Stafford LAR, Robinson ATL, McCaffrey SF, Chase CIN, Garrett CLE, Sewell DET", [awards.NFL_CODES[allp["teams"][n]] for n in ("Matthew Stafford", "Bijan Robinson", "Christian McCaffrey", "Ja\u2019Marr Chase", "Myles Garrett", "Penei Sewell")] == ["LAR", "ATL", "SF", "CIN", "CLE", "DET"])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
