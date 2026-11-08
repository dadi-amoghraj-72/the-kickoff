"""Tests for athletics and swimming (kickoff/athletics.py, D 2026-11-08): world records, close finishes, world leads and meeting records only, on real saved Wikipedia pages:
the 2025 Brussels Diamond League, the 2025 World Championships in Tokyo, the 2025 World Indoor Championships in Nanjing, the 2025 Diamond League calendar and both world-record lists
as of 8 November 2026. Run: .venv/bin/python scripts/test_athletics.py"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import athletics as a  # noqa: E402
from kickoff import around  # noqa: E402

F = ROOT / "tests" / "fixtures" / "athletics"
page = lambda n: (F / f"{n}.wiki").read_text()  # noqa: E731
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:400]}"))
    results.append(ok)


# ---- the rules ----
check("times read as seconds: 9.77, 1:41.86, 2:06:30; a distance is not a time", (a.seconds("9.77"), a.seconds("1:41.86"), a.seconds("2:06:30"), a.seconds("17")) == (9.77, 101.86, 7590.0, None))
check("D's margins: 0.03s up to 400m and the 4x100, 0.5s for 800m to 1500m and the 4x400 legs, 1.5s for longer", [a.margin_needed(a.metres(e)) for e in ("200 metres", "4 × 100 metres relay", "400 metres hurdles", "800 metres", "1500 metres", "4 × 400 metres relay", "5000 metres", "3000 metres steeplechase", "Marathon")]
      == [0.03, 0.03, 0.03, 0.5, 0.5, 0.03, 1.5, 1.5, 1.5], None)
check("a field event has no race distance, and its mark carries the unit", a.metres("Pole vault") is None and a.show_mark("6.30", "Pole vault") == "6.30m" and a.show_mark("9.77", "100 metres") == "9.77" and a.show_mark("8550", "Decathlon") == "8550")

# ---- a Diamond League meeting: Brussels 2025 ----
bru = a.findings(a.meeting_finals(page("dl_brussels_2025")), "Brussels Diamond League")
close = [t for k, t, _ in bru if k == "close"]
check("Brussels: the men's 200m (Ogando 20.16, Gregory 20.19: 0.03s) is a close finish", "Brussels Diamond League · Men's 200m final: Ogando 20.16, Gregory 20.19" in close, close)
check("Brussels: the women's 100m (Jefferson-Wooden 10.76, Richardson 11.08: 0.32s) is not", not any("100m final" in t for t in close), close)
check("Brussels: the women's 1500m (Hiltz 3:55.94, Hall 3:56.33: 0.39s, under 0.5s) is", any("Women's 1500m final: Hiltz 3:55.94, Hall 3:56.33" in t for t in close), close)
check("Brussels: no field event is ever a close finish", not any(w in t for t in close for w in ("jump", "throw", "vault", "put")), close)

# ---- a championship: Tokyo 2025 ----
tok = a.findings(a.medal_finals(page("wch_2025")), "Tokyo World Championships", "championship record")
texts = [t for _, t, _ in tok]
check("Tokyo: Duplantis' world record, written D's way", "World record: Armand Duplantis, Men's pole vault, 6.30m (Tokyo World Championships)" in texts, [t for t in texts if "World record" in t])
check("Tokyo: a world lead and a championship record are said together on one line (McLaughlin-Levrone 47.78)", "Tokyo World Championships · Women's 400m: Sydney McLaughlin-Levrone 47.78, world lead and championship record" in texts)
check("Tokyo: a relay is its country, not its runners", "Tokyo World Championships · Men's 4 × 100m relay: United States 37.29, world lead" in texts and not any("<br" in t for t in texts))
check("Tokyo: the men's 1500m (Nader 3:34.10, Wightman 3:34.12) and the marathon (Simbu and Petros both 2:09:48) are close finishes",
      any("Men's 1500m final: Nader 3:34.10, Wightman 3:34.12" in t for t in texts) and any("Men's marathon final: Simbu 2:09:48, Petros 2:09:48" in t for t in texts))
check("Tokyo: the men's 100m (Seville 9.77, Thompson 9.82: 0.05s) is not a close finish", not any("Men's 100m final" in t for t in texts))
check("the host city and last day come from the infobox", a.champ_dates_city(page("wch_2025"), 2025) == (date(2025, 9, 21), "Tokyo") and a.champ_dates_city(page("wich_2025"), 2025) == (date(2025, 3, 23), "Nanjing"))
nj = [t for _, t, _ in a.findings(a.medal_finals(page("wich_2025")), "Nanjing World Indoor Championships", "championship record")]
check("indoors too: Nanjing's men's 60m (Azu 6.49, Kennedy 6.50) is a close finish; Díaz's triple jump a world lead", any("Men's 60m final: Azu 6.49, Kennedy 6.50" in t for t in nj) and any("Andy Díaz 17.80m, world lead" in t for t in nj), nj)

# ---- the calendar ----
cal = a.dl_meetings(page("dl_2025_calendar"), 2025)
check("the 2025 Diamond League calendar: 15 meetings with their city and last day (Brussels 22 August; Shanghai's was in Shaoxing)", len(cal) == 15 and ("2025 Memorial Van Damme", "Brussels", date(2025, 8, 22)) in cal
      and ("2025 Shanghai Diamond League", "Shaoxing", date(2025, 5, 3)) in cal, cal[:3])

# ---- world-record lists ----
ath = a.recent_records("athletics", page("wr_athletics_2026-11-08"), date(2026, 3, 13))
check("the athletics list: Duplantis' 6.31m of 12 March 2026 is found the next day, with the meeting and city", ath == [("World record: Armand Duplantis, Men's pole vault, 6.31m (Mondo Classic, Uppsala)", "wr:men's pole vault:6.31")], ath)
check("and not a week later", a.recent_records("athletics", page("wr_athletics_2026-11-08"), date(2026, 3, 20)) == [])
sw = a.recent_records("swimming", page("wr_swimming_2026-11-08"), date(2026, 11, 1))
check("the swimming list: the six short-course world records of the US trials on 30 October 2026, each with its course",
      len(sw) == 6 and "World record: Jack Alexy, Men's 100m freestyle (short course), 44.64 (U.S. Short Course World Championship Trials, Westmont)" in [t for t, _ in sw], [t for t, _ in sw])
check("nothing on a day with no new record", a.recent_records("swimming", page("wr_swimming_2026-11-08"), date(2026, 11, 20)) == [])
_u = page("u20_athletics_2026-11-08")
check("youth records (D, 2026-11-08): the World U20 record list, Gout Gout's 19.67 of 12 April 2026 the next morning, a time with no stray 'm'",
      a.recent_records("athletics", _u, date(2026, 4, 13), "World U20 record") == [("World U20 record: Gout Gout, Men's 200m, 19.67 (Australian Championships)", "u20:wr:men's 200m:19.67")],
      a.recent_records("athletics", _u, date(2026, 4, 13), "World U20 record"))
_j = a.recent_records("swimming", page("junior_swimming_2026-11-08"), date(2026, 8, 14), "World junior record")
check("and swimming's world junior records (Boys' and Girls', long and short course): the Pan Pacs of 13 August 2026", len(_j) == 3 and any("World junior record: Shin Ohashi, Boys' 100m breaststroke (long course), 58.54" in t for t, _ in _j), [t for t, _ in _j])
check("one record, one id, however it is written (the meeting's '6.30' and the list's '6.30m')", a.wr_uid("Men's pole vault", "6.30") == a.wr_uid("Men's pole vault", "6.30m"))


# ---- the morning: the whole run on a fake Wikipedia ----
class Wiki:
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def wikitext(self, title):
        self.asked.append(title)
        return self.pages.get(title, "")


w = Wiki({"List of world records in athletics": page("wr_athletics_2026-11-08"), "List of world records in swimming": page("wr_swimming_2026-11-08"),
          "2025 Diamond League": page("dl_2025_calendar"), "2025 Memorial Van Damme": page("dl_brussels_2025"), "2025 World Athletics Championships": page("wch_2025")})
day = a.run(w, date(2025, 8, 23))
check("the morning after Brussels: its close finishes come, and only that meeting's page is read (not every meeting of the season)",
      any("Brussels Diamond League · Men's 200m final" in t for _, t, _ in day["athletics"]) and [t for t in w.asked if t in {p_ for p_, _, _ in cal}] == ["2025 Memorial Van Damme"], w.asked)
w2 = Wiki(w.pages)
tokyo_day = a.run(w2, date(2025, 9, 22))
check("the morning after Tokyo: its world record first, then the close finishes, then the world leads and records", [k for k, _, _ in tokyo_day["athletics"]][:1] == ["wr"]
      and [k for k, _, _ in tokyo_day["athletics"]] == sorted([k for k, _, _ in tokyo_day["athletics"]], key=lambda k: {"wr": 0, "close": 1, "mark": 2}[k]))
quiet = a.run(Wiki(w.pages), date(2026, 11, 20))
check("a November morning with no new record and no meeting: nothing at all", quiet == {"athletics": [], "swimming": []}, quiet)
broken = a.run(Wiki({}), date(2025, 9, 22), fails := [])
check("missing pages give nothing, never an error", broken == {"athletics": [], "swimming": []})


class Src(Wiki):
    def rugby(self, league):
        return {"events": []}

    def golf(self, tour):
        return {"events": []}

    def ufc(self):
        return {"events": []}

    def news(self):
        return []

    def rugby_table(self, league):
        return {}


from datetime import datetime, timezone  # noqa: E402
around.GAMES = []
o = around.run(datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc), {}, Src({"List of world records in swimming": page("wr_swimming_2026-11-08")}), None)
h = o["sections"][0]["html"] if o["sections"] else ""
check("Other Sports: a Swimming heading with each world record, 'World record:' in bold", '">Swimming</h4>' in h and "<li><strong>World record:</strong> Jack Alexy, Men&#x27;s 100m freestyle (short course), 44.64" in h, h[:400])
check("at most five lines a morning; the sixth record is not marked seen, so it can come the next morning", h.count("<li>") == 5 and sum(1 for u in o["state"]["around"]["seen"] if u.startswith("wr:swim")) == 5)
check("a world record is a Star Of The Night candidate", sum(1 for e in o["events"] if e.get("milestone") and e["text"].startswith("World record:")) == 5)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
