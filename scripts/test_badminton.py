"""Tests for badminton (D's rules, 2026-11-05): reading a Wikipedia draw page, who counts (India, Southeast Asia, the top three singles seeds), one line per early-round match of interest, tables
from the semi-finals, the draw note, and showing each match once. Real 2025 pages: All England Open, China Open, World Tour Finals. Run: .venv/bin/python scripts/test_badminton.py"""
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


# ---- the countries ----------------------------------------------------------------------------------------
check("the countries D named: India, Singapore, Malaysia, Indonesia, Thailand, the Philippines, Vietnam, Brunei, Cambodia, Myanmar, Laos and Timor-Leste",
      {"IND", "SGP", "MAS", "INA", "THA", "PHI", "VIE", "BRU", "CAM", "MYA", "LAO", "TLS"} <= set(bd.SPOT) and bd.SPOT["TLS"] == "Timor-Leste" and bd.SPOT["IDN"] == "Indonesia" and len(set(bd.SPOT.values())) == 12)
check("the events: the four Super 1000s, the World Championships, the World Tour Finals, the Singapore Open and the India Open",
      [n for n, _, _ in bd.CALENDAR] == ["All England Open", "Malaysia Open", "India Open", "Indonesia Open", "Singapore Open", "China Open", "BWF World Championships", "BWF World Tour Finals"])

# ---- reading cells -------------------------------------------------------------------------------------------
s = bd.side("'''{{flagicon|IND}} [[Lakshya Sen|L Sen]]'''")
check("a cell gives the full name from the link's target (the display text is abbreviated), the flag, and whether it is bold (the winner)", s == {"names": ["Lakshya Sen"], "flag": "IND", "bold": True}, s)
d = bd.side("{{flagicon|KOR}} [[Kim Won-ho]]<br />{{flagicon|KOR}} [[Seo Seung-jae]]")
check("a doubles cell gives both partners", d["names"] == ["Kim Won-ho", "Seo Seung-jae"] and d["flag"] == "KOR" and not d["bold"])
check("a disambiguation in the link is dropped: '[[Lee Jong-min (badminton)|Lee Jong-min]]' is Lee Jong-min", bd.side("[[Lee Jong-min (badminton)|Lee Jong-min]]")["names"] == ["Lee Jong-min"])

# ---- a real draw page -------------------------------------------------------------------------------------------
p = bd.parse(AE)
check("the All England page: five disciplines, a 32-draw has 31 matches (30 for women's singles: a walkover has no scores), the semi-finals (2) and the final (1) in each",
      list(p) == list(bd.DISCIPLINES) and [len(p[d]["matches"]) for d in bd.DISCIPLINES] == [31, 30, 31, 31, 31]
      and all(sum(1 for m in p[d]["matches"] if m["round"] == "Semi-finals") == 2 and sum(1 for m in p[d]["matches"] if m["round"] == "Final") == 1 for d in bd.DISCIPLINES), {d: len(p[d]["matches"]) for d in p})
fin = {d: next(m for m in p[d]["matches"] if m["round"] == "Final") for d in p}
w = lambda m: m["a" if m["winner"] == "a" else "b"]["names"]  # noqa: E731
check("the five finals: winners and scores as on the page", [w(fin[d]) for d in bd.DISCIPLINES] == [["Shi Yuqi"], ["An Se-young"], ["Kim Won-ho", "Seo Seung-jae"], ["Nami Matsuyama", "Chiharu Shida"], ["Guo Xinwa", "Chen Fanghui"]]
      and bd.score_text(fin["Men's singles"]) == "21–17, 21–19" and bd.score_text(fin["Women's singles"]) == "13–21, 21–18, 21–18", [bd.score_text(fin[d]) for d in bd.DISCIPLINES])
check("seeds are read in order: men's singles Shi Yuqi, Antonsen, Christie; women's An Se-young, Wang Zhiyi, Yamaguchi", [n for n, _ in p["Men's singles"]["seeds"][:3]] == ["Shi Yuqi", "Anders Antonsen", "Jonatan Christie"] and [n for n, _ in p["Women's singles"]["seeds"][:3]] == ["An Se-young", "Wang Zhiyi", "Akane Yamaguchi"])
tops = bd.top_seeds(p)
check("the top three singles seeds stand for the top three ranked players (men and women)", tops == {"Men's singles": {"Shi Yuqi", "Anders Antonsen", "Jonatan Christie"}, "Women's singles": {"An Se-young", "Wang Zhiyi", "Akane Yamaguchi"}}, tops)
check("the draw has 36 entrants listed per discipline (a 32 draw with the qualifiers' first-round entries)", all(len(p[d]["field"]) >= 32 for d in bd.DISCIPLINES))

