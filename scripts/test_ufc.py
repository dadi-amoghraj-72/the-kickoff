"""Tests for UFC (D's rules, 2026-11-05): UFC.com's event page read for the main event, the co-main event and the top bout of the Prelims; the NBA-style box (winner, def., loser, ranks in brackets, then
method, weight class and title fight); the header; numbered events only; each event once. Real saved UFC.com pages of UFC 309 (16 Nov 2024) and UFC 316 (7 Jun 2025). Run: .venv/bin/python scripts/test_ufc.py"""
import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import ufc  # noqa: E402

FX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


H309, H316 = (FX / "ufc_com_309.html").read_text(), (FX / "ufc_com_316.html").read_text()
ESPN = json.loads((FX / "ufc_espn_309.json").read_text())
text = lambda html: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&#x27;", "'")  # noqa: E731
p309, p316 = ufc.parse(H309), ufc.parse(H316)


class Src:
    """ESPN's board and UFC.com's pages. page: one html (served for any address of UFC 309: ufc-309) or a {address: html} dict."""

    def __init__(self, board, page=None, boom=False, listing=None):
        self.b, self.p, self.boom, self.l, self.asked = board, page, boom, listing, []

    def ufc(self):
        if self.boom == "espn":
            raise RuntimeError
        return self.b

    def ufc_listing(self):
        if self.l is None:
            raise RuntimeError("no listing")
        return self.l

    def ufc_page(self, slug):
        self.asked.append(slug)
        if self.p is None or self.boom == "page":
            raise RuntimeError("blocked")
        if isinstance(self.p, dict):
            return self.p.get(slug, "<html>no such event</html>")
        assert slug == "ufc-309", slug
        return self.p


# ---- the page --------------------------------------------------------------------------------------------
check("UFC 309: 5 fights on the Main Card, 3 on the Prelims and 4 on the Early Prelims, in billing order", [len(p309[k]) for k in ("main", "prelims", "early")] == [5, 3, 4]
      and [(f["red"]["name"], f["blue"]["name"]) for f in p309["main"]][:3] == [("Jon Jones", "Stipe Miocic"), ("Charles Oliveira", "Michael Chandler"), ("Bo Nickal", "Paul Craig")])
check("a fighter whose name is plain text in the page (not in given and family spans) is read too (Viviane Araújo)", ("Viviane Araújo", "Karine Silva") in [(f["red"]["name"], f["blue"]["name"]) for f in p309["main"]])
main, co, top = p309["main"][0], p309["main"][1], p309["prelims"][0]
check("main event: Jones (champion) won, Miocic was #8, a Heavyweight Title Bout, KO/TKO in round 3 at 4:29 (as UFC.com and Wikipedia both say)",
      main["red"] == {"name": "Jon Jones", "rank": "C", "outcome": "win"} and main["blue"] == {"name": "Stipe Miocic", "rank": "8", "outcome": "loss"} and main["title"] and main["weight"] == "Heavyweight"
      and (main["method"], main["round"], main["time"]) == ("KO/TKO", "3", "4:29"), main)
check("co-main event: Oliveira (#2) def. Chandler (#7), a Lightweight Bout (no title), Decision - Unanimous", co["red"]["rank"] == "2" and co["blue"]["rank"] == "7" and not co["title"] and co["weight"] == "Lightweight"
      and co["method"] == "Decision - Unanimous" and co["round"] == "5", co)
check("top bout of the Prelims: McGhee (unranked) def. Martinez (#13), a Bantamweight Bout, a unanimous decision", top["red"]["name"] == "Jonathan Martinez" and top["blue"]["name"] == "Marcus McGhee" and top["blue"]["outcome"] == "win" and top["blue"]["rank"] == "" and top["red"]["rank"] == "13" and top["method"] == "Decision - Unanimous", top)
check("UFC 316: a title fight on both: Dvalishvili (C) def. O'Malley (#1) by submission in round 3 (4:42); Harrison (#2) def. the champion Peña, the women's bantamweight title bout, by submission in round 2 (4:55)",
      p316["main"][0]["title"] and p316["main"][0]["red"]["rank"] == "C" and p316["main"][0]["method"] == "Submission" and p316["main"][0]["time"] == "4:42"
      and p316["main"][1]["title"] and p316["main"][1]["weight"] == "Women's Bantamweight" and p316["main"][1]["blue"] == {"name": "Kayla Harrison", "rank": "2", "outcome": "win"} and p316["main"][1]["red"]["rank"] == "C")
