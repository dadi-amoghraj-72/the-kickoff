"""Tests for the major events read from Wikipedia (darts, chess, hockey, handball, women's football ...; badminton has its own tests) and the chess results from Lichess. The Wikipedia pages are real 2025 pages;
the Lichess tier 5 paths use made-up games in the real layout (no elite event was running when this was built). Run: .venv/bin/python scripts/test_majors.py"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import chess_live, majors  # noqa: E402

FX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


rd = lambda n: (FX / f"majors_{n}.txt").read_text()  # noqa: E731
PAGES = {"2025 Grand Slam of Darts": rd("gsod_2025"), "2025 PDC World Darts Championship": rd("pdc_wc_2025"), "2025 World Men's Handball Championship": rd("handball_m_2025"),
         "2025 Men's Hockey Asia Cup": rd("euro_hockey_w_2025")}


class Wiki:
    def __init__(self, pages, boom=False):
        self.pages, self.boom, self.asked = pages, boom, []

    def wikitext(self, title):
        self.asked.append(title)
        if self.boom:
            raise RuntimeError("down")
        return self.pages.get(title, "")


# ---- the page readers on real pages -----------------------------------------------------------------
b = majors.infobox(rd("gsod_2025"))
check("infobox: the darts page's dates and winner are read (the winner is a flag template around a link)", b["dates"] == "8–16 November 2025" and majors.champion_of(b) == "Luke Littler", b.get("winner"))
check("end dates: a range within a month, across a year, and without a year (the title's year is used)", majors.end_date("8–16 November 2025", 2025) == date(2025, 11, 16)
      and majors.end_date("15 December 2024 – {{nowrap|3 January 2025}}", 2025) == date(2025, 1, 3) and majors.end_date("9–17 August", 2025) == date(2025, 8, 17) and majors.end_date("", 2025) is None)
check("a country code in a flag template becomes the country (handball and hockey champions)", majors.champion_of(majors.infobox(rd("handball_m_2025"))) == "Denmark" and majors.champion_of(majors.infobox(rd("euro_hockey_w_2025"))) == "Netherlands")
check("a champion field that says TBD or is empty is no champion", majors.champion_of({"winner": "TBD"}) is None and majors.champion_of({"champion": ""}) is None and majors.champion_of({}) is None)

# ---- the calendar -------------------------------------------------------------------------------------
c = {(n, y) for _, n, _, _, y in majors.candidates(date(2025, 11, 17))}
check("in November only the November events are looked at (the Grand Slam of Darts, the women's handball worlds ...), never March's or July's events", ("Grand Slam of Darts", 2025) in c and not any(n in ("World Men's Handball Championship", "Candidates Tournament") for n, _ in c), sorted(c))
check("in January the PDC World Championship is found under the title of that year, and the previous year's events still in their window", any(n == "PDC World Championship" for n, _ in {(n, y) for _, n, _, _, y in majors.candidates(date(2026, 1, 3))}))

# ---- the run ----------------------------------------------------------------------------------------------
w = Wiki(PAGES)
got = majors.run(w, date(2025, 11, 17))
check("darts: the day after the Grand Slam of Darts final, the winner is reported once, with the calendar's name, the year and a Wikipedia link", [(s, t) for s, t, _, _ in got if s == "darts"] == [("darts", "Grand Slam of Darts 2025: Luke Littler won")]
      and got[0][3] == "https://en.wikipedia.org/wiki/2025_Grand_Slam_of_Darts", got)
check("four days after the end the event is no longer news", majors.run(Wiki(PAGES), date(2025, 11, 20)) == [])
check("before the end date nothing is reported (the champion field is not read ahead of the dates)", majors.run(Wiki(PAGES), date(2025, 11, 10)) == [])
got = majors.run(Wiki(PAGES), date(2025, 3, 17))
orig = majors.CALENDAR
majors.CALENDAR = [("handball", "World Men's Handball Championship", ["{y} World Men's Handball Championship"], {2}, "infobox")]
got = majors.run(Wiki(PAGES), date(2025, 2, 3))
majors.CALENDAR = orig
check("handball: the champions of the world championship, a country not a code", got and got[0][1] == "World Men's Handball Championship 2025: Denmark won", got)
check("a page that does not exist gives nothing and does not stop the others", majors.run(Wiki({}), date(2025, 11, 17)) == [])
fails = []
check("a Wikipedia that is down gives nothing and the failure is counted, never an error", majors.run(Wiki(PAGES, boom=True), date(2025, 11, 17), fails) == [] and fails, fails)

# ---- Lichess chess --------------------------------------------------------------------------------------------
def game(w, b, res, we=2700, be=2700, rnd=1):
    return f'[Event "Round {rnd}: {w} - {b}"]\n[Round "{rnd}.1"]\n[White "{w}"]\n[Black "{b}"]\n[Result "{res}"]\n[WhiteElo "{we}"]\n[BlackElo "{be}"]\n\n1. e4 e5 {res}'


pgn = "\n\n".join([game("Gukesh, D", "Firouzja, Alireza", "1-0", 2780, 2760), game("Caruana, Fabiano", "Nakamura, Hikaru", "1/2-1/2", 2790, 2800),
                   game("Abdusattorov, Nodirbek", "Wei Yi", "0-1", 2750, 2730), game("Giri, Anish", "Erigaisi, Arjun", "1/2-1/2", 2745, 2780), game("A", "B", "*")])
g = chess_live.parse_pgn(pgn)
check("PGN: finished games are read with names, result and ratings; an unfinished game ('*') is left out", len(g) == 4 and g[0]["white"] == "Gukesh, D" and g[0]["elo"] == (2780, 2760))
check("surnames: 'Gukesh, D' is Gukesh; a plain 'Wei Yi' keeps its longest word", chess_live.surname("Gukesh, D") == "Gukesh" and chess_live.surname("Praggnanandhaa R") == "Praggnanandhaa")
check("the decisive games come with the highest combined rating first, named by surname", chess_live.decisive(g) == ["Gukesh beat Firouzja", "Wei beat Abdusattorov"], chess_live.decisive(g))
table = chess_live.standings([chess_live.parse_pgn(game("A", "B", "1-0")), chess_live.parse_pgn(game("A", "C", "1/2-1/2")), chess_live.parse_pgn(game("B", "C", "0-1"))])
check("standings: points summed over the rounds", table == {"A": 1.5, "B": 0, "C": 1.5})

NOW = datetime(2027, 1, 31, 12, 0, tzinfo=timezone.utc)
ms = lambda dt: int(dt.timestamp() * 1000)  # noqa: E731


class Lichess:
    def __init__(self, items, pgns, tour=None, boom=False):
        self.items, self.pgns, self.t, self.boom = items, pgns, tour or {"rounds": []}, boom

    def top(self):
        if self.boom:
            raise RuntimeError
        return {"active": [], "past": {"currentPageResults": self.items}}

    def round_pgn(self, rid):
        return self.pgns[rid]

    def tour(self, tid):
        return self.t


def item(name, tier, rid, finished_h, last_day_h=-100):
    fin = ms(NOW.replace(hour=12) - __import__("datetime").timedelta(hours=finished_h))
    return {"tour": {"id": "T1", "name": name, "slug": "x", "tier": tier, "dates": [fin - 86400000 * 10, fin + last_day_h * 3600000]}, "round": {"id": rid, "name": "Round 13", "finished": True, "finishedAt": fin, "url": f"https://lichess.org/broadcast/x/{rid}"}}


out = chess_live.run(Lichess([item("Tata Steel Chess 2027 | Masters", 5, "R13", 5)], {"R13": pgn}), NOW)
check("an elite round that just finished: the top decisive games and the draws, named for the event without its '| Masters' suffix",
      out and out[0][0].startswith("Tata Steel Chess 2027, Round 13: Gukesh beat Firouzja") and "; 2 drawn" in out[0][0] and out[0][2] == "https://lichess.org/broadcast/x/R13", out)
rr = {"rounds": [{"id": "R12", "finished": True}, {"id": "R13", "finished": True}]}
final = chess_live.run(Lichess([item("Tata Steel Chess 2027 | Masters", 5, "R13", 5, last_day_h=-2)], {"R13": pgn, "R12": game("Gukesh, D", "Giri, Anish", "1-0")}, rr), NOW)
check("the last round of a round-robin: the winner and the points, summed from every round", any("wins on 2 points" in t and "Gukesh" in t for t, *_ in final), final)
check("a minor event (tier 3) is ignored, and so is an old round", chess_live.run(Lichess([item("Club open", 3, "R13", 5), item("Tata Steel", 5, "R13", 60)], {"R13": pgn}), NOW) == [])
star = chess_live.run(Lichess([item("Chola Chess Open | Open", 4, "R13", 5)], {"R13": pgn}), NOW)
check("the spotlight: a listed Indian player's win in a tier 4 event gets a line (the draw does not)", [t for t, *_ in star] == ["Gukesh beat Firouzja in Chola Chess Open, Round 13"], star)
check("Lichess down gives nothing, never an error", chess_live.run(Lichess([], {}, boom=True), NOW) == [])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