# ---- who is of interest ---------------------------------------------------------------------------------------------
ms = p["Men's singles"]["matches"]
sen = next(m for m in ms if "Lakshya Sen" in m["a"]["names"] + m["b"]["names"] and m["round"] == "Second round")
check("an Indian player's match is of interest; so is a top seed's; a match between two unlisted, unseeded players is not",
      bd.interesting(sen, "Men's singles", tops) and any(bd.interesting(m, "Men's singles", tops) for m in ms if "Shi Yuqi" in m["a"]["names"] + m["b"]["names"])
      and not bd.interesting(next(m for m in ms if m["a"]["flag"] not in bd.SPOT and m["b"]["flag"] not in bd.SPOT and not ({"Shi Yuqi", "Anders Antonsen", "Jonatan Christie"} & set(m["a"]["names"] + m["b"]["names"]))), "Men's singles", tops))
check("an early-round line leads with the winner ('beat') or, when the listed player lost, with him ('lost to')",
      bd.line(sen) == "Second round: Lakshya Sen (IND) beat Jonatan Christie (INA) 21–13, 21–10" and bd.line(next(m for m in ms if m["round"] == "Quarter-finals" and "Loh Kean Yew" in m["a"]["names"] + m["b"]["names"])) == "Quarter-finals: Loh Kean Yew (SGP) lost to Shi Yuqi (CHN) 18–21, 16–21")
ret = next(m for d in p for m in p[d]["matches"] if m.get("retired"))
check("a match with fewer than two games won by anyone is a retirement and says so (Satwik/Chirag, 16–21 in round 2)", bd.line(ret) == "Second round: Satwiksairaj Rankireddy / Chirag Shetty (IND) lost to Xie Haonan / Zeng Weihan (CHN) 16–21 (retired)", bd.line(ret))
co = bd.parse(CO)
han = next(m for m in co["Women's singles"]["matches"] if m["round"] == "Semi-finals" and m.get("retired"))
check("a retired semi-final too (China Open: Han Yue beat An Se-young 21–19 and the match ended)", "Han Yue" in han["a"]["names"] + han["b"]["names"] and bd.score_text(han) == "21–19 (retired)", bd.score_text(han))

# ---- the draw note ----------------------------------------------------------------------------------------------------
note = bd.draw_note(p, tops)
lines = bd.note_text(note)
check("the draw note lists India first, then the others alphabetically, then the top seeds", [x["head"] for x in note] == ["India", "Indonesia", "Malaysia", "Singapore", "Thailand", "Vietnam", "Top seeds"], [x["head"] for x in note])
check("India: men's singles Lakshya Sen and Prannoy, women's singles Sindhu and Bansod, Satwik/Chirag in men's doubles, Treesa/Gayatri in women's doubles, one row a discipline",
      note[0]["rows"][:4] == [("MS", "Lakshya Sen, Prannoy H. S."), ("WS", "Malvika Bansod, P. V. Sindhu"), ("MD", "Satwiksairaj Rankireddy / Chirag Shetty"),
                              ("WD", "Priya Konjengbam / Shruti Mishra; Tanisha Crasto / Ashwini Ponnappa; Treesa Jolly / Gayatri Gopichand")] and [c for c, _ in note[0]["rows"]] == ["MS", "WS", "MD", "WD", "XD"], note[0]["rows"])
check("a player is listed once even though he is in the draw and in the seeds (Jonatan Christie once under Indonesia's MS)", lines[1].count("Jonatan Christie") == 1)
check("Singapore: Loh Kean Yew and Jason Teh in the men's singles, Yeo Jia Min in the women's, Terry Hee / Jin Yujia in the mixed", lines[3] == "Singapore: MS Jason Teh, Loh Kean Yew; WS Yeo Jia Min; XD Terry Hee / Jin Yujia", lines[3])
check("the top seeds row names the six: Shi Yuqi, Antonsen, Christie and An Se-young, Wang Zhiyi, Yamaguchi", lines[-1] == "Top seeds: MS Shi Yuqi, Anders Antonsen, Jonatan Christie; WS An Se-young, Wang Zhiyi, Akane Yamaguchi", lines[-1])

