"""Tests for the monthly UFC rankings table (D, 2026-11-05): UFC.com's rankings page read, the top 10 of both pound-for-pound lists and the champion plus #1 and #2 of the 11 divisions, the moves since the
table was last shown, and the first-Wednesday-of-the-month rule. The real page of 3 November 2026. Run: .venv/bin/python scripts/test_ufcrank.py"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import ufcrank  # noqa: E402

PAGE = (ROOT / "tests" / "fixtures" / "ufc_com_rankings.html").read_text()
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


text = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&#x27;", "'")  # noqa: E731


class Src:
    def __init__(self, page=PAGE, boom=False):
        self.page, self.boom = page, boom

    def ufc_rankings_page(self):
        if self.boom:
            raise RuntimeError("down")
        return self.page


g = ufcrank.parse(PAGE)
check("the page has 13 lists: both pound-for-pound lists and the 11 divisions (its repeated phone blocks are ignored)", len(g) == 13 and set(ufcrank.P4P) <= set(g) and set(ufcrank.DIVISIONS) <= set(g), sorted(g))
check("each list is read with its champion (or top rank) and 15 ranked names", all(len(v["ranks"]) == 15 and v["champion"] for v in g.values()))
check("an apostrophe in a name is unescaped (Sean O'Malley, Women's Strawweight)", "Sean O'Malley" in g["Bantamweight"]["ranks"] and "Women's Strawweight" in g)
check("the page says when UFC updated the rankings", ufcrank.updated(PAGE) == "Tuesday, Nov. 03")
lst = ufcrank.listing(g)
check("the table lists the top 10 of both pound-for-pound lists and the champion, #1 and #2 of each division", [len(lst[k]) for k in ufcrank.P4P] == [10, 10] and all(len(lst[k]) == 3 for k in ufcrank.DIVISIONS)
      and lst["Men's Pound-for-Pound"][0] == "Islam Makhachev" and lst["Flyweight"] == ["Joshua Van", "Alexandre Pantoja", "Manel Kape"] and lst["Heavyweight"] == ["Ciryl Gane", "Tom Aspinall", "Alexander Volkov"], lst["Flyweight"])
check("cross-check against the raw page: the Lightweight champion and the first two contenders appear in the page's own text in that order", PAGE.index("Justin Gaethje") < PAGE.index("Ilia Topuria") < PAGE.index("Arman Tsarukyan") and lst["Lightweight"] == ["Justin Gaethje", "Ilia Topuria", "Arman Tsarukyan"])

# ---- the moves ------------------------------------------------------------------------------------------------------------
old = ["A", "B", "C", "D"]
check("moves: up two is ▲2, down one ▼1, no change –, a name that was not in the old list NEW; with no old list there is no move at all",
      ufcrank.move("C", old, 0) == "\u25b22" and ufcrank.move("A", old, 1) == "\u25bc1" and ufcrank.move("B", old, 1) == "\u2013" and ufcrank.move("Z", old, 0) == "NEW" and ufcrank.move("A", None, 0) == "")

# ---- when --------------------------------------------------------------------------------------------------------------------
check("it is due on the first Wednesday of a month (4 Nov 2026), not before it (3 Nov), and not again that month", ufcrank.due(date(2026, 11, 4), {}) and not ufcrank.due(date(2026, 11, 3), {}) and not ufcrank.due(date(2026, 11, 11), {"month": "2026-11"}))
check("if that morning was missed, the first edition after it is due (Saturday 7 Nov), and next month's first Wednesday (2 Dec) is due again", ufcrank.due(date(2026, 11, 7), {}) and ufcrank.due(date(2026, 12, 2), {"month": "2026-11"}) and not ufcrank.due(date(2026, 12, 1), {"month": "2026-11"}))

# ---- the run -----------------------------------------------------------------------------------------------------------------
out = ufcrank.run(Src(), date(2026, 11, 4), {})
h = out["blocks"][0]
t = text(h)
heads = [x.replace("&#x27;", "'") for x in re.findall(r'<tr class="sub"><td class=""></td><td class="">([^<]*)</td>', h)]
check("D's order: the men's pound-for-pound, the eight men's classes from Flyweight to Heavyweight, a break, then the women's pound-for-pound and the three women's classes",
      heads == ["Men's Pound-for-Pound", "Flyweight", "Bantamweight", "Featherweight", "Lightweight", "Welterweight", "Middleweight", "Light Heavyweight", "Heavyweight", "Women's Pound-for-Pound",
                "Women's Strawweight", "Women's Flyweight", "Women's Bantamweight"], heads)
check("one break row, between the last men's class and the women's pound-for-pound", h.count('class="gap"') == 1 and h.index("Heavyweight") < h.index('class="gap"') < h.index("Women&#x27;s Pound-for-Pound"))
p1_rows = re.findall(r'<tr class="p1">(.*?)</tr>', h, re.S)
check("D: the first rank of each pound-for-pound list and the champion of each division are in bold gold (13 rows, the first row under each sub-heading)", len(p1_rows) == 13
      and [text(x).strip().split(" ")[0] for x in p1_rows] == ["1", "C", "C", "C", "C", "C", "C", "C", "C", "1", "C", "C", "C"]
      and "Islam Makhachev" in text(p1_rows[0]) and "Joshua Van" in text(p1_rows[1]) and "Valentina Shevchenko" in text(p1_rows[9]), [text(x).strip()[:24] for x in p1_rows])
css = (ROOT / "kickoff" / "static" / "style.css").read_text()
check("the gold rows have their own colour rule so the Move column is gold too", ".ufcrank tr.p1 td, .ufcrank tr.p1 td:nth-child(3) { color: var(--gold); font-weight: 700; }" in css)
check("the first column has padding on the left (12px): the numbers are not flush against the edge, in the UFC table and in the golf tables", ".ufcrank th:first-child, .ufcrank td:first-child { padding-left: 12px; }" in css and ".pts.f1.golf th:first-child, .pts.f1.golf td:first-child { padding-left: 12px; }" in css)

check("the block: a title with the update date, then one compact table with a sub-heading for each list", t.strip().startswith("UFC rankings \u00b7 updated Tuesday, Nov. 03") and h.count('class="sub"') == 13 and "Women's Pound-for-Pound" in t and "Light Heavyweight" in t, t[:200])
check("the divisions show C for the champion, then 1 and 2; the pound-for-pound lists show 1 to 10", "Flyweight C Joshua Van 1 Alexandre Pantoja 2 Manel Kape" in t and "Men's Pound-for-Pound 1 Islam Makhachev 2 Alexander Volkanovski" in t and "10 Alex Pereira" in t, t[:600])
check("the first time there are no moves in the Move column", "\u25b2" not in t and "\u25bc" not in t and "NEW" not in t)
check("the state remembers the month and what was shown", out["state"]["month"] == "2026-11" and out["state"]["snapshot"]["Flyweight"] == ["Joshua Van", "Alexandre Pantoja", "Manel Kape"])
check("once a month: the same Wednesday's page again gives nothing", ufcrank.run(Src(), date(2026, 11, 4), out["state"])["blocks"] == [])
prev = {"month": "2026-10", "snapshot": {**out["state"]["snapshot"], "Flyweight": ["Alexandre Pantoja", "Joshua Van", "Brandon Royval"], "Men's Pound-for-Pound": ["Alexander Volkanovski", "Islam Makhachev"] + out["state"]["snapshot"]["Men's Pound-for-Pound"][2:]}}
nxt = ufcrank.run(Src(), date(2026, 12, 2), prev)
tn = text(nxt["blocks"][0])
fw = tn[tn.index("Flyweight"):tn.index("Bantamweight")]
check("the Flyweight rows read: C Joshua Van ▲1 (he was second in the list), 1 Alexandre Pantoja ▼1, 2 Manel Kape NEW", "C Joshua Van \u25b21" in fw and "1 Alexandre Pantoja \u25bc1" in fw and "2 Manel Kape NEW" in fw, fw)
check("Makhachev is up one on the men's pound-for-pound list (he was second)", "1 Islam Makhachev \u25b21" in tn, tn[tn.index("Men's Pound"):tn.index("Men's Pound") + 120])
check("UFC.com down or laid out differently gives nothing rather than a half table, and no error", ufcrank.run(Src(boom=True), date(2026, 11, 4), {})["blocks"] == [] and ufcrank.run(Src("<html>nothing</html>"), date(2026, 11, 4), {})["blocks"] == []
      and ufcrank.run(Src(boom=True), date(2026, 11, 4), {})["state"] == {})
fails = []
ufcrank.run(Src(boom=True), date(2026, 11, 4), {}, fails)
check("a rankings page that cannot be read is counted", fails)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
