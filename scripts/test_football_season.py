"""Offline tests for football's season notes on saved real data: the 2025-26 final Premier League table, the real FA Cup and Champions League finals of May 2026, and the
Wikipedia award pages. Run: python3 scripts/test_football_season.py"""
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import football_season as fs, honours  # noqa: E402
from kickoff.sources import espn, espn_season  # noqa: E402

FX = ROOT / "tests" / "fixtures"
L = lambda n: json.loads((FX / n).read_text())  # noqa: E731
RAW = L("espn_eng1_table_2025.json")
ROWS = espn.parse_table(RAW)
FA = [espn.parse_match(e, "eng.fa") for e in L("espn_facup_final_2026.json")["events"]]
CL = [espn.parse_match(e, "uefa.champions") for e in L("espn_cl_final_2026.json")["events"]]
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


import html as _html  # noqa: E402
text = lambda h: _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))).strip()  # noqa: E731

# ---- the Premier League's last day ----
raw_entries = RAW["children"][0]["standings"]["entries"]
raw_top = max(raw_entries, key=lambda e: next(s["value"] for s in e["stats"] if s["name"] == "points"))
raw_bottom = sorted(raw_entries, key=lambda e: next(s["value"] for s in e["stats"] if s["name"] == "rank"))[-3:]
note = text(fs.pl_closing(ROWS, 2025))
check("the closing note: the 2025-26 season, the champions with their points, the top four and the three relegated", note.startswith("That's the 2025-26 Premier League season. Arsenal are champions with 85 points.") and "complete the top four" in note and note.endswith("are relegated.") and "Arsenal, Man City" not in note, note)
check("independent: the champions and the relegated are the raw feed's points leader and bottom three by rank", raw_top["team"]["displayName"] == "Arsenal" and all(e["team"]["shortDisplayName"] in note for e in raw_bottom), (raw_top["team"]["displayName"], [e["team"]["shortDisplayName"] for e in raw_bottom]))
check("a table with a club that has not played 38 gives no note (the last day is not over), and neither does a short table", fs.pl_closing([dict(x, played=37) if i == 5 else x for i, x in enumerate(ROWS)], 2025) == "" and fs.pl_closing(ROWS[:19], 2025) == "")

# ---- the cup finals ----
check("the FA Cup final of 16 May 2026 is found: stage 'final', Manchester City won 1-0 away at Wembley (ESPN lists Chelsea as the home side)", FA[0]["stage"] == "final" and FA[0]["winner"] == "away" and (FA[0]["home_score"], FA[0]["away_score"]) == (0, 1), FA[0])
check("the FA Cup note: the winners and the score from the winner's side", text(fs.final_note("FA Cup", FA, 2025)) == "That's the 2025-26 FA Cup. Manchester City are the winners, beating Chelsea 1–0.", text(fs.final_note("FA Cup", FA, 2025)))
check("the Champions League final went to penalties: PSG are champions 'on penalties after a 1–1 draw', Arsenal the beaten side", text(fs.final_note("Champions League", CL, 2025)) == "That's the 2025-26 Champions League. Paris Saint-Germain are champions, beating Arsenal on penalties after a 1–1 draw.", text(fs.final_note("Champions League", CL, 2025)))
check("a match that is not a final, not finished or has no winner gives no note", fs.final_note("FA Cup", [dict(FA[0], stage="semifinals")], 2025) == "" and fs.final_note("FA Cup", [dict(FA[0], completed=False)], 2025) == "" and fs.final_note("FA Cup", [dict(FA[0], winner=None)], 2025) == "" and fs.final_note("FA Cup", [], 2025) == "")

# ---- the awards pages ----
PAGES = {name: (FX / f).read_text() for name, f in (("Premier League Player of the Season", "wiki_pl_pots.txt"), ("Premier League Young Player of the Season", "wiki_pl_young.txt"),
                                                     ("Premier League Manager of the Season", "wiki_pl_manager.txt"), ("Premier League Golden Boot", "wiki_pl_boot.txt"),
                                                     ("Premier League Golden Glove", "wiki_pl_glove.txt"))}


class Wiki:
    def __init__(self, pages=PAGES):
        self.pages = pages

    def wikitext(self, page):
        return self.pages.get(page, "")