check("the pick is three fights: the main event, the co-main event and the top bout of the Prelims", [l for l, _ in ufc.three(p309)] == ["Main Event", "Co-Main Event", "Prelims · Top Bout"] and [f["red"]["name"] for _, f in ufc.three(p309)] == ["Jon Jones", "Charles Oliveira", "Jonathan Martinez"])
unfought = copy.deepcopy(p309)
for k in unfought:
    for f in unfought[k]:
        f["finished"] = False
check("a card still to be fought gives no picks; a half-finished one only the fights that are over", ufc.three(unfought) == [] and [l for l, _ in ufc.three({**p309, "main": [{**p309["main"][0], "finished": False}] + p309["main"][1:]})] == ["Co-Main Event", "Prelims · Top Bout"])

# ---- the box ----------------------------------------------------------------------------------------------------
check("how the fight was won: a finish gives the round and the time, a decision gives its type", ufc.how(main) == "KO/TKO, round 3 (4:29)" and ufc.how(co) == "Decision - Unanimous")
box = ufc.box_html("Main Event", main)
t = text(box)
check("the box: its title, then the winner on the left in bold with [C], 'def.' in the middle, the loser with [8] on the right", "Main Event" in t and "<strong>Jon Jones</strong>" in box and "[C]" in t and "def." in t and "Stipe Miocic [8]" in t
      and box.index("Jon Jones") < box.index("def.") < box.index("Stipe Miocic"), t)
check("under it in the same box: Method, Weight class and Title fight (Yes for a title bout)", "Method KO/TKO, round 3 (4:29)" in t and "Weight class Heavyweight" in t and "Title fight Yes" in t and box.count("<table>") == 1, t)
bo = text(ufc.box_html("Co-Main Event", co))
check("a fight without a belt says 'Title fight No'; the winner's rank is in brackets too ([2])", "Title fight No" in bo and "Charles Oliveira" in bo and "[2]" in bo and "[7]" in bo and "Method Decision - Unanimous" in bo, bo)
check("an unranked fighter has no brackets at all", "[" not in re.sub(r"\[13\]", "", text(ufc.box_html("Prelims · Top Bout", top))), text(ufc.box_html("x", top)))
nc = copy.deepcopy(main)
nc["red"]["outcome"] = nc["blue"]["outcome"] = "draw"
check("a draw or a no contest gives no box (there is no winner to put first)", ufc.box_html("Main Event", nc) == "")

# ---- the header ------------------------------------------------------------------------------------------------------
ev = ESPN["events"][0]
check("the header: 'UFC 309 · New York · Sun 17 Nov' (the date in Singapore time: 23:00 UTC on 16 November is 7am on the 17th)", ufc.header(ev) == "UFC 309 · New York · Sun 17 Nov", ufc.header(ev))

# ---- the run ----------------------------------------------------------------------------------------------------------------
NOW = datetime(2024, 11, 17, 2, 0, tzinfo=timezone.utc)
got = ufc.run(Src(ESPN, H309), NOW, {})
html = got["blocks"][0]
check("the run: the header above, then three boxes (main event, co-main event, Prelims top bout)", len(got["blocks"]) == 1 and html.startswith('<p class="subhead">UFC 309 · New York · Sun 17 Nov</p>') and html.count('<div class="ufc">') == 3
      and [m for m in re.findall(r'<th class="tt" colspan="3">([^<]*)</th>', html)] == ["Main Event", "Co-Main Event", "Prelims · Top Bout"], html[:300])
check("each event is shown once", ufc.run(Src(ESPN, H309), NOW, got["state"])["blocks"] == [] and len(got["state"]["done"]) == 1)
check("an event more than 40 hours old is not news", ufc.run(Src(ESPN, H309), NOW + timedelta(days=3), {})["blocks"] == [])
check("a different sport's event (not UFC) is ignored", ufc.run(Src({"events": [{**ESPN["events"][0], "name": "PFL 10: A vs. B"}]}, H309), NOW, {})["blocks"] == [])
pre = copy.deepcopy(ESPN)
pre["events"][0]["status"]["type"]["state"] = "pre"
check("a card that has not finished gives nothing", ufc.run(Src(pre, H309), NOW, {})["blocks"] == [])
fb = ufc.run(Src(ESPN, None), NOW, {})
ft = text(fb["blocks"][0]) if fb["blocks"] else ""
check("when UFC.com cannot be read, ESPN's bare result gives the main event and the co-main event without ranks or a belt (so those rows are left out)",
      "Main Event" in ft and "Jon Jones def. Stipe Miocic" in ft.replace("  ", " ") and "[" not in ft and "Title fight" not in ft and "Weight class Heavyweight" in ft and "Ended round 3 (4:29)" in ft, ft)