# ---- the tables ---------------------------------------------------------------------------------------------------------
h = bd.late_table("Men's singles", "All England Open · Final", [fin["Men's singles"]])
t = text(h)
check("a table: the title, then two rows a match (the winner first and bold), a column for each game", "Men's singles · All England Open · Final" in t and 'class="w"' in h and 'class="l"' in h and h.count("<tr class") == 2
      and "Shi Yuqi CHN 21 21" in t and "Lee Chia-hao TPE 17 19" in t, t)
h2 = bd.late_table("Women's singles", "All England Open · Final", [fin["Women's singles"]])
check("a three-game match fills all three columns: An Se-young 13 21 21 over Wang Zhiyi 21 18 18", "An Se-young KOR 13 21 21" in text(h2) and "Wang Zhiyi CHN 21 18 18" in text(h2))
h3 = bd.late_table("Men's doubles", "x", [fin["Men's doubles"]])
check("doubles pairs sit one partner above the other in a single cell", "Kim Won-ho / Seo Seung-jae KOR" in text(h3) and h3.count("<br>") == 2)
h4 = bd.late_table("Women's singles", "China Open · Semi-finals", [han])
check("a retired match is marked in the table (the one game played, and 'ret.')", "ret." in h4 and "21" in text(h4))

# ---- the run: day by day, each match once ------------------------------------------------------------------------------------
wiki = Wiki({"2025 All England Open": AE})
check("before the event (more than a day ahead) and well after it, nothing", bd.run(wiki, date(2025, 3, 5), {})["blocks"] == [] and bd.run(wiki, date(2025, 3, 20), {})["blocks"] == [])
d1 = bd.run(wiki, date(2025, 3, 17), {})
h = d1["blocks"][0][1]
check("on a day in the window: the draw note, the early-round lines of interest, and the semi-final and final tables", "who is in the draw" in h and "Second round: Lakshya Sen (IND) beat Jonatan Christie (INA)" in text(h) and h.count('<div class="tennis">') == 10, h.count('<div class="tennis">'))
early = [m for d in bd.DISCIPLINES for m in p[d]["matches"] if m["round"] not in bd.LATE and bd.interesting(m, d, tops)]
check("every early match of interest has a line and no other early match does (counted separately with the same rule)", len(re.findall(r"<li>", h.split("who is in the draw")[1].split("</ul>", 1)[1])) == len(early) and "Quarter-finals: Lee Zii Jia" not in text(h), (len(early),))
d2 = bd.run(wiki, date(2025, 3, 17), d1["state"])
check("each match is shown once: the same page the next morning gives nothing, and the draw note is not repeated", d2["blocks"] == [] and d1["state"]["2025 All England Open"]["noted"], d2["blocks"])
half = {k: dict(v) for k, v in d1["state"].items()}
half["2025 All England Open"]["seen"] = [x for x in half["2025 All England Open"]["seen"] if "Final" not in x.split("|")[0] and "Semi" not in x.split("|")[0]]
d3 = bd.run(wiki, date(2025, 3, 17), half)
check("a later morning shows only what is new: forgetting the semi-finals and final gives just those tables (10 of them: 5 semis, 5 finals) and no draw note", d3["blocks"][0][1].count('<div class="tennis">') == 10 and "who is in the draw" not in d3["blocks"][0][1])
check("a page that has no draw yet, no page, or a Wikipedia that is down gives nothing and no error", bd.run(Wiki({"2025 All England Open": "{{Infobox badminton}}"}), date(2025, 3, 17), {})["blocks"] == [] and bd.run(Wiki({}), date(2025, 3, 17), {})["blocks"] == []
      and bd.run(Wiki({}, boom=True), date(2025, 3, 17), {}, [])["blocks"] == [])
fails = []
bd.run(Wiki({}, boom=True), date(2025, 3, 17), {}, fails)
check("a Wikipedia that is down is counted", fails)
july = bd.run(Wiki({"2025 China Open (badminton)": CO}), date(2025, 7, 29), {})
check("the China Open of July 2025 is found in July (its month list covers July and November), semi-finals and final as tables", july["blocks"] and "Han Yue" in text(july["blocks"][0][1]) and july["blocks"][0][1].count('<div class="tennis">') == 10)
nov = bd.run(Wiki({"2025 BWF World Tour Finals": WTF}), date(2025, 12, 22), {})
check("the World Tour Finals (a small draw of four a discipline) show their semi-finals and finals too", nov["blocks"] and nov["blocks"][0][1].count('<div class="tennis">') == 10, nov["blocks"][0][1].count('<div class="tennis">') if nov["blocks"] else 0)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