codes = {"Arsenal": "ARS", "Manchester City": "MCI", "Manchester United": "MUN"}
items = fs.pl_award_items(Wiki(), 2025, codes)
got = {i["label"]: (i["data"]["name"], i["data"]["team"]) for i in items}
check("the five main awards for 2025-26: Fernandes (Manchester United), O'Reilly (Manchester City), Arteta (Arsenal), Haaland (Manchester City), Raya (Arsenal), with the clubs' codes",
      got == {"Player": ("Bruno Fernandes", "MUN"), "Young Player": ("Nico O'Reilly", "MCI"), "Manager": ("Mikel Arteta", "ARS"), "Golden Boot": ("Erling Haaland", "MCI"), "Golden Glove": ("David Raya", "ARS")}, got)
check("independent: each name is the one the raw page has beside the 2025–26 row", all(n.split()[-1].lower().replace("'", "") in re.sub(r"[^a-z ]", "", PAGES[p].lower()) for n, p in (("Bruno Fernandes", "Premier League Player of the Season"), ("Mikel Arteta", "Premier League Manager of the Season"), ("David Raya", "Premier League Golden Glove"))))
check("a season whose row is not on the page yet (2026-27) gives no items, and so does a page that is down", fs.pl_award_items(Wiki(), 2026, codes) == [] and fs.pl_award_items(Wiki({}), 2025, codes) == [])

# ---- the whole block ----
DAY = date(2026, 5, 25)
NOW = datetime(2026, 5, 24, 23, 0, tzinfo=timezone.utc)
out = fs.build(DAY, NOW, ROWS, FA, CL, {}, client=None, wiki=Wiki())
check("on the morning after the last day (25 May 2026): the Premier League block has the Awards table and the closing note; the FA Cup and Champions League notes are there", "Premier League Awards" in out["pl"] and "champions with 85 points" in out["pl"] and "FA Cup" in out["fa"] and "Champions League" in out["cl"], text(out["pl"])[:200])
check("the state remembers what has been said", out["state"]["pl_closed"] == 2025 and out["state"]["fa_closed"] == 2025 and out["state"]["cl_closed"] == 2025 and out["state"]["awards"]["season"] == 2025)
out2 = fs.build(date(2026, 5, 26), NOW, ROWS, FA, CL, out["state"], client=None, wiki=Wiki())
check("the next morning: nothing is said again", out2["pl"] == "" and out2["fa"] == "" and out2["cl"] == "")
out3 = fs.build(date(2026, 11, 4), NOW, [], [], [], {}, client=None, wiki=Wiki({}))
check("an ordinary day in November: nothing at all, and no error", out3["pl"] == "" and out3["fa"] == "" and out3["cl"] == "")
out4 = fs.build(DAY, NOW, "not rows", None, None, {}, client=None, wiki=Wiki())
check("bad input never raises", isinstance(out4, dict) and "state" in out4)

# ---- the preview: the first match day from the league's calendar ----
CAL = ["2026-08-21T07:00Z", "2026-08-22T07:00Z", "2026-08-23T07:00Z", "2026-08-24T07:00Z", "2026-08-28T07:00Z"]
src = espn_season.Source("soccer", "eng.1", get_json=lambda u: {"leagues": [{"calendar": CAL}]}, pause=0)
check("the Premier League's season starts on the first date of ESPN's calendar (21 August 2026)", src.regular_season_start(2026) == "2026-08-21T07:00Z")
from kickoff import preview  # noqa: E402
check("the preview is due from 14 August (a week before) to the eve of the opener, not on the day", [preview.due("2026-08-21T07:00Z", date(2026, 8, d), 2026, []) for d in (13, 14, 20, 21)] == [False, True, True, False])
check("the season is called 2026-27 for the Premier League", preview.season_label("epl", 2026) == "2026-27" and preview.season_label("nba", 2027) == "2026-27")
no_log = espn_season.Source("soccer", "eng.1", get_json=lambda u: (_ for _ in ()).throw(espn_season.http.SourceError("HTTP 404")) if "transactions" in u else {"articles": []}, pause=0)
check("football has no transaction log: asking for it gives an empty list, not an error", no_log.transactions() == [])

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
