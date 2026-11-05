"""Tests for badminton (D's rules, 2026-11-05 as revised after he saw the demo): reading a Wikipedia draw page, official round names, who counts (India, Southeast Asia, the top three singles seeds),
the one-line start notice, early-round matches grouped by discipline in one standard 'winner def. loser' form, tables from the semi-finals, and showing each match once. Real 2025 pages: All England Open,
China Open, World Tour Finals. Run: .venv/bin/python scripts/test_badminton.py"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import badminton as bd  # noqa: E402

FX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


rd = lambda n: (FX / f"majors_{n}.txt").read_text()  # noqa: E731
AE, CO, WTF = rd("all_england_2025"), rd("china_open_2025"), rd("wtf_2025")
text = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.replace("<br>", " / "))).replace("&#x27;", "'")  # noqa: E731


class Wiki:
    def __init__(self, pages, boom=False):
        self.pages, self.boom = pages, boom

    def wikitext(self, title):
        if self.boom:
            raise RuntimeError("down")
        return self.pages.get(title, "")


# ---- the countries and events -----------------------------------------------------------------------------
check("the countries D named: India, Singapore, Malaysia, Indonesia, Thailand, the Philippines, Vietnam, Brunei, Cambodia, Myanmar, Laos and Timor-Leste",
      {"IND", "SGP", "MAS", "INA", "THA", "PHI", "VIE", "BRU", "CAM", "MYA", "LAO", "TLS"} <= set(bd.SPOT) and bd.SPOT["TLS"] == "Timor-Leste" and bd.SPOT["IDN"] == "Indonesia" and len(set(bd.SPOT.values())) == 12)
check("the events: the four Super 1000s, the World Championships, the World Tour Finals, the Singapore Open and the India Open",
      [n for n, _, _ in bd.CALENDAR] == ["All England Open", "Malaysia Open", "India Open", "Indonesia Open", "Singapore Open", "China Open", "BWF World Championships", "BWF World Tour Finals"])
check("the disciplines are always in D's order: men's singles, women's singles, men's doubles, women's doubles, mixed doubles", bd.DISCIPLINES == ("Men's singles", "Women's singles", "Men's doubles", "Women's doubles", "Mixed doubles"))

# ---- reading cells -------------------------------------------------------------------------------------------
s = bd.side("'''{{flagicon|IND}} [[Lakshya Sen|L Sen]]'''")
check("a cell gives the full name from the link's target (the display text is abbreviated), the flag, and whether it is bold (the winner)", s == {"names": ["Lakshya Sen"], "flag": "IND", "bold": True}, s)
d = bd.side("{{flagicon|KOR}} [[Kim Won-ho]]<br />{{flagicon|KOR}} [[Seo Seung-jae]]")
check("a doubles cell gives both partners", d["names"] == ["Kim Won-ho", "Seo Seung-jae"] and d["flag"] == "KOR" and not d["bold"])
check("a disambiguation in the link is dropped: '[[Lee Jong-min (badminton)|Lee Jong-min]]' is Lee Jong-min", bd.side("[[Lee Jong-min (badminton)|Lee Jong-min]]")["names"] == ["Lee Jong-min"])

# ---- official round names -------------------------------------------------------------------------------------
check("rounds count back from the quarter-finals: a 32 draw's first round is the Round of 32, its second the Round of 16; a 64 draw starts at the Round of 64",
      bd.official_rounds({1: "First round", 2: "Second round", 3: "Quarter-finals"}) == {1: "Round of 32", 2: "Round of 16", 3: "Quarter-finals"}
      and bd.official_rounds({1: "First round", 2: "Second round", 3: "Third round", 4: "Quarter-finals"}) == {1: "Round of 64", 2: "Round of 32", 3: "Round of 16", 4: "Quarter-finals"})
check("the finals bracket keeps Semi-finals and Final", bd.official_rounds({1: "Semi-finals", 2: "Final"}) == {1: "Semi-finals", 2: "Final"})

# ---- a real draw page --------------------------------------------------------------------------------------------
p = bd.parse(AE)
check("the All England page: five disciplines, a 32 draw has 31 matches (30 for women's singles: a walkover has no scores), the semi-finals (2) and the final (1) in each",
      list(p) == list(bd.DISCIPLINES) and [len(p[d]["matches"]) for d in bd.DISCIPLINES] == [31, 30, 31, 31, 31]
      and all(sum(1 for m in p[d]["matches"] if m["round"] == "Semi-finals") == 2 and sum(1 for m in p[d]["matches"] if m["round"] == "Final") == 1 for d in bd.DISCIPLINES), {d: len(p[d]["matches"]) for d in p})
check("the rounds are the official names: Round of 32 (16 matches in singles), Round of 16 (8), Quarter-finals (4), Semi-finals (2), Final (1)",
      {m["round"] for m in p["Men's singles"]["matches"]} == {"Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"}
      and [sum(1 for m in p["Men's singles"]["matches"] if m["round"] == r_) for r_ in ("Round of 32", "Round of 16", "Quarter-finals")] == [16, 8, 4])
fin = {d: next(m for m in p[d]["matches"] if m["round"] == "Final") for d in p}
w = lambda m: m["a" if m["winner"] == "a" else "b"]["names"]  # noqa: E731
check("the five finals: winners and scores as on the page", [w(fin[d]) for d in bd.DISCIPLINES] == [["Shi Yuqi"], ["An Se-young"], ["Kim Won-ho", "Seo Seung-jae"], ["Nami Matsuyama", "Chiharu Shida"], ["Guo Xinwa", "Chen Fanghui"]]
      and bd.score_text(fin["Men's singles"]) == "21–17, 21–19" and bd.score_text(fin["Women's singles"]) == "13–21, 21–18, 21–18", [bd.score_text(fin[d]) for d in bd.DISCIPLINES])
check("seeds are read in order: men's singles Shi Yuqi, Antonsen, Christie; women's An Se-young, Wang Zhiyi, Yamaguchi", [n for n, _ in p["Men's singles"]["seeds"][:3]] == ["Shi Yuqi", "Anders Antonsen", "Jonatan Christie"] and [n for n, _ in p["Women's singles"]["seeds"][:3]] == ["An Se-young", "Wang Zhiyi", "Akane Yamaguchi"])
tops = bd.top_seeds(p)
check("the top three singles seeds stand for the top three ranked players (men and women)", tops == {"Men's singles": {"Shi Yuqi", "Anders Antonsen", "Jonatan Christie"}, "Women's singles": {"An Se-young", "Wang Zhiyi", "Akane Yamaguchi"}}, tops)
check("the event's level is read from the page ('BWF World Tour Super 1000'); the World Tour Finals have none", bd.level_of(AE) == "BWF World Tour Super 1000" and bd.level_of(CO) == "BWF World Tour Super 1000" and bd.level_of(WTF) is None)

# ---- who is of interest ---------------------------------------------------------------------------------------------
ms = p["Men's singles"]["matches"]
sen = next(m for m in ms if "Lakshya Sen" in m["a"]["names"] + m["b"]["names"] and m["round"] == "Round of 16")
check("an Indian player's match is of interest; so is a top seed's; a match between two unlisted, unseeded players is not",
      bd.interesting(sen, "Men's singles", tops) and any(bd.interesting(m, "Men's singles", tops) for m in ms if "Shi Yuqi" in m["a"]["names"] + m["b"]["names"])
      and not bd.interesting(next(m for m in ms if m["a"]["flag"] not in bd.SPOT and m["b"]["flag"] not in bd.SPOT and not ({"Shi Yuqi", "Anders Antonsen", "Jonatan Christie"} & set(m["a"]["names"] + m["b"]["names"]))), "Men's singles", tops))

# ---- the one standard line ---------------------------------------------------------------------------------------------
check("the line is always winner first: 'Lakshya Sen (IND) def. Jonatan Christie (INA) [3] 21–13, 21–10'", bd.line(sen) == "Lakshya Sen (IND) def. Jonatan Christie (INA) [3] 21–13, 21–10", bd.line(sen))
loh = next(m for m in ms if m["round"] == "Quarter-finals" and "Loh Kean Yew" in m["a"]["names"] + m["b"]["names"])
check("a loss by the player D follows reads the same way, the winner first: 'Shi Yuqi (CHN) [1] def. Loh Kean Yew (SGP) 21–18, 21–16' (never 'lost to')", bd.line(loh) == "Shi Yuqi (CHN) [1] def. Loh Kean Yew (SGP) 21–18, 21–16", bd.line(loh))
check("in every match of the page the line has 'def.' and none has 'lost to' or 'beat'", all(" def. " in bd.line(m) and " lost to " not in bd.line(m) and " beat " not in bd.line(m) for d in p for m in p[d]["matches"]))
check("the winner is in bold and the loser is not", bd.line_html(sen).startswith("<strong>Lakshya Sen (IND)</strong> def. Jonatan Christie (INA) [3] 21–13, 21–10") and bd.line_html(sen).count("<strong>") == 1)
ret = next(m for d in p for m in p[d]["matches"] if m.get("retired"))
check("a match that ended early says so, winner first: Satwik/Chirag's retirement in the Round of 16", bd.line(ret) == "Xie Haonan / Zeng Weihan (CHN) def. Satwiksairaj Rankireddy / Chirag Shetty (IND) [7] 21–16 (retired)", bd.line(ret))
co = bd.parse(CO)
han = next(m for m in co["Women's singles"]["matches"] if m["round"] == "Semi-finals" and m.get("retired"))
check("a retired semi-final too (China Open: Han Yue beat An Se-young 21–19 and the match ended)", "Han Yue" in han["a"]["names"] + han["b"]["names"] and bd.score_text(han) == "21–19 (retired)", bd.score_text(han))

# ---- seeds and the order D looks in ---------------------------------------------------------------------------------------------
check("the seeds come from the page's Seeds list (1, 2, 3 ... in order): Shi Yuqi 1, Antonsen 2, Christie 3, Vitidsarn 5, Lee Zii Jia 7 in the men's singles",
      {n: i for i, (n, _) in enumerate(p["Men's singles"]["seeds"], 1)}["Shi Yuqi"] == 1 and {n: i for i, (n, _) in enumerate(p["Men's singles"]["seeds"], 1)}["Lee Zii Jia"] == 7)
raw_seed = re.search(r"RD1-seed\d+\s*=\s*(\d+)\s*\n\|\s*RD1-team\d+\s*=[^\n]*Satwiksairaj", AE)
check("a seeded pair carries its seed: Satwik/Chirag are 7 (the same number the draw's own seed field has next to them)", raw_seed and raw_seed.group(1) == "7" and "Satwiksairaj Rankireddy / Chirag Shetty (IND) [7]" in bd.line(ret))
check("seeded players show it in square brackets in the line (Shi Yuqi [1], Lee Zii Jia [7], Christie [3]) and an unseeded player does not", "[1]" in bd.line_html(loh) and "Lee Zii Jia (MAS) [7]" in bd.line(next(m for m in ms if "Lee Zii Jia" in m["a"]["names"] + m["b"]["names"] and m["round"] == "Round of 32")) and "Lakshya Sen (IND) def" in bd.line(sen))
r32 = [m for m in p["Men's singles"]["matches"] if m["round"] == "Round of 32" and bd.interesting(m, "Men's singles", tops)]
ordered = bd.by_priority(r32)
check("Singapore's matches come first, then India's, then the other Southeast Asian countries', then the rest (a top seed against an unlisted player)", [bd.priority(m) for m in ordered] == sorted(bd.priority(m) for m in r32)
      and bd.priority(ordered[0]) == 0 and "Loh Kean Yew" in ordered[0]["a"]["names"] + ordered[0]["b"]["names"] and [bd.priority(m) for m in ordered][:3] == [0, 1, 1] and bd.priority(ordered[-1]) == 3, [bd.priority(m) for m in ordered])
check("priority: a Singapore-India match counts as Singapore's; Brunei, Cambodia, Myanmar, Laos and Timor-Leste are 'other Southeast Asian'; China-Japan is neither",
      bd.priority({"a": {"flag": "SGP"}, "b": {"flag": "IND"}}) == 0 and bd.priority({"a": {"flag": "IND"}, "b": {"flag": "CHN"}}) == 1 and all(bd.priority({"a": {"flag": f}, "b": {"flag": "CHN"}}) == 2 for f in ("BRU", "CAM", "MYA", "LAO", "TLS", "MAS", "INA", "THA", "PHI", "VIE")) and bd.priority({"a": {"flag": "CHN"}, "b": {"flag": "JPN"}}) == 3)
h_ord = bd.event_html("All England Open", {"Men's singles": r32}, tops)
names_in_order = re.findall(r"<li><strong>([^<]*)</strong>", h_ord)
check("in the page the bullets are in that order: Loh Kean Yew (SGP) first, then the two Indians", names_in_order[0].startswith("Loh Kean Yew") and names_in_order[1].startswith("Lakshya Sen") and names_in_order[2].startswith("Toma Junior Popov"), names_in_order[:4])
sf = [m for m in p["Women's doubles"]["matches"] if m["round"] == "Semi-finals"]
check("the semi-final tables are ordered the same way (the match with the listed country first)", [bd.priority(m) for m in bd.by_priority(sf)] == sorted(bd.priority(m) for m in sf))

# ---- the start notice ----------------------------------------------------------------------------------------------------
wiki = Wiki({"2025 All England Open": AE})
n1 = bd.run(wiki, date(2025, 3, 6), {})
check("five days before: one line, 'All England Open (BWF World Tour Super 1000) starts on Tuesday 11 March', and no list of players", len(n1["blocks"]) == 1 and text(n1["blocks"][0][1]).strip() == "All England Open (BWF World Tour Super 1000) starts on Tuesday 11 March", text(n1["blocks"][0][1]))
check("the notice is given once", bd.run(wiki, date(2025, 3, 7), n1["state"])["blocks"] == [] and n1["state"]["2025 All England Open"]["announced"])
check("more than a week before there is no notice", bd.run(wiki, date(2025, 3, 1), {})["blocks"] == [])
check("there is no 'who is in the draw' paragraph any more: nothing in the module builds one", not hasattr(bd, "draw_note") and "who is in the draw" not in text(bd.run(wiki, date(2025, 3, 17), {})["blocks"][0][1]))

# ---- grouping and order ---------------------------------------------------------------------------------------------------
fresh = {d: [m for m in info["matches"] if m["round"] == "Round of 32" and bd.interesting(m, d, tops)] for d, info in p.items()}
h = bd.event_html("All England Open", {d: v for d, v in fresh.items() if v}, tops)
t = text(h)
import html as _html  # noqa: E402
titles = [_html.unescape(x) for x in re.findall(r"<p class=\"subhead\">([^<]*)</p>", h)]
check("one title for each discipline that has matches, in the fixed order, each with its round", titles == ["All England Open", "Men's singles · Round of 32", "Women's singles · Round of 32", "Men's doubles · Round of 32", "Women's doubles · Round of 32", "Mixed doubles · Round of 32"], titles)
check("each match is one bullet of a gold-diamond list with space between the lines, winner in bold", h.count('<ul class="standouts bd">') == 5 and h.count("<li>") == sum(len(v) for v in fresh.values()) and h.count("<strong>") == h.count("<li>"))
check("a discipline with no match that day gets no title", "Mixed doubles" not in text(bd.event_html("X", {"Men's singles": fresh["Men's singles"]}, tops)))
check("the early rounds are in round order inside a discipline (Round of 32 before Round of 16)", re.findall(r"Men&#x27;s singles · ([^<]*)</p>", bd.event_html("X", {"Men's singles": [m for m in p["Men's singles"]["matches"] if m["round"] in ("Round of 16", "Round of 32", "Quarter-finals") and bd.interesting(m, "Men's singles", tops)]}, tops)) == ["Round of 32", "Round of 16", "Quarter-finals"])

# ---- the tables ---------------------------------------------------------------------------------------------------------------
h = bd.late_table("Men's singles", "All England Open · Final", [fin["Men's singles"]])
t = text(h)
check("a table: the title, then two rows a match (the winner first and bold), a column for each game", "Men's singles · All England Open · Final" in t and 'class="w"' in h and 'class="l"' in h and h.count("<tr class") == 2
      and "Shi Yuqi CHN [1] 21 21" in t and "Lee Chia-hao TPE 17 19" in t, t)
h2 = bd.late_table("Women's singles", "All England Open · Final", [fin["Women's singles"]])
check("a three-game match fills all three columns: An Se-young 13 21 21 over Wang Zhiyi 21 18 18", "An Se-young KOR [1] 13 21 21" in text(h2) and "Wang Zhiyi CHN [2] 21 18 18" in text(h2))
h3 = bd.late_table("Men's doubles", "x", [fin["Men's doubles"]])
check("doubles pairs sit one partner above the other in a single cell", "Kim Won-ho / Seo Seung-jae KOR" in text(h3) and h3.count("<br>") == 2)
h4 = bd.late_table("Women's singles", "China Open · Semi-finals", [han])
check("a retired match is marked in the table (the one game played, and 'ret.')", "ret." in h4 and "21" in text(h4))

# ---- the run: day by day, each match once ----------------------------------------------------------------------------------------
check("well after the event, nothing", bd.run(wiki, date(2025, 3, 20), {})["blocks"] == [])
d1 = bd.run(wiki, date(2025, 3, 17), {})
h = d1["blocks"][0][1]
early = [m for d in bd.DISCIPLINES for m in p[d]["matches"] if m["round"] not in bd.LATE and bd.interesting(m, d, tops)]
check("on a day in the window: every early match of interest (and no other) as a bullet, and the 10 semi-final and final tables", h.count("<li>") == len(early) and h.count('<div class="tennis">') == 10 and "starts on" not in h, (h.count("<li>"), len(early)))
check("each match is shown once: the same page the next morning gives nothing", bd.run(wiki, date(2025, 3, 17), d1["state"])["blocks"] == [])
half = {k: dict(v) for k, v in d1["state"].items()}
half["2025 All England Open"]["seen"] = [x for x in half["2025 All England Open"]["seen"] if x.split("|")[0] not in ("Final", "Semi-finals")]
d3 = bd.run(wiki, date(2025, 3, 17), half)
check("a later morning shows only what is new: forgetting the semi-finals and final gives just those 10 tables and no bullets", d3["blocks"][0][1].count('<div class="tennis">') == 10 and "<li>" not in d3["blocks"][0][1])
check("a page that has no draw yet, no page, or a Wikipedia that is down gives nothing and no error", bd.run(Wiki({"2025 All England Open": "{{Infobox badminton}}"}), date(2025, 3, 17), {})["blocks"] == [] and bd.run(Wiki({}), date(2025, 3, 17), {})["blocks"] == []
      and bd.run(Wiki({}, boom=True), date(2025, 3, 17), {}, [])["blocks"] == [])
fails = []
bd.run(Wiki({}, boom=True), date(2025, 3, 17), {}, fails)
check("a Wikipedia that is down is counted", fails)
july = bd.run(Wiki({"2025 China Open (badminton)": CO}), date(2025, 7, 29), {})
check("the China Open of July 2025 is found in July (its month list covers July and November), semi-finals and final as tables", july["blocks"] and "Han Yue" in text(july["blocks"][0][1]) and july["blocks"][0][1].count('<div class="tennis">') == 10)
nov = bd.run(Wiki({"2025 BWF World Tour Finals": WTF}), date(2025, 12, 22), {})
check("the World Tour Finals (a small draw of four a discipline) show their semi-finals and finals too, with no level in a notice", nov["blocks"] and nov["blocks"][0][1].count('<div class="tennis">') == 10)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