check("when both ESPN and UFC.com fail, nothing and no error", ufc.run(Src(ESPN, H309, boom="espn"), NOW, {}, [])["blocks"] == [])
fails = []
ufc.run(Src(ESPN, None), NOW, {}, fails)
check("a UFC.com page that cannot be read is counted", fails)
check("a page laid out differently gives nothing rather than a wrong box", ufc.parse("<html><body>no fights here</body></html>") == {"main": [], "prelims": [], "early": []} and ufc.three(ufc.parse("<div>x</div>")) == [])


# ---- Fight Nights (added by D the same day) and finding the address ------------------------------------------------------------
HFN = (FX / "ufc_com_fn_20251122.html").read_text()
fn_event = {"id": "600052000", "name": "UFC Fight Night: Tsarukyan vs. Hooker", "date": "2025-11-22T15:00Z", "venues": [{"address": {"city": "Doha"}}], "status": {"type": {"state": "post", "completed": True}}, "competitions": []}
pfn = ufc.parse(HFN)
check("a Fight Night page is read the same way: Main Card, Prelims and Early Prelims, the main event first", [len(pfn[k]) for k in ("main", "prelims", "early")] and len(pfn["main"]) >= 4 and len(ufc.three(pfn)) == 3, {k: len(v) for k, v in pfn.items()})
src = Src({"events": [fn_event]}, {"ufc-fight-night-november-22-2025": HFN})
got = ufc.run(src, datetime(2025, 11, 23, 2, 0, tzinfo=timezone.utc), {})
check("a Fight Night is covered: its header is its name, the city and the date in Singapore time (15:00 UTC on the 22nd is 11pm there), then the three boxes",
      got["blocks"] and got["blocks"][0].startswith('<p class="subhead">UFC Fight Night: Tsarukyan vs. Hooker \u00b7 Doha \u00b7 Sat 22 Nov</p>') and got["blocks"][0].count('<div class="ufc">') == 3, got["blocks"][:1])
check("the Fight Night's address is the date it was held: ufc-fight-night-november-22-2025 is tried first", src.asked[0] == "ufc-fight-night-november-22-2025", src.asked)
night = {"id": "1", "name": "UFC Fight Night: A vs. B", "date": "2026-11-08T01:00Z"}
check("the addresses to try for a Fight Night: the day of the start, the day before, the day after (a late card is dated the day before where it was held)",
      ufc.slugs(night) == ["ufc-fight-night-november-08-2026", "ufc-fight-night-november-07-2026", "ufc-fight-night-november-09-2026"], ufc.slugs(night))
num = {"id": "2", "name": "UFC 331: A vs. B", "date": "2026-11-15T01:00Z"}
check("a numbered event is ufc-331, but an address from the events list with a sponsor in front (cryptocom-ufc-331) is tried first", ufc.slugs(num) == ["ufc-331"] and ufc.slugs(num, ["ufc-332", "cryptocom-ufc-331", "ufc-fight-night-x"]) == ["cryptocom-ufc-331", "ufc-331"])
src2 = Src({"events": [{**fn_event, "date": "2025-11-23T03:00Z"}]}, {"ufc-fight-night-november-22-2025": HFN})
got2 = ufc.run(src2, datetime(2025, 11, 23, 12, 0, tzinfo=timezone.utc), {})
check("an address that gives a page with no fights is skipped for the next one (a card at 03:00 UTC on the 23rd was held on the 22nd)", got2["blocks"] and src2.asked[:2] == ["ufc-fight-night-november-23-2025", "ufc-fight-night-november-22-2025"], src2.asked)
src3 = Src({"events": [{**ESPN["events"][0], "name": "UFC 309: Jones vs. Miocic"}]}, {"cryptocom-ufc-309": H309}, listing=["cryptocom-ufc-309"])
check("the events list is used to find a sponsored address", ufc.run(src3, NOW, {})["blocks"] and src3.asked[0] == "cryptocom-ufc-309", src3.asked)

_g = ufc.run(Src(ESPN, H309), NOW, {})
check("a title fight is a Big Stuff story: UFC 309's heavyweight title, winner first, with how it ended", _g.get("stories") == ["UFC 309: Jon Jones def. Stipe Miocic for the heavyweight title (KO/TKO, round 3 (4:29))"], _g.get("stories"))
check("the co-main event (no belt) is not a story, and the fallback gives none", len(_g["stories"]) == 1 and ufc.run(Src(ESPN, None), NOW, {})["stories"] == [])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
