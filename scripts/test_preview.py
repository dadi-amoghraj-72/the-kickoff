"""Offline tests for the "season is coming" note, on saved real ESPN data (the NBA's news and transaction log of 4 November 2026) and a fake Claude. Run: python3 scripts/test_preview.py"""
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import preview  # noqa: E402

FX = ROOT / "tests" / "fixtures"
DATA = json.loads((FX / "espn_season_nba.json").read_text())
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


class FakeSource:
    def __init__(self, start=DATA["start"]):
        self.start, self.calls = start, []

    def regular_season_start(self, season):
        self.calls.append("start")
        return self.start

    def news(self):
        self.calls.append("news")
        return DATA["news"]

    def transactions(self):
        self.calls.append("tx")
        return DATA["tx"]


class FakeClient:
    """Claude: returns the bullets it is given, as the JSON the code asks for."""
    def __init__(self, bullets, stop="end_turn"):
        self.bullets, self.stop, self.asked = bullets, stop, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **body):
        self.asked.append(body)
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=3000, output_tokens=400), stop_reason=self.stop,
                               content=[SimpleNamespace(type="text", text=json.dumps({"bullets": self.bullets}))])


# ---- when ----
START = DATA["start"]                 # 2026-10-20T07:00Z, the 2026-27 NBA regular season (not the preseason)
check("the real start date is the regular season's (20 October 2026)", START.startswith("2026-10-20"), START)
check("due: 7 days before through the eve, once", [preview.due(START, date(2026, 10, d), 2027, []) for d in (12, 13, 19, 20, 21)] == [False, True, True, False, False])
check("due: not again once the season is noted", preview.due(START, date(2026, 10, 15), 2027, [2027]) is False and preview.due(START, date(2026, 10, 15), 2027, [2026]) is True)
check("an unreadable date is never due", preview.due(None, date(2026, 10, 15), 2027, []) is False and preview.due("junk", date(2026, 10, 15), 2027, []) is False)

# ---- the material ----
items = preview.material(DATA["news"], DATA["tx"])
texts = [x["text"] for x in items]
check("material: numbered from 1, news first, then trades and signings; waivers and the like are left out", [x["n"] for x in items] == list(range(1, len(items) + 1)) and not any(": Waived" in t for t in texts) and any("Re-signed" in t for t in texts), len(items))
raw_keep = [t for t in DATA["tx"] if t["description"].lower().startswith(preview.KEEP)]
check("independent: as many transaction items as the raw log has rows starting with a kept verb", len(items) - sum(1 for a in DATA["news"] if a.get("headline") or a.get("description")) == len(raw_keep), (len(items), len(raw_keep)))

# ---- the check on what Claude writes ----
tx_n = next(x["n"] for x in items if x["text"].startswith("Utah Jazz: Re-signed C Jusuf Nurkic"))
good = {"text": "The Jazz re-signed centre Jusuf Nurkic.", "items": [tx_n]}
check("a bullet whose names and numbers are in the cited item stands", preview.supported(good, items))
check("a bullet naming someone the cited item does not mention is dropped", not preview.supported({"text": "The Jazz re-signed Jusuf Nurkic and Luka Doncic.", "items": [tx_n]}, items))
check("a bullet with a number the item does not have is dropped", not preview.supported({"text": "The Jazz re-signed Jusuf Nurkic for 99 million.", "items": [tx_n]}, items))
check("a bullet citing nothing, or an item that does not exist, is dropped", not preview.supported({"text": "Nurkic stayed.", "items": []}, items) and not preview.supported({"text": "Nurkic stayed.", "items": [99999]}, items))

# ---- writing it ----
five = [{"text": f"The Jazz re-signed Jusuf Nurkic ({i}).", "items": [tx_n]} for i in range(5)]
five = [{"text": "The Jazz re-signed Jusuf Nurkic.", "items": [tx_n]}] * 3 + [{"text": "Zion Williamson won the title.", "items": [tx_n]}]
c = FakeClient(five)
bullets, usage = preview.write(c, "NBA", "2026-27", items)
check("write: the unsupported bullet (Zion Williamson) is dropped, three solid ones stay, and the cost is reported", len(bullets) == 3 and all("Nurkic" in b for b in bullets) and usage == {"input": 3000, "output": 400}, bullets)
check("the prompt carries the numbered items and says to use only them", "Items:\n1. " in c.asked[0]["messages"][0]["content"] and "ONLY" in c.asked[0]["system"], c.asked[0]["system"][:80])
thin = FakeClient(five[:2])
check("fewer than three solid bullets means no note", preview.write(thin, "NBA", "2026-27", items)[0] == [])
check("no client or no material: no note and no call", preview.write(None, "NBA", "2026-27", items)[0] == [] and preview.write(FakeClient(five), "NBA", "2026-27", [])[0] == [])
check("a cut-off Claude reply: no note, no error", preview.write(FakeClient(five, stop="max_tokens"), "NBA", "2026-27", items)[0] == [])

# ---- the block for a morning ----
src = FakeSource()
h, done, cost = preview.block("nba", "basketball", "NBA", 2027, date(2026, 10, 15), [], FakeClient(five), source=src)
check("block: five days before the season, the note is written once: a heading with the weekday and date, three bullets, the season marked done, a cost", h.startswith("<h4>The 2026-27 NBA season starts Tue 20 Oct</h4>") and h.count("<li>") == 3 and done == [2027] and cost > 0, h[:200])
src2 = FakeSource()
h2, done2, cost2 = preview.block("nba", "basketball", "NBA", 2027, date(2026, 10, 16), done, FakeClient(five), source=src2)
check("the next morning: nothing, and no news or transactions are fetched", h2 == "" and done2 == [2027] and src2.calls == ["start"] and cost2 == 0)
src3 = FakeSource()
h3, d3, c3 = preview.block("nba", "basketball", "NBA", 2027, date(2026, 11, 4), [], FakeClient(five), source=src3)
check("in November (the season has started): nothing", h3 == "" and src3.calls == ["start"])
h4, d4, c4 = preview.block("nba", "basketball", "NBA", 2027, date(2026, 10, 15), [], None, source=(src4 := FakeSource()))
check("without Claude: no note, no calls, season not marked done", h4 == "" and d4 == [] and src4.calls == [])
h5, d5, c5 = preview.block("nba", "basketball", "NBA", 2027, date(2026, 10, 15), [], FakeClient(five[:1]), source=FakeSource())
check("a thin day: no note, the season is not marked done, so tomorrow tries again", h5 == "" and d5 == [] and c5 > 0)


class Boom(FakeSource):
    def regular_season_start(self, season):
        raise OSError("down")


check("ESPN down: no note, no error, state unchanged", preview.block("nba", "basketball", "NBA", 2027, date(2026, 10, 15), [2026], FakeClient(five), source=Boom()) == ("", [2026], 0.0))
check("season labels: 2026-27 for the NBA, the year for the others", preview.season_label("nba", 2027) == "2026-27" and preview.season_label("nfl", 2026) == "2026" and preview.season_label("mlb", 2027) == "2027")

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
